"""Correlation engine: transforms, cited relations, and the joint model."""

from __future__ import annotations

import math

import numpy as np
import pytest

from carebundle.correlation import relations
from carebundle.correlation.distributions import (
    Marginal,
    correlation_from_r_squared,
    sd_from_regression_slope,
    standard_normal_cdf,
    standard_normal_ppf,
)
from carebundle.correlation.engine import JointModel

# --- normal transforms -----------------------------------------------------------

def test_cdf_matches_known_values():
    assert standard_normal_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
    assert standard_normal_cdf(1.96) == pytest.approx(0.975, abs=1e-4)
    assert standard_normal_cdf(-1.96) == pytest.approx(0.025, abs=1e-4)


def test_ppf_inverts_cdf_across_the_range():
    z = np.linspace(-4.0, 4.0, 400)
    assert np.allclose(standard_normal_ppf(standard_normal_cdf(z)), z, atol=1e-6)


def test_ppf_rejects_values_outside_the_open_unit_interval():
    for bad in (0.0, 1.0, -0.1, 1.1):
        with pytest.raises(ValueError, match="0 < u < 1"):
            standard_normal_ppf(np.array([bad]))


# --- truncated-normal moments ----------------------------------------------------

def test_moments_match_an_empirical_sample():
    marginal = Marginal("x", mean=7.8, sd=0.9, low=6.5, high=12.0)
    analytic_mean, analytic_sd = marginal.moments()
    rng = np.random.default_rng(0)
    drawn = marginal.ppf(rng.uniform(1e-9, 1 - 1e-9, 200_000))
    assert analytic_mean == pytest.approx(float(drawn.mean()), abs=0.01)
    assert analytic_sd == pytest.approx(float(drawn.std()), abs=0.01)


def test_truncation_near_the_mean_actually_shifts_the_moments():
    """The effect that broke the first ADAG calibration — worth pinning down."""
    marginal = Marginal("hba1c", mean=7.8, sd=0.90, low=6.5, high=12.0)
    mean, sd = marginal.moments()
    assert mean > 7.8, "a low truncation should pull the mean up"
    assert sd < 0.90, "truncation should shrink the SD"
    assert sd == pytest.approx(0.78, abs=0.02)


def test_untruncated_marginal_keeps_its_nominal_moments():
    marginal = Marginal("x", mean=100.0, sd=10.0, low=40.0, high=160.0)
    mean, sd = marginal.moments()
    assert mean == pytest.approx(100.0, abs=0.01)
    assert sd == pytest.approx(10.0, abs=0.01)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"mean": 1.0, "sd": 0.0, "low": 0.0, "high": 2.0}, "sd must be positive"),
        ({"mean": 1.0, "sd": 1.0, "low": 2.0, "high": 1.0}, "low must be below high"),
        ({"mean": 9.0, "sd": 1.0, "low": 0.0, "high": 2.0}, "outside"),
    ],
)
def test_invalid_marginals_are_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        Marginal("x", **kwargs)


# --- regression algebra ----------------------------------------------------------

def test_correlation_from_r_squared():
    assert correlation_from_r_squared(0.84) == pytest.approx(math.sqrt(0.84))
    with pytest.raises(ValueError):
        correlation_from_r_squared(1.5)


def test_sd_from_regression_slope_inverts_the_slope_identity():
    rho, predictor_sd, slope = 0.9165, 0.78, 28.7
    response_sd = sd_from_regression_slope(
        slope=slope, predictor_sd=predictor_sd, rho=rho
    )
    assert rho * response_sd / predictor_sd == pytest.approx(slope)


# --- CKD-EPI 2021 ----------------------------------------------------------------

def test_ckd_epi_round_trips_creatinine_and_egfr():
    """The inverse must be exact, or the CKD profile silently misses its band."""
    for sex in ("F", "M"):
        for age in (30.0, 58.0, 80.0):
            for target in (12.0, 35.0, 55.0, 75.0, 110.0):
                creatinine = relations.ckd_epi_2021_creatinine(
                    egfr=target, age_years=age, sex=sex
                )
                back = relations.ckd_epi_2021_egfr(
                    creatinine_mg_dl=creatinine, age_years=age, sex=sex
                )
                assert back == pytest.approx(target, rel=1e-9)


def test_egfr_falls_with_rising_creatinine():
    values = [
        relations.ckd_epi_2021_egfr(creatinine_mg_dl=c, age_years=58.0, sex="M")
        for c in (0.8, 1.2, 1.8, 2.5)
    ]
    assert values == sorted(values, reverse=True)


