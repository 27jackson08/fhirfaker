"""Bounded longitudinal output: one patient across several visits.

This is deliberately *not* lifecycle simulation. There is no birth, no death, no
disease-progression modules and no comorbidity cascade — competing with Synthea on
breadth loses, and the build document says so in Section 14. What this adds is a time
axis for the one thing the distributional model can already do that a pathway simulator
cannot: show a clinical value responding to treatment.

`BENCHMARK.md` records the gap this closes. Blood pressure is modelled as the
*equilibrium* a titrated patient reaches, which is the right value for a
most-recent-reading quality measure but hides the mechanism. Here the mechanism is
visible: a patient arrives uncontrolled, therapy is escalated at each visit while they
remain above goal, and the recorded pressure falls toward target at published effect
sizes.

Every number comes from the same two sources the single-visit model already cites, so
this introduces no new evidence claims:

  * Law MR, Wald NJ, Morris JK, BMJ 2003;326:1427 — 9.1/5.5 mmHg per standard-dose
    agent, larger from a higher starting pressure.
  * Lancet 2025 (484 trials) — a further 1.5 mmHg systolic per dose doubling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from carebundle.builders.clinical import build_blood_pressure, build_condition
from carebundle.builders.orders import build_encounter
from carebundle.builders.people import build_patient, build_practitioner
from carebundle.core.bundle import Entry, build_transaction_bundle
from carebundle.core.ids import deterministic_uuid, urn_uuid
from carebundle.correlation import relations
from carebundle.generate import (
    AMBULATORY_VISIT_TYPE,
    DEFAULT_REFERENCE_DATE,
    _birth_date,
    _require_sex,
    generate_draw,
)
from carebundle.models.r4 import Bundle

DEFAULT_VISITS = 4
DEFAULT_INTERVAL_DAYS = 90  # A quarterly review, the usual cadence for titration.


@dataclass(frozen=True)
class Visit:
    """One encounter in a course of treatment."""

    index: int
    on: date
    systolic: float
    diastolic: float
    agents: int
    at_goal: bool


def blood_pressure_course(
    *,
    pretreatment_systolic: float,
    pretreatment_diastolic: float,
    visits: int,
    start_agents: int = 0,
) -> list[tuple[float, float, int]]:
    """Pressure at each visit as therapy is escalated toward goal.

    Returns `(systolic, diastolic, agents)` per visit. The first visit is recorded
    *before* the regimen it prompts, which is what a real first presentation looks like:
    the clinician measures, then prescribes.

    Escalation adds an agent while the patient is above 140/90, up to three, and then
    doubles doses — the order real practice uses, since a second agent from a different
    class buys more than doubling the first.
    """
    if visits < 1:
        raise ValueError(f"visits must be at least 1, got {visits}")

    course: list[tuple[float, float, int]] = []
    agents = start_agents
    for _ in range(visits):
        systolic, diastolic = relations.titrated_response(
            systolic=pretreatment_systolic,
            diastolic=pretreatment_diastolic,
            agent_count=agents,
        )
        course.append((systolic, diastolic, agents))
        if systolic >= relations.GOAL_SYSTOLIC or diastolic >= relations.GOAL_DIASTOLIC:
            agents = min(agents + 1, 3)
    return course


def generate_history(
    *,
    profile: str = "hypertension",
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
    visits: int = DEFAULT_VISITS,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
) -> Bundle:
    """One patient over `visits` encounters, with blood pressure responding to therapy.

    The last visit is on `reference_date` and earlier ones are spaced `interval_days`
    before it, so the most recent reading is the one a quality measure would score —
    matching how the single-visit bundle is read.

    Deliberately additive: `generate_bundle` is untouched, so the determinism contract
    for existing seeds is unaffected by anything here.
    """
    _require_sex(sex)
    if visits < 1:
        raise ValueError(f"visits must be at least 1, got {visits}")
    if interval_days < 1:
        raise ValueError(f"interval_days must be at least 1, got {interval_days}")

    # Distinct stream from generate_bundle so demographic draws here cannot shift
    # the single-visit output for the same seed.
    rng = np.random.default_rng([seed, index, 0x415354])
    born, age_years = _birth_date(rng, age_range, reference_date)
    drawn = generate_draw(
        profile=profile, seed=seed, sex=sex, age_years=age_years, index=index
    )

    pre_systolic = drawn.raw.get("pretreatment_systolic", drawn.raw["systolic"])
    pre_diastolic = drawn.raw.get("pretreatment_diastolic", drawn.raw["diastolic"])
    course = blood_pressure_course(
        pretreatment_systolic=float(pre_systolic),
        pretreatment_diastolic=float(pre_diastolic),
        visits=visits,
    )

    def urn(role: str) -> str:
        return urn_uuid(seed, role, index)

    def rid(role: str) -> str:
        return deterministic_uuid(seed, role, index)

    entries = [
        Entry(
            urn("patient"),
            build_patient(
                resource_id=rid("patient"),
                sex=sex,
                birth_date=born,
                family_index=int(rng.integers(0, 10)),
                given_index=int(rng.integers(0, 10)),
            ),
        ),
        Entry(
            urn("practitioner"),
            build_practitioner(
                resource_id=rid("practitioner"), family_index=3, given_index=5
            ),
        ),
    ]

    first_visit_on = reference_date - timedelta(days=interval_days * (visits - 1))
    for position, (systolic, diastolic, _agents) in enumerate(course):
        on = first_visit_on + timedelta(days=interval_days * position)
        encounter_role = f"encounter-{position}"
        entries.append(
            Entry(
                urn(encounter_role),
                build_encounter(
                    resource_id=rid(encounter_role),
                    subject_urn=urn("patient"),
                    start=f"{on.isoformat()}T09:00:00Z",
                    end=f"{on.isoformat()}T09:30:00Z",
                    type_concept=AMBULATORY_VISIT_TYPE,
                ),
            )
        )
        bp_role = f"blood-pressure-{position}"
        entries.append(
            Entry(
                urn(bp_role),
                build_blood_pressure(
                    resource_id=rid(bp_role),
                    subject_urn=urn("patient"),
                    encounter_urn=urn(encounter_role),
                    effective=f"{on.isoformat()}T09:15:00Z",
                    systolic=relations.to_reported(systolic, "blood_pressure"),
                    diastolic=relations.to_reported(diastolic, "blood_pressure"),
                    performer_urn=urn("practitioner"),
                ),
            )
        )

    # Conditions attach to the first encounter: that is when they were recognised.
    for position, code in enumerate(drawn.conditions):
        role = f"condition-{position}"
        entries.append(
            Entry(
                urn(role),
                build_condition(
                    resource_id=rid(role),
                    code=code,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter-0"),
                    onset_date=(first_visit_on - timedelta(days=730)).isoformat(),
                ),
            )
        )

    return build_transaction_bundle(entries)


def visits_of(
    *,
    profile: str = "hypertension",
    seed: int,
    sex: str = "F",
    age_years: float = 58.0,
    index: int = 0,
    visits: int = DEFAULT_VISITS,
    reference_date: date = DEFAULT_REFERENCE_DATE,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
) -> list[Visit]:
    """The course as data rather than FHIR, for inspection and for tests."""
    drawn = generate_draw(
        profile=profile, seed=seed, sex=sex, age_years=age_years, index=index
    )
    pre_systolic = float(drawn.raw.get("pretreatment_systolic", drawn.raw["systolic"]))
    pre_diastolic = float(drawn.raw.get("pretreatment_diastolic", drawn.raw["diastolic"]))
    course = blood_pressure_course(
        pretreatment_systolic=pre_systolic,
        pretreatment_diastolic=pre_diastolic,
        visits=visits,
    )
    first_visit_on = reference_date - timedelta(days=interval_days * (visits - 1))
    return [
        Visit(
            index=position,
            on=first_visit_on + timedelta(days=interval_days * position),
            systolic=systolic,
            diastolic=diastolic,
            agents=agents,
            at_goal=(
                systolic < relations.GOAL_SYSTOLIC
                and diastolic < relations.GOAL_DIASTOLIC
            ),
        )
        for position, (systolic, diastolic, agents) in enumerate(course)
    ]


__all__ = [
    "DEFAULT_INTERVAL_DAYS",
    "DEFAULT_VISITS",
    "Visit",
    "blood_pressure_course",
    "generate_history",
    "visits_of",
]
