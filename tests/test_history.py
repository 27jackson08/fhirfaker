"""Bounded longitudinal output (ROADMAP.md Phase 7).

The feature's whole claim is that a clinical value visibly responds to treatment over
time — the thing a care-pathway simulator structurally cannot show. These test that
claim, plus the property that makes the feature safe to add: it does not disturb the
existing determinism contract.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from carebundle.core.bundle import dangling_references, to_json
from carebundle.correlation import relations
from carebundle.history import blood_pressure_course, generate_history, visits_of

# --- the clinical claim -------------------------------------------------------------

def test_pressure_falls_as_therapy_is_escalated():
    course = blood_pressure_course(
        pretreatment_systolic=168.0, pretreatment_diastolic=104.0, visits=4
    )
    systolics = [systolic for systolic, _, _ in course]
    assert systolics == sorted(systolics, reverse=True), "pressure must not rise"
    assert systolics[0] > systolics[-1], "four visits of titration must achieve something"


def test_first_visit_is_recorded_before_the_regimen_it_prompts():
    """A real first presentation is measured, then treated — not treated, then measured."""
    course = blood_pressure_course(
        pretreatment_systolic=162.0, pretreatment_diastolic=100.0, visits=3
    )
    assert course[0] == (162.0, 100.0, 0)


def test_a_patient_already_at_goal_is_never_escalated():
    course = blood_pressure_course(
        pretreatment_systolic=128.0, pretreatment_diastolic=80.0, visits=4
    )
    assert {agents for _, _, agents in course} == {0}


def test_escalation_stops_once_goal_is_reached():
    course = visits_of(profile="hypertension", seed=42, sex="F", visits=6)
    at_goal = [v for v in course if v.at_goal]
    assert at_goal, "precondition: this patient should reach goal"
    first = at_goal[0].index
    after = {v.agents for v in course[first:]}
    assert len(after) == 1, "the regimen should stop changing once the patient is at goal"


def test_agent_count_is_bounded():
    course = blood_pressure_course(
        pretreatment_systolic=220.0, pretreatment_diastolic=130.0, visits=12
    )
    assert max(agents for _, _, agents in course) <= 3


# --- the FHIR ------------------------------------------------------------------------

def test_history_emits_one_encounter_and_one_pressure_per_visit():
    bundle = json.loads(to_json(generate_history(seed=42, visits=5)))
    kinds = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert kinds.count("Encounter") == 5
    assert kinds.count("Observation") == 5
    assert kinds.count("Patient") == 1, "one patient, many visits"


def test_history_has_no_dangling_references():
    assert not dangling_references(generate_history(seed=7, visits=4))


def test_visits_are_ordered_and_end_on_the_reference_date():
    reference = date(2026, 1, 1)
    course = visits_of(seed=3, visits=4, reference_date=reference)
    dates = [v.on for v in course]
    assert dates == sorted(dates)
    assert dates[-1] == reference, (
        "a quality measure scores the most recent reading, so it must be the last one"
    )


def test_history_is_deterministic():
    first = to_json(generate_history(seed=11, visits=4))
    second = to_json(generate_history(seed=11, visits=4))
    assert first == second


# --- the property that makes this safe to add ---------------------------------------

def test_history_does_not_disturb_single_visit_output():
    """`generate_bundle` must be byte-identical whether or not this module is used.

    The determinism contract is the reason to be careful here: a shared RNG stream
    would have made adding a feature a breaking change for every existing seed.
    """
    from carebundle import generate_bundle

    before = to_json(generate_bundle(profile="hypertension", seed=42))
    generate_history(seed=42, visits=6)
    after = to_json(generate_bundle(profile="hypertension", seed=42))
    assert before == after


# --- validation ----------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [{"visits": 0}, {"visits": -1}, {"interval_days": 0}])
def test_invalid_arguments_are_rejected(kwargs):
    with pytest.raises(ValueError):
        generate_history(seed=1, **kwargs)


@pytest.mark.conformance
def test_history_bundle_is_us_core_conformant(tmp_path):
    from carebundle.conformance.validator import validate

    path = tmp_path / "history.json"
    path.write_text(to_json(generate_history(profile="hypertension", seed=42, visits=4)))
    result = validate(path)
    assert not result.errors, "US Core errors:\n" + "\n".join(
        f"  {i.location} :: {i.message}" for i in result.errors
    )


def test_goal_thresholds_come_from_the_shared_constants():
    """The course and the CBP measure must agree on what 'controlled' means."""
    assert relations.GOAL_SYSTOLIC == 140.0
    assert relations.GOAL_DIASTOLIC == 90.0
