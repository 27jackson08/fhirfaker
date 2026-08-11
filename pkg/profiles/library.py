"""The four v1 clinical profiles.

Marginals are clinically-informed estimates for a 45-65 adult population, chosen to
sit inside published reference and treatment-target ranges. They are NOT fitted to a
named cohort — calibrating against NHANES marginals is Phase 4 work, and the README
should say so rather than implying more provenance than exists.

What IS taken from the literature is the *dependence* structure: the HbA1c/glucose
correlation is derived from the ADAG R^2 rather than hand-tuned, and eGFR is computed
from creatinine by CKD-EPI 2021 rather than sampled.
"""

from __future__ import annotations

from pkg.correlation import relations
from pkg.correlation.distributions import (
    Marginal,
    calibrate_latent_correlation,
    correlation_from_r_squared,
    sd_from_regression_slope,
)
from pkg.correlation.engine import JointModel
from pkg.profiles.base import (
    EGFR_FROM_CREATININE,
    EGFR_FROM_TARGET,
    ClinicalProfile,
    ComorbidityRule,
    MedicationRule,
)
from pkg.terminology import codes

# --- shared marginals ------------------------------------------------------------
# Creatinine reference intervals are sex-specific; using one distribution for both
# would put half the population outside their own reference range.
CREATININE_BY_SEX = {
    "F": Marginal("creatinine", mean=0.75, sd=0.13, low=0.40, high=1.30),
    "M": Marginal("creatinine", mean=0.95, sd=0.15, low=0.50, high=1.50),
}
NORMOTENSIVE = (
    Marginal("systolic", mean=120.0, sd=11.0, low=85.0, high=160.0),
    Marginal("diastolic", mean=76.0, sd=8.0, low=50.0, high=100.0),
)
HYPERTENSIVE = (
    Marginal("systolic", mean=146.0, sd=12.0, low=125.0, high=200.0),
    Marginal("diastolic", mean=90.0, sd=8.0, low=70.0, high=120.0),
)
NORMOGLYCAEMIC = (
    Marginal("hba1c", mean=5.4, sd=0.30, low=4.0, high=6.4),
    Marginal("glucose", mean=92.0, sd=9.0, low=60.0, high=140.0),
)

# Systolic and diastolic move together; drawing them independently produces
# physiologically absurd pairs like 170/55.
BP_CORRELATION = 0.60


def _adag_calibrated_glucose(hba1c: Marginal) -> tuple[Marginal, float]:
    """Derive the glucose marginal and correlation from the published ADAG fit.

    For a simple linear regression, R^2 fixes rho and the slope then fixes the
    response SD:  slope = rho * (sd_glucose / sd_hba1c).  So both parameters follow
    from Nathan et al. 2008 rather than being chosen to look plausible.

    Reproducing R^2 = 0.84 (not 1.0) is the point: glucose must carry residual scatter
    around the ADAG line, or the joint distribution collapses onto it and is visibly
    synthetic.
    """
    rho = correlation_from_r_squared(relations.ADAG_R_SQUARED)
    # Realized, not nominal: HbA1c is truncated at the diagnostic threshold, which
    # shrinks its effective SD. Calibrating against the nominal SD inflated the
    # generated slope to 33.0 against ADAG's 28.7.
    realized_mean, realized_sd = hba1c.moments()
    mean = relations.estimated_average_glucose(realized_mean)
    sd = sd_from_regression_slope(
        slope=relations.ADAG_SLOPE, predictor_sd=realized_sd, rho=rho
    )
    # Glucose bounds sit ~4 SD out, so its own truncation is negligible and its
    # nominal parameters can be used as the realized targets directly.
    glucose = Marginal("glucose", mean=mean, sd=sd, low=70.0, high=400.0)

    # sqrt(R^2) is the correlation we want to *observe*. Truncation attenuates it, so
    # the latent copula parameter has to be solved for rather than used directly.
    latent_rho = calibrate_latent_correlation(
        hba1c, glucose, relations.ADAG_R_SQUARED
    )
    return glucose, latent_rho


def _joint(*marginals, correlations=()) -> JointModel:
    return JointModel(marginals=tuple(marginals), correlations=tuple(correlations))


