"""Multi-criteria co-occurrence.

The instrument written after TSTR turned out to be blind to the thing it was meant to
probe. Synthea's side needs a generated population and cannot run in CI; this package's
side can, and it is the side that would regress silently.
"""

from __future__ import annotations

import json

import pytest

from carebundle.benchmark import cooccurrence as co
from carebundle.core.bundle import to_json
from carebundle.generate import generate_cohort


@pytest.mark.parametrize("row,sex,expected", [
    ({"bmi": 34.0, "triglycerides": 210.0, "hdl": 35.0, "glucose": 118.0}, "M", 4),
    ({"bmi": 23.0, "triglycerides": 90.0, "hdl": 62.0, "glucose": 88.0}, "M", 0),
    # Exactly on the thresholds: three are at-or-above, HDL alone is strict.
    ({"bmi": 30.0, "triglycerides": 150.0, "hdl": 40.0, "glucose": 100.0}, "M", 3),
])
def test_criteria_counting(row, sex, expected):
    assert co.criteria_met(row, sex) == expected


def test_hdl_threshold_differs_by_sex():
    """A 45 mg/dL HDL is low in a woman and normal in a man.

    Applying one threshold to both would move the co-occurrence rate in opposite
    directions for the two sexes and partly cancel in the total, which is the kind of
    error a single headline number hides.
    """
    row = {"bmi": 20.0, "triglycerides": 90.0, "hdl": 45.0, "glucose": 85.0}
    assert co.criteria_met(row, "F") == 1
    assert co.criteria_met(row, "M") == 0


def test_measure_is_monotone_in_k():
    """P(>=1) >= P(>=2) >= P(>=3) >= P(>=4), by construction."""
    rows = list(co.rows_from_bundles(
        json.loads(to_json(b)) for b in generate_cohort(count=600, seed=42, sex="mixed")
    ))
    result = co.measure(rows)
    rates = [result.rate(k) for k in (1, 2, 3, 4)]
    assert rates == sorted(rates, reverse=True), rates


def test_empty_input_is_not_a_rate_of_zero():
    """An empty population has no rate; reporting 0% would be the CBP trap again."""
    result = co.measure([])
    assert result.n == 0


def test_cooccurrence_rate_is_stable():
    """Regression guard on this package's own co-occurrence.

    Wide because the point is to catch the joint structure collapsing, not to pin a
    third decimal: if the analytes ever become independent again, the multi-criteria
    rate falls sharply while every marginal keeps passing.
    """
    rows = list(co.rows_from_bundles(
        json.loads(to_json(b)) for b in generate_cohort(count=1500, seed=42, sex="mixed")
    ))
    result = co.measure(rows)
    assert result.n > 1000, "too few usable panels to judge"
    assert 0.10 < result.rate(3) < 0.45, (
        f"3-of-4 co-occurrence is {result.rate(3):.1%}, outside the expected band"
    )


def test_independence_control_is_computed_and_sane():
    """The control is the finding, so it gets its own guard.

    Without it this module reports a rate that looks like evidence for whichever
    mechanism the reader already believes. Synthea's 3-of-4 rate is a quarter of
    reality's, which reads as missing dependence until the ratio shows it clusters
    *more* than reality and the real cause is mild marginals.
    """
    rows = list(co.rows_from_bundles(
        json.loads(to_json(b)) for b in generate_cohort(count=1500, seed=42, sex="mixed")
    ))
    result = co.measure(rows)
    assert len(result.marginals) == 4
    assert all(0.0 <= p <= 1.0 for p in result.marginals)
    # Independence expectations are probabilities and monotone in k, like the observed.
    exp = [result.independent[k] for k in (1, 2, 3, 4)]
    assert exp == sorted(exp, reverse=True)
    assert all(0.0 <= e <= 1.0 for e in exp)
    # This package clusters more than independence at the strict end, which is the whole
    # point of modelling the joint distribution.
    assert result.dependence_ratio(3) > 1.0


def test_independent_rates_match_a_hand_computed_case():
    """Four fair coins: P(>=3 of 4) = 5/16, P(>=4) = 1/16."""
    rates = co._independent_rates((0.5, 0.5, 0.5, 0.5))
    assert rates[4] == pytest.approx(1 / 16)
    assert rates[3] == pytest.approx(5 / 16)
    assert rates[1] == pytest.approx(15 / 16)


def test_a_perfectly_independent_population_scores_ratio_one():
    """Sanity on the control itself: independent inputs must give ~1.0, not 1.45."""
    import random

    rng = random.Random(7)
    rows = []
    for _ in range(20000):
        rows.append((
            {"bmi": 31.0 if rng.random() < 0.4 else 25.0,
             "triglycerides": 160.0 if rng.random() < 0.3 else 100.0,
             "hdl": 35.0 if rng.random() < 0.3 else 60.0,
             "glucose": 110.0 if rng.random() < 0.4 else 90.0},
            "M",
        ))
    result = co.measure(rows)
    assert result.dependence_ratio(3) == pytest.approx(1.0, abs=0.12)