def test_equal_creatinine_gives_women_the_lower_egfr():
    """Counter-intuitive but correct, and worth pinning down.

    The equation carries a +1.2% female factor, so it is tempting to assume women
    score higher at equal creatinine. They do not: kappa is 0.7 for women against 0.9
    for men, so the same creatinine sits further up the curve and that dominates.
    Clinically this is the point — women carry less muscle mass, so a creatinine of
    1.1 mg/dL signals worse kidney function in a woman than in a man.
    """
    common = {"creatinine_mg_dl": 1.1, "age_years": 58.0}
    female = relations.ckd_epi_2021_egfr(**common, sex="F")
    male = relations.ckd_epi_2021_egfr(**common, sex="M")
    assert female < male
    assert female == pytest.approx(58.2, abs=0.5)
    assert male == pytest.approx(77.8, abs=0.5)


def test_age_reduces_egfr():
    common = {"creatinine_mg_dl": 1.0, "sex": "M"}
    assert (
        relations.ckd_epi_2021_egfr(**common, age_years=30.0)
        > relations.ckd_epi_2021_egfr(**common, age_years=70.0)
    )


def test_invalid_ckd_epi_inputs_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        relations.ckd_epi_2021_egfr(creatinine_mg_dl=0.0, age_years=50.0, sex="M")
    with pytest.raises(ValueError, match="'F' or 'M'"):
        relations.ckd_epi_2021_egfr(creatinine_mg_dl=1.0, age_years=50.0, sex="X")


# --- CKD staging -----------------------------------------------------------------

def test_stage_boundaries_tile_the_line_without_gaps():
    """Regression: 44.988 previously fell between G3b's top and G3a's bottom."""
    for egfr in np.arange(0.0, 130.0, 0.013):
        relations.ckd_stage_for(float(egfr))  # must not raise


@pytest.mark.parametrize(
    "egfr,stage",
    [(95.0, "G1"), (75.0, "G2"), (59.99, "G3a"), (45.0, "G3a"),
     (44.988, "G3b"), (30.0, "G3b"), (20.0, "G4"), (5.0, "G5")],
)
def test_known_stage_assignments(egfr, stage):
    assert relations.ckd_stage_for(egfr) == stage


# --- joint model -----------------------------------------------------------------

def test_inconsistent_correlations_are_rejected_not_silently_accepted():
    """Cholesky on a non-PD matrix yields quietly wrong dependence."""
    model = JointModel(
        marginals=(
            Marginal("a", 0.0, 1.0, -5.0, 5.0),
            Marginal("b", 0.0, 1.0, -5.0, 5.0),
            Marginal("c", 0.0, 1.0, -5.0, 5.0),
        ),
        correlations=(("a", "b", 0.99), ("b", "c", 0.99), ("a", "c", -0.99)),
    )
    with pytest.raises(ValueError, match="not positive definite"):
        model.correlation_matrix()


def test_correlation_naming_an_unknown_analyte_raises():
    model = JointModel(
        marginals=(Marginal("a", 0.0, 1.0, -5.0, 5.0),),
        correlations=(("a", "nonexistent", 0.5),),
    )
    with pytest.raises(KeyError, match="nonexistent"):
        model.correlation_matrix()


def test_requested_correlation_is_reproduced_in_the_sample():
    model = JointModel(
        marginals=(
            Marginal("x", 100.0, 15.0, 40.0, 160.0),
            Marginal("y", 50.0, 8.0, 18.0, 82.0),
        ),
        correlations=(("x", "y", 0.6),),
    )
    drawn = model.sample(np.random.default_rng(1), size=50_000)
    observed = float(np.corrcoef(drawn["x"], drawn["y"])[0, 1])
    assert observed == pytest.approx(0.6, abs=0.02)


def test_sampling_is_deterministic_for_a_given_seed():
    model = JointModel(marginals=(Marginal("x", 0.0, 1.0, -4.0, 4.0),))
    first = model.sample(np.random.default_rng(7), size=100)["x"]
    second = model.sample(np.random.default_rng(7), size=100)["x"]
    assert np.array_equal(first, second)


# --- the claim itself ------------------------------------------------------------

def test_a_deterministic_glucose_model_would_fail_the_r_squared_check():
    """Proves the fidelity check is not vacuous.

    The whole differentiator is that glucose carries residual scatter around the ADAG
    line. If a naive deterministic implementation could pass the R^2 check, the check
    would be worthless — so assert that it visibly fails.
    """
    rng = np.random.default_rng(3)
    hba1c = Marginal("hba1c", 7.8, 0.9, 6.5, 12.0).ppf(rng.uniform(1e-9, 1 - 1e-9, 5_000))
    naive_glucose = relations.estimated_average_glucose(hba1c)

    r_squared = float(np.corrcoef(hba1c, naive_glucose)[0, 1] ** 2)
    assert r_squared == pytest.approx(1.0, abs=1e-9)
    assert abs(r_squared - relations.ADAG_R_SQUARED) > 0.02, (
        "a deterministic generator must fall outside the fidelity tolerance"
    )


# --- antihypertensive response (Law 2003) ----------------------------------------

def test_no_agents_leaves_blood_pressure_untouched():
    """An untreated diagnosed hypertensive is the agent_count == 0 case."""
    assert relations.antihypertensive_response(
        systolic=152.0, diastolic=94.0, agent_count=0
    ) == (152.0, 94.0)