def healthy(sex: str) -> ClinicalProfile:
    hba1c, glucose = NORMOGLYCAEMIC
    return ClinicalProfile(
        key="healthy",
        display="Healthy baseline",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *NORMOTENSIVE,
            correlations=[
                ("hba1c", "glucose", 0.55),
                ("systolic", "diastolic", BP_CORRELATION),
            ],
        ),
        egfr_mode=EGFR_FROM_CREATININE,
    )


def type2_diabetes(sex: str) -> ClinicalProfile:
    """Diagnosed, moderately controlled type 2 diabetes."""
    hba1c = Marginal("hba1c", mean=7.8, sd=0.90, low=6.5, high=12.0)
    glucose, rho = _adag_calibrated_glucose(hba1c)

    return ClinicalProfile(
        key="type2_diabetes",
        display="Type 2 diabetes (moderately controlled)",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *HYPERTENSIVE,
            correlations=[
                ("hba1c", "glucose", rho),
                ("systolic", "diastolic", BP_CORRELATION),
            ],
        ),
        primary_conditions=(codes.T2DM_NO_COMPLICATIONS,),
        # ~70% hypertension comorbidity is a realistic co-occurrence rate for this
        # population, not decoration.
        comorbidities=(ComorbidityRule(codes.ESSENTIAL_HYPERTENSION, 0.70),),
        medications=(
            MedicationRule(codes.METFORMIN_500),
            # A second agent follows from poor control rather than a bare coin flip.
            MedicationRule(
                codes.ATORVASTATIN_20,
                probability=0.15,
                requires=lambda a: a["hba1c"] > 8.5,
            ),
        ),
        egfr_mode=EGFR_FROM_CREATININE,
    )


def hypertension(sex: str) -> ClinicalProfile:
    hba1c, glucose = NORMOGLYCAEMIC
    return ClinicalProfile(
        key="hypertension",
        display="Essential hypertension",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *HYPERTENSIVE,
            correlations=[
                ("hba1c", "glucose", 0.55),
                ("systolic", "diastolic", BP_CORRELATION),
            ],
        ),
        primary_conditions=(codes.ESSENTIAL_HYPERTENSION,),
        medications=(MedicationRule(codes.LISINOPRIL_10),),
        egfr_mode=EGFR_FROM_CREATININE,
    )


def _ckd_stage_code(raw: dict[str, float]) -> tuple:
    """Pick the ICD-10-CM stage-3 code that matches the eGFR actually drawn."""
    stage = relations.ckd_stage_for(raw["egfr"])
    return ({"G3a": codes.CKD_STAGE_3A, "G3b": codes.CKD_STAGE_3B}.get(
        stage, codes.CKD_STAGE_3_UNSPECIFIED
    ),)


def ckd_stage3(sex: str) -> ClinicalProfile:
    """CKD stage 3.

    eGFR is sampled inside the stage-3 band and creatinine is *inverted* from it, so
    the constraint holds by construction instead of by rejection sampling.
    """
    hba1c, glucose = NORMOGLYCAEMIC
    return ClinicalProfile(
        key="ckd_stage3",
        display="Chronic kidney disease, stage 3",
        joint=_joint(
            Marginal("egfr_target", mean=45.0, sd=8.0, low=30.0, high=59.9),
            hba1c, glucose, *HYPERTENSIVE,
            correlations=[("systolic", "diastolic", BP_CORRELATION)],
        ),
        derived_conditions=_ckd_stage_code,
        comorbidities=(ComorbidityRule(codes.ESSENTIAL_HYPERTENSION, 0.80),),
        medications=(MedicationRule(codes.LISINOPRIL_10),),
        egfr_mode=EGFR_FROM_TARGET,
    )


PROFILES = {
    "healthy": healthy,
    "type2_diabetes": type2_diabetes,
    "hypertension": hypertension,
    "ckd_stage3": ckd_stage3,
}


def get_profile(key: str, sex: str) -> ClinicalProfile:
    if key not in PROFILES:
        raise ValueError(f"unknown profile {key!r}; available: {sorted(PROFILES)}")
    return PROFILES[key](sex)
