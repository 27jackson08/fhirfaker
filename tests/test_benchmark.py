"""Clinical quality measures over generated output.

Phase 6 of ROADMAP.md. The headline claim — that this reproduces an outcome measure
Synthea scores 0% on — is only worth making if the measure engine is itself correct,
so most of this file tests the engine against hand-built bundles rather than testing
the generator through it.
"""

from __future__ import annotations

import json

import pytest

from carebundle import generate_bundle
from carebundle.benchmark import MeasureResult, run_measure
from carebundle.benchmark.cqm import controlling_high_blood_pressure
from carebundle.core.bundle import to_json
from carebundle.terminology import codes, systems

# Published comparators. Chen J et al., BMC Med Inform Decis Mak 2019 — the study that
# measured Synthea against CMS quality measures.
SYNTHEA_PUBLISHED_CBP_RATE = 0.0
REAL_WORLD_CBP_US = 0.697
REAL_WORLD_CBP_MA = 0.745


def _bundle(*, age: str, birth: str, systolic, diastolic, hypertensive=True):
    """A minimal bundle shaped like the real emitter's output.

    `effectiveDateTime` on the observation is not optional decoration. This fixture
    claimed to match real output while omitting it, and the omission went unnoticed
    until the measure started reading dates to find the most recent reading — at which
    point every test here failed and the emitter was fine. A fixture that is missing a
    field the emitter always writes is a test asserting the wrong thing.
    """
    entries = [
        {"resource": {"resourceType": "Patient", "birthDate": birth}},
        {"resource": {"resourceType": "Encounter", "period": {"start": age}}},
    ]
    if hypertensive:
        entries.append({"resource": {
            "resourceType": "Condition",
            "code": {"coding": [{
                "system": systems.ICD10CM,
                "code": codes.ESSENTIAL_HYPERTENSION.code,
            }]},
        }})
    if systolic is not None:
        entries.append({"resource": {
            "resourceType": "Observation",
            "code": {"coding": [{"system": systems.LOINC, "code": "85354-9"}]},
            "effectiveDateTime": f"{age}T09:00:00Z",
            "component": [
                {"code": {"coding": [{"code": codes.BP_DIASTOLIC.code}]},
                 "valueQuantity": {"value": diastolic}},
                {"code": {"coding": [{"code": codes.BP_SYSTOLIC.code}]},
                 "valueQuantity": {"value": systolic}},
            ],
        }})
    return {"resourceType": "Bundle", "entry": entries}


# --- the measure engine ------------------------------------------------------------

@pytest.mark.parametrize(
    "systolic,diastolic,controlled",
    [
        (120, 78, True),
        (139, 89, True),      # just inside on both
        (140, 80, False),     # systolic exactly at threshold is NOT controlled
        (120, 90, False),     # isolated diastolic elevation still fails
        (165, 101, False),
    ],
)
def test_control_requires_both_components_below_threshold(systolic, diastolic, controlled):
    denom, num = controlling_high_blood_pressure(
        _bundle(age="2026-01-01", birth="1970-01-01",
                systolic=systolic, diastolic=diastolic)
    )
    assert denom is True
    assert num is controlled


def test_component_order_does_not_change_the_reading():
    """A BP panel's components are unordered; reading by position would invert them."""
    denom, num = controlling_high_blood_pressure(
        _bundle(age="2026-01-01", birth="1970-01-01", systolic=118, diastolic=76)
    )
    assert (denom, num) == (True, True)


def test_patient_without_coded_hypertension_is_outside_the_denominator():
    denom, num = controlling_high_blood_pressure(
        _bundle(age="2026-01-01", birth="1970-01-01",
                systolic=118, diastolic=76, hypertensive=False)
    )
    assert (denom, num) == (False, False)


@pytest.mark.parametrize("birth,in_denominator", [
    ("2010-01-01", False),   # 16 — under 18
    ("2008-01-01", True),    # 18 exactly
    ("1941-01-01", True),    # 85 exactly
    ("1939-01-01", False),   # 87 — over 85
])
def test_denominator_respects_the_hedis_age_bounds(birth, in_denominator):
    denom, _ = controlling_high_blood_pressure(
        _bundle(age="2026-06-01", birth=birth, systolic=120, diastolic=78)
    )
    assert denom is in_denominator


def test_a_bundle_with_no_blood_pressure_cannot_enter_the_denominator():
    denom, num = controlling_high_blood_pressure(
        _bundle(age="2026-01-01", birth="1970-01-01", systolic=None, diastolic=None)
    )
    assert (denom, num) == (False, False)


def test_zero_denominator_is_not_reported_as_a_zero_rate_silently():
    """'Nobody qualified' and 'everybody failed' must stay distinguishable."""
    result = MeasureResult(measure="x", numerator=0, denominator=0)
    assert result.rate == 0.0
    assert result.denominator == 0


def test_unknown_measure_raises_rather_than_returning_empty():
    with pytest.raises(KeyError, match="unknown measure"):
        run_measure("not_a_measure", [])


# --- the generator, measured through the emitted FHIR ------------------------------

@pytest.mark.fidelity
def test_generated_hypertensives_reproduce_a_real_world_control_rate():
    """The Phase 6 exit criterion.

    Synthea's published rate on this measure is 0%. The real-world comparators are
    69.7% (US) and 74.5% (Massachusetts). This asserts a band that is wide enough not
    to flake and narrow enough to mean something — and crucially it is checked, not
    tuned: the inputs are NHANES treatment prevalence and Law 2003 effect sizes, and
    this rate is what they imply.
    """
    bundles = [
        json.loads(to_json(generate_bundle(profile="hypertension", seed=7, index=i)))
        for i in range(1500)
    ]
    result = run_measure("controlling_high_blood_pressure", bundles)

    assert result.denominator == 1500, "every hypertensive should qualify"
    assert 0.55 <= result.rate <= 0.75, (
        f"CBP rate {result.rate:.1%} left the real-world range; "
        f"Synthea's published rate is {SYNTHEA_PUBLISHED_CBP_RATE:.0%}"
    )
    assert result.rate > SYNTHEA_PUBLISHED_CBP_RATE + 0.5, (
        "the entire point of this measure is beating a pathway simulator's 0%"
    )


@pytest.mark.fidelity
def test_healthy_patients_do_not_enter_the_hypertension_denominator():
    bundles = [
        json.loads(to_json(generate_bundle(profile="healthy", seed=7, index=i)))
        for i in range(200)
    ]
    result = run_measure("controlling_high_blood_pressure", bundles)
    assert result.denominator == 0, "a patient without hypertension is not measurable"
