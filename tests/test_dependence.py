"""The cross-domain dependence benchmark.

This measures the claim that replaced the withdrawn outcome-measure one, so it gets a
regression guard rather than living only in a document. Synthea's side cannot run in CI
— it needs a 197 MB JAR and a generated population — but this package's side can, and
that is the side that would silently regress.
"""

from __future__ import annotations

import json

import pytest

from carebundle.benchmark import dependence
from carebundle.core.bundle import to_json
from carebundle.generate import generate_cohort


@pytest.fixture(scope="module")
def cells():
    rows = dependence.panels(
        json.loads(to_json(b))
        for b in generate_cohort(count=1200, seed=42, sex="mixed")
    )
    return dependence.measure(rows)


def test_every_configured_pair_is_measurable(cells):
    """A pair that silently drops out would flatter the mean deviation."""
    measured = {(c.pair, c.sex) for c in cells}
    expected = {(p, s) for p in dependence.PAIRS for s in ("F", "M")}
    assert measured == expected, f"unmeasured cells: {sorted(expected - measured)}"


def test_dependence_tracks_nhanes(cells):
    """Mean absolute deviation from the NHANES extraction.

    0.10 is deliberately loose against a measured 0.05: the cohort mixes strata, so
    between-group covariance sits on top of the within-stratum values that were fitted,
    and the point of this test is to catch the dependence disappearing rather than to
    pin it to three decimals. Synthea measures 0.192 on the same seven pairs.
    """
    deviations = [c.deviation for c in cells]
    mean = sum(deviations) / len(deviations)
    assert mean < 0.10, f"mean |deviation| rose to {mean:.3f}; dependence has drifted"


def test_no_correlation_has_the_wrong_sign(cells):
    """The failure that is qualitative rather than quantitative.

    A heavier patient with a *higher* HDL is not a slightly wrong number, it is a
    patient no clinician would recognise. Synthea gets 4 of these 14 cells backwards,
    including triglycerides against HDL in men.
    """
    wrong = [(c.pair, c.sex, c.observed, c.target) for c in cells if not c.sign_agrees]
    assert not wrong, f"sign disagrees with NHANES: {wrong}"


def test_panel_of_requires_a_sex_and_birth_date():
    """An unusable bundle must drop out rather than enter with a guessed sex."""
    assert dependence.panel_of({"entry": []}) is None
    assert dependence.panel_of(
        {"entry": [{"resource": {"resourceType": "Patient", "gender": "unknown"}}]}
    ) is None


def test_panel_of_takes_the_richest_date_not_the_last():
    """Contemporaneity is the point: values from different years are not a panel."""
    def obs(code, value, when):
        return {"resource": {
            "resourceType": "Observation",
            "code": {"coding": [{"code": code}]},
            "valueQuantity": {"value": value},
            "effectiveDateTime": when,
        }}

    bundle = {"entry": [
        {"resource": {"resourceType": "Patient", "gender": "female",
                      "birthDate": "1970-01-01"}},
        obs("29463-7", 70.0, "2020-01-01"),   # weight, alone
        obs("2085-9", 55.0, "2020-01-01"),    # HDL, same day -> richest
        obs("2571-8", 120.0, "2021-06-01"),   # triglycerides, alone and later
    ]}
    panel = dependence.panel_of(bundle)
    assert panel is not None
    assert panel["weight_kg"] == 70.0 and panel["hdl"] == 55.0
    assert "triglycerides" not in panel, "took a later, thinner date over the richest"
