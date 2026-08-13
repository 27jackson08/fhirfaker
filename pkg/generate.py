"""Bundle generation — the public API.

A bundle is produced from a single profile draw, so the Conditions, Observations and
MedicationRequests inside it all come from one coherent sample rather than being
decided independently. That is the whole point of the correlation engine
(build doc Section 8).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from pkg.builders.clinical import (
    build_blood_pressure,
    build_condition,
    build_lab_observation,
    build_vital_observation,
)
from pkg.builders.orders import (
    build_diagnostic_report,
    build_encounter,
    build_medication_request,
)
from pkg.builders.people import build_patient, build_practitioner
from pkg.core import uscore
from pkg.core.bundle import Entry, build_transaction_bundle, to_json  # noqa: F401
from pkg.core.ids import deterministic_uuid, stable_digest, urn_uuid
from pkg.models.r4 import Bundle, CodeableConcept
from pkg.profiles.base import ProfileDraw, draw
from pkg.profiles.library import get_profile
from pkg.terminology import codes

# Injected rather than read from the clock: any datetime.now() call would destroy the
# determinism contract (build doc Section 9).
DEFAULT_REFERENCE_DATE = date(2026, 1, 1)

# US Core's Encounter.type value set draws on CPT-4 (AMA-licensed) and SNOMED CT
# (affiliate-licensed). Neither can ship here, so we assert text only and let the
# extensible binding degrade to a warning rather than embed an unlicensed code.
AMBULATORY_VISIT_TYPE = CodeableConcept(text="Ambulatory visit")

SEX_TO_FHIR_GENDER = {"F": "female", "M": "male"}

# Analyte -> (LOINC code, unit). Drives which lab Observations a bundle emits.
LAB_ANALYTES = (
    ("hba1c", codes.HBA1C, codes.UNIT_PERCENT),
    ("glucose", codes.GLUCOSE, codes.UNIT_MG_DL),
    ("creatinine", codes.CREATININE, codes.UNIT_MG_DL),
    ("egfr", codes.EGFR, codes.UNIT_EGFR),
    ("cholesterol_total", codes.CHOLESTEROL_TOTAL, codes.UNIT_MG_DL),
    ("hdl", codes.HDL, codes.UNIT_MG_DL),
    ("ldl", codes.LDL_CALCULATED, codes.UNIT_MG_DL),
    ("triglycerides", codes.TRIGLYCERIDES, codes.UNIT_MG_DL),
)

# Analyte -> (LOINC code, US Core vitals profile, unit).
VITAL_ANALYTES = (
    ("height_cm", codes.BODY_HEIGHT, uscore.BODY_HEIGHT, codes.UNIT_CM),
    ("weight_kg", codes.BODY_WEIGHT, uscore.BODY_WEIGHT, codes.UNIT_KG),
    ("bmi", codes.BMI, uscore.BMI, codes.UNIT_KG_M2),
)


def _birth_date(rng, age_range: tuple[int, int], reference: date) -> tuple[date, float]:
    low, high = age_range
    age = int(rng.integers(low, high + 1))
    day_offset = int(rng.integers(0, 365))
    born = reference - timedelta(days=age * 365 + day_offset)
    return born, (reference - born).days / 365.25


def _require_sex(sex: str) -> None:
    if sex not in SEX_TO_FHIR_GENDER:
        raise ValueError(f"sex must be one of {sorted(SEX_TO_FHIR_GENDER)}, got {sex!r}")


def generate_patient(
    *,
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
):
    """Generate a single US Core Patient with no clinical history."""
    _require_sex(sex)
    rng = np.random.default_rng([seed, index])
    born, _ = _birth_date(rng, age_range, reference_date)
    return build_patient(
        resource_id=deterministic_uuid(seed, "patient", index),
        sex=sex,
        birth_date=born,
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )


def generate_draw(
    *,
    profile: str = "type2_diabetes",
    seed: int,
    sex: str = "F",
    age_years: float = 55.0,
    index: int = 0,
) -> ProfileDraw:
    """Draw clinical values without building FHIR — useful for analysis and testing."""
    _require_sex(sex)
    # The profile key enters the seed so two profiles sharing a marginal do not draw
    # identical values at the same seed. stable_digest, not hash(): the built-in is
    # salted per process and would break byte-identical output across runs.
    rng = np.random.default_rng([seed, index, stable_digest(profile)])
    return draw(get_profile(profile, sex), rng=rng, age_years=age_years, sex=sex)


def generate_bundle(
    *,
    profile: str = "type2_diabetes",
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
) -> Bundle:
    """Generate a transaction Bundle for one patient drawn from `profile`."""
    _require_sex(sex)

    rng = np.random.default_rng([seed, index])
    born, age_years = _birth_date(rng, age_range, reference_date)

    patient = build_patient(
        resource_id=deterministic_uuid(seed, "patient", index),
        sex=sex,
        birth_date=born,
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )
    practitioner = build_practitioner(
        resource_id=deterministic_uuid(seed, "practitioner", index),
        family_index=3,
        given_index=5,
    )
    drawn = generate_draw(
        profile=profile, seed=seed, sex=sex, age_years=age_years, index=index
    )

    def urn(role: str) -> str:
        return urn_uuid(seed, role, index)

    def rid(role: str) -> str:
        return deterministic_uuid(seed, role, index)

    visit = reference_date.isoformat()
    start, end = f"{visit}T09:00:00Z", f"{visit}T09:30:00Z"

    entries = [
        Entry(urn("patient"), patient),
        Entry(urn("practitioner"), practitioner),
        Entry(
            urn("encounter"),
            build_encounter(
                resource_id=rid("encounter"),
                subject_urn=urn("patient"),
                start=start,
                end=end,
                type_concept=AMBULATORY_VISIT_TYPE,
            ),
        ),
    ]

    for position, code in enumerate(drawn.conditions):
        role = f"condition-{position}"
        entries.append(
            Entry(
                urn(role),
                build_condition(
                    resource_id=rid(role),
                    code=code,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter"),
                    onset_date=(reference_date - timedelta(days=730)).isoformat(),
                ),
            )
        )

    lab_urns = []
    for analyte, code, unit in LAB_ANALYTES:
        if analyte not in drawn.analytes:
            continue
        role = f"obs-{analyte}"
        lab_urns.append(urn(role))
        entries.append(
            Entry(
                urn(role),
                build_lab_observation(
                    resource_id=rid(role),
                    code=code,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter"),
                    performer_urn=urn("practitioner"),
                    effective=start,
                    value=drawn.analytes[analyte],
                    unit=unit,
                ),
            )
        )

    for analyte, code, vital_profile, unit in VITAL_ANALYTES:
        if analyte not in drawn.analytes:
            continue
        role = f"obs-{analyte}"
        entries.append(
            Entry(
                urn(role),
                build_vital_observation(
                    resource_id=rid(role),
                    code=code,
                    profile=vital_profile,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter"),
                    performer_urn=urn("practitioner"),
                    effective=start,
                    value=drawn.analytes[analyte],
                    unit=unit,
                ),
            )
        )

    entries.append(
        Entry(
            urn("obs-bp"),
            build_blood_pressure(
                resource_id=rid("obs-bp"),
                subject_urn=urn("patient"),
                encounter_urn=urn("encounter"),
                performer_urn=urn("practitioner"),
                effective=start,
                systolic=drawn.analytes["systolic"],
                diastolic=drawn.analytes["diastolic"],
            ),
        )
    )

    for position, code in enumerate(drawn.medications):
        role = f"medreq-{position}"
        entries.append(
            Entry(
                urn(role),
                build_medication_request(
                    resource_id=rid(role),
                    medication=code,
                    subject_urn=urn("patient"),
                    requester_urn=urn("practitioner"),
                    encounter_urn=urn("encounter"),
                    authored_on=visit,
                ),
            )
        )

    if lab_urns:
        entries.append(
            Entry(
                urn("report-lab"),
                build_diagnostic_report(
                    resource_id=rid("report-lab"),
                    subject_urn=urn("patient"),
                    performer_urn=urn("practitioner"),
                    effective=start,
                    issued=end,
                    result_urns=lab_urns,
                ),
            )
        )

    return build_transaction_bundle(entries)