def test_one_agent_reproduces_the_published_effect_at_the_reference_pressure():
    """At Law's reference 154/97 the baseline term vanishes, leaving 9.1/5.5 exactly."""
    systolic, diastolic = relations.antihypertensive_response(
        systolic=relations.LAW_REFERENCE_SYSTOLIC,
        diastolic=relations.LAW_REFERENCE_DIASTOLIC,
        agent_count=1,
    )
    assert systolic == pytest.approx(154.0 - 9.1)
    assert diastolic == pytest.approx(97.0 - 5.5)


def test_reduction_is_larger_from_a_higher_starting_pressure():
    """Law: 'for a 10 mm Hg higher blood pressure the reduction was 1.0 mm Hg greater'."""
    low_drop = 140.0 - relations.antihypertensive_response(
        systolic=140.0, diastolic=90.0, agent_count=1
    )[0]
    high_drop = 150.0 - relations.antihypertensive_response(
        systolic=150.0, diastolic=90.0, agent_count=1
    )[0]
    assert high_drop - low_drop == pytest.approx(1.0)


def test_each_added_agent_lowers_pressure_by_less_than_the_one_before():
    """Diminishing returns is per agent, and it falls out of the baseline dependence.

    Note it is *not* 'less than naive n x 9.1'. From a high pre-treatment pressure the
    baseline term makes each reduction larger than 9.1, so sequential application
    lowers pressure further than the naive product, not less far. The property that
    actually holds is that the second agent achieves less than the first.
    """
    start = 170.0
    one = relations.antihypertensive_response(
        systolic=start, diastolic=100.0, agent_count=1
    )[0]
    two = relations.antihypertensive_response(
        systolic=start, diastolic=100.0, agent_count=2
    )[0]

    first_drop, second_drop = start - one, one - two
    assert second_drop < first_drop, "each agent acts on an already-lowered pressure"
    assert second_drop > 0, "a second agent must still lower it further"


def test_treated_pressure_never_falls_below_the_physiological_floor():
    # Far more agents than any real regimen; the point is that the clamp exists at all.
    systolic, diastolic = relations.antihypertensive_response(
        systolic=145.0, diastolic=92.0, agent_count=20
    )
    assert systolic == relations.TREATED_SYSTOLIC_FLOOR
    assert diastolic == relations.TREATED_DIASTOLIC_FLOOR


def test_a_negative_agent_count_raises_rather_than_silently_passing():
    with pytest.raises(ValueError, match="non-negative"):
        relations.antihypertensive_response(
            systolic=150.0, diastolic=90.0, agent_count=-1
        )


# --- dose titration (Lancet 2025) -------------------------------------------------

def test_titration_does_not_touch_a_patient_already_at_goal():
    """Escalating a controlled patient would inflate a control rate from the wrong end."""
    standard = relations.antihypertensive_response(
        systolic=150.0, diastolic=95.0, agent_count=2
    )
    assert standard[0] < relations.GOAL_SYSTOLIC, "precondition: already controlled"
    assert relations.titrated_response(
        systolic=150.0, diastolic=95.0, agent_count=2
    ) == standard


def test_titration_lowers_a_patient_left_above_goal_by_standard_dose():
    standard = relations.antihypertensive_response(
        systolic=180.0, diastolic=105.0, agent_count=3
    )
    titrated = relations.titrated_response(
        systolic=180.0, diastolic=105.0, agent_count=3
    )
    assert standard[0] >= relations.GOAL_SYSTOLIC, "precondition: still uncontrolled"
    assert titrated[0] < standard[0]
    assert titrated[1] < standard[1]


def test_an_untreated_patient_has_no_dose_to_escalate():
    assert relations.titrated_response(
        systolic=168.0, diastolic=102.0, agent_count=0
    ) == (168.0, 102.0)


def test_titration_is_bounded_by_the_doubling_ceiling():
    """Without a ceiling a severely hypertensive patient would titrate to the floor."""
    capped = relations.titrated_response(
        systolic=210.0, diastolic=120.0, agent_count=1, max_doublings=2
    )
    uncapped = relations.titrated_response(
        systolic=210.0, diastolic=120.0, agent_count=1, max_doublings=8
    )
    assert capped[0] > uncapped[0], "more doublings must lower it further"
    standard = relations.antihypertensive_response(
        systolic=210.0, diastolic=120.0, agent_count=1
    )
    expected = standard[0] - 2 * relations.LANCET_SYSTOLIC_PER_DOUBLING
    assert capped[0] == pytest.approx(expected)


def test_a_bigger_regimen_gains_more_from_each_doubling():
    """Doubling three agents' doses beats doubling one, per-step."""
    one = relations.titrated_response(systolic=200.0, diastolic=115.0, agent_count=1)
    three = relations.titrated_response(systolic=200.0, diastolic=115.0, agent_count=3)
    assert three[0] < one[0]
