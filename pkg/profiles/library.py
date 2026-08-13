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
    AllergyRule,
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

# Triglycerides and HDL are inversely related — the classic dyslipidaemia pattern.
# Drawing them independently would produce high-TG/high-HDL patients that essentially
# do not exist.
TG_HDL_CORRELATION = -0.40
HEIGHT_WEIGHT_CORRELATION = 0.45

# Upper bound sits below Friedewald's validity threshold (400 mg/dL), so the
# calculated LDL is always one a laboratory would actually report.
_TG_MAX = 380.0

NORMOLIPIDAEMIC = (
    Marginal("cholesterol_total", mean=190.0, sd=32.0, low=110.0, high=310.0),
    Marginal("triglycerides", mean=115.0, sd=45.0, low=40.0, high=_TG_MAX),
)
# Diabetic dyslipidaemia: higher triglycerides, lower HDL, at similar total
# cholesterol. This is the characteristic pattern, not a generic "worse lipids".
DYSLIPIDAEMIC = (
    Marginal("cholesterol_total", mean=200.0, sd=35.0, low=110.0, high=330.0),
    Marginal("triglycerides", mean=185.0, sd=70.0, low=50.0, high=_TG_MAX),
)
HDL_BY_SEX = {
    "F": Marginal("hdl", mean=55.0, sd=13.0, low=22.0, high=110.0),
    "M": Marginal("hdl", mean=46.0, sd=12.0, low=20.0, high=100.0),
}
HDL_LOW_BY_SEX = {
    "F": Marginal("hdl", mean=46.0, sd=11.0, low=20.0, high=95.0),
    "M": Marginal("hdl", mean=39.0, sd=10.0, low=18.0, high=85.0),
}
# Height is the same population either way; only weight shifts. Giving every profile
# one weight distribution left diabetic patients with the same BMI as everyone else,
# which contradicts the single strongest association in type 2 diabetes.
_HEIGHT_BY_SEX = {
    "F": Marginal("height_cm", mean=163.0, sd=6.8, low=140.0, high=188.0),
    "M": Marginal("height_cm", mean=176.0, sd=7.2, low=150.0, high=200.0),
}
ANTHROPOMETRICS_TYPICAL = {
    sex: (
        _HEIGHT_BY_SEX[sex],
        Marginal("weight_kg", mean=weight, sd=sd, low=low, high=high),
    )
    for sex, weight, sd, low, high in (
        ("F", 70.0, 14.0, 40.0, 135.0),
        ("M", 83.0, 15.0, 48.0, 150.0),
    )
}
# Type 2 diabetes carries a markedly higher BMI distribution than the typical adult.
# Weights are set so the generated obesity rate lands near 60%, the middle of the
# 55-65% range reported for US type 2 diabetes populations — chosen from the target
# rate rather than tuned until the number looked acceptable.
ANTHROPOMETRICS_RAISED_BMI = {
    sex: (
        _HEIGHT_BY_SEX[sex],
        Marginal("weight_kg", mean=weight, sd=sd, low=low, high=high),
    )
    for sex, weight, sd, low, high in (
        ("F", 84.0, 18.0, 45.0, 170.0),
        ("M", 97.0, 19.0, 52.0, 185.0),
    )
}


# Reported drug-allergy prevalence in US adults. Penicillin is the dominant reported
# allergy at roughly 10%, most of which is not true IgE-mediated allergy on testing —
# but a record generator models what is *recorded*, not what is confirmed.
COMMON_DRUG_ALLERGIES = (
    AllergyRule(codes.ALLERGEN_PENICILLIN_G, 0.10),
    AllergyRule(codes.ALLERGEN_SULFAMETHOXAZOLE, 0.03),
    AllergyRule(codes.ALLERGEN_CODEINE, 0.02),
    AllergyRule(codes.ALLERGEN_IBUPROFEN, 0.01),
    AllergyRule(codes.ALLERGEN_AMOXICILLIN, 0.02),
    AllergyRule(codes.ALLERGEN_ASPIRIN, 0.01),
)


# --- routine panels ---------------------------------------------------------------
# A real ambulatory visit draws a comprehensive metabolic panel and a CBC alongside
# whatever the presenting problem needs. Centred on standard adult reference
# intervals, bounded at the limits a laboratory would flag rather than reject.
COMPREHENSIVE_METABOLIC = (
    Marginal("sodium", mean=140.0, sd=2.4, low=128.0, high=150.0),
    Marginal("potassium", mean=4.2, sd=0.34, low=3.0, high=5.8),
    Marginal("chloride", mean=102.0, sd=2.9, low=90.0, high=114.0),
    Marginal("co2", mean=25.0, sd=2.4, low=15.0, high=34.0),
    Marginal("calcium", mean=9.5, sd=0.40, low=7.5, high=11.5),
    Marginal("albumin", mean=4.2, sd=0.34, low=2.5, high=5.4),
    Marginal("bun", mean=15.0, sd=4.0, low=4.0, high=45.0),
    Marginal("alt", mean=25.0, sd=11.0, low=5.0, high=90.0),
    Marginal("ast", mean=24.0, sd=9.0, low=8.0, high=80.0),
    Marginal("alkaline_phosphatase", mean=76.0, sd=21.0, low=25.0, high=180.0),
    Marginal("bilirubin_total", mean=0.7, sd=0.28, low=0.1, high=2.0),
)
CBC_BY_SEX = {
    "F": (
        Marginal("hemoglobin", mean=13.6, sd=1.05, low=8.0, high=17.0),
        Marginal("hematocrit", mean=40.5, sd=3.1, low=25.0, high=51.0),
        Marginal("rbc", mean=4.55, sd=0.38, low=3.0, high=6.0),
    ),
    "M": (
        Marginal("hemoglobin", mean=15.1, sd=1.15, low=9.0, high=19.0),
        Marginal("hematocrit", mean=44.8, sd=3.4, low=28.0, high=56.0),
        Marginal("rbc", mean=5.05, sd=0.42, low=3.4, high=6.6),
    ),
}
CBC_SHARED = (
    Marginal("wbc", mean=7.1, sd=1.8, low=2.5, high=16.0),
    Marginal("platelets", mean=262.0, sd=58.0, low=90.0, high=480.0),
)
ROUTINE_VITALS = (
    Marginal("heart_rate", mean=74.0, sd=10.0, low=45.0, high=120.0),
    Marginal("respiratory_rate", mean=16.0, sd=2.3, low=10.0, high=26.0),
    Marginal("body_temperature", mean=36.8, sd=0.30, low=35.5, high=38.5),
    Marginal("oxygen_saturation", mean=97.2, sd=1.4, low=88.0, high=100.0),
)

# Haemoglobin, haematocrit and red cell count measure the same underlying red cell
# mass — the clinical rule of thumb is Hct ~ 3 x Hgb. Sampling them independently
# produces a CBC no haematology analyser could ever emit.
RED_CELL_CORRELATIONS = (
    ("hemoglobin", "hematocrit", 0.93),
    ("hemoglobin", "rbc", 0.86),
    ("hematocrit", "rbc", 0.87),
)
# Urea nitrogen tracks renal function, so it must move with creatinine.
BUN_CREATININE_CORRELATION = 0.55
# Sodium and chloride move together; the aminotransferases share a liver signal.
ELECTROLYTE_CORRELATIONS = (
    ("sodium", "chloride", 0.65),
    ("alt", "ast", 0.72),
)


def _routine_marginals(sex: str) -> tuple:
    return (*COMPREHENSIVE_METABOLIC, *CBC_BY_SEX[sex], *CBC_SHARED, *ROUTINE_VITALS)


def _routine_correlations(*, has_creatinine: bool = True) -> list[tuple[str, str, float]]:
    """The CKD profile derives creatinine from a target eGFR rather than sampling it,
    so the BUN/creatinine correlation has nothing to attach to there."""
    pairs = [*RED_CELL_CORRELATIONS, *ELECTROLYTE_CORRELATIONS]
    if has_creatinine:
        pairs.append(("bun", "creatinine", BUN_CREATININE_CORRELATION))
    return pairs


# Background chronic conditions and their treatments, common in any 45-65 population
# and independent of the profile's presenting problem. Each drug is gated on its
# diagnosis so a prescription never appears without a reason on the problem list.
BACKGROUND_COMORBIDITIES = (
    ComorbidityRule(codes.HYPOTHYROIDISM, 0.09),
    ComorbidityRule(codes.ATHEROSCLEROTIC_HEART_DISEASE, 0.07),
)
BACKGROUND_MEDICATIONS = (
    MedicationRule(codes.LEVOTHYROXINE_50, 0.85, requires_condition="E03.9"),
    MedicationRule(codes.ASPIRIN_81, 0.70, requires_condition="I25.10"),
    MedicationRule(codes.SIMVASTATIN_20, 0.35, requires_condition="I25.10"),
    MedicationRule(codes.OMEPRAZOLE_20, 0.10),
    MedicationRule(codes.SERTRALINE_50, 0.07),
    MedicationRule(codes.GABAPENTIN_300, 0.05),
)
# Combination therapy is the norm in hypertension, so these are independent draws
# rather than a single pick — most treated patients are on two or more agents.
ANTIHYPERTENSIVES = (
    MedicationRule(codes.LISINOPRIL_10, 0.45),
    MedicationRule(codes.AMLODIPINE_5, 0.28),
    MedicationRule(codes.HYDROCHLOROTHIAZIDE_25, 0.24),
    MedicationRule(codes.LOSARTAN_50, 0.18),
    MedicationRule(codes.CARVEDILOL_12_5, 0.11),
    # Higher doses follow poor control, not chance.
    MedicationRule(
        codes.LISINOPRIL_20, 0.30, requires=lambda a: a.get("systolic", 0.0) >= 160.0
    ),
    MedicationRule(
        codes.AMLODIPINE_10, 0.25, requires=lambda a: a.get("systolic", 0.0) >= 165.0
    ),
)
# Albuminuria is the other axis of KDIGO staging and the earliest marker of diabetic
# kidney disease, so it belongs wherever the kidney is the point.
ALBUMINURIA = (
    Marginal("uacr", mean=45.0, sd=60.0, low=2.0, high=900.0),
    Marginal("microalbumin_urine", mean=30.0, sd=35.0, low=1.0, high=400.0),
)
ALBUMINURIA_NORMAL = (
    Marginal("uacr", mean=12.0, sd=9.0, low=2.0, high=120.0),
    Marginal("microalbumin_urine", mean=9.0, sd=7.0, low=1.0, high=90.0),
)


def _lipid_and_body_correlations() -> list[tuple[str, str, float]]:
    return [
        ("triglycerides", "hdl", TG_HDL_CORRELATION),
        ("height_cm", "weight_kg", HEIGHT_WEIGHT_CORRELATION),
    ]


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


def _metabolic_conditions(raw: dict[str, float]) -> tuple:
    """Conditions implied by the values actually drawn.

    Coding that follows from the labs rather than sitting beside them. A bundle whose
    LDL is 190 mg/dL but whose problem list is silent is not coherent data.
    """
    found = []
    if raw.get("ldl", 0.0) >= 160.0:
        found.append(codes.PURE_HYPERCHOLESTEROLEMIA)
    elif raw.get("triglycerides", 0.0) >= 200.0 or raw.get("ldl", 0.0) >= 130.0:
        found.append(codes.HYPERLIPIDEMIA)
    if raw.get("bmi", 0.0) >= relations.OBESITY_BMI_THRESHOLD:
        found.append(codes.OBESITY)
    return tuple(found)


def healthy(sex: str) -> ClinicalProfile:
    hba1c, glucose = NORMOGLYCAEMIC
    cholesterol, triglycerides = NORMOLIPIDAEMIC
    height, weight = ANTHROPOMETRICS_TYPICAL[sex]
    return ClinicalProfile(
        key="healthy",
        display="Healthy baseline",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *NORMOTENSIVE,
            cholesterol, triglycerides, HDL_BY_SEX[sex], height, weight,
            *ALBUMINURIA_NORMAL, *_routine_marginals(sex),
            correlations=[
                ("hba1c", "glucose", 0.55),
                ("systolic", "diastolic", BP_CORRELATION),
                *_lipid_and_body_correlations(),
                *_routine_correlations(),
            ],
        ),
        derived_conditions=_metabolic_conditions,
        allergies=COMMON_DRUG_ALLERGIES,
        egfr_mode=EGFR_FROM_CREATININE,
    )


HYPERGLYCEMIA_HBA1C_THRESHOLD = 9.0
# KDIGO A3 (severely increased albuminuria) begins at 300 mg/g.
ALBUMINURIA_UACR_THRESHOLD = 300.0
CKD_EGFR_THRESHOLD = 60.0

# KDIGO stage -> ICD-10-CM code.
_STAGE_TO_ICD10 = {
    "G1": codes.CKD_STAGE_1,
    "G2": codes.CKD_STAGE_2,
    "G3a": codes.CKD_STAGE_3A,
    "G3b": codes.CKD_STAGE_3B,
    "G4": codes.CKD_STAGE_4,
    "G5": codes.CKD_STAGE_5,
}


def _ckd_code_for(egfr: float):
    return _STAGE_TO_ICD10.get(relations.ckd_stage_for(egfr), codes.CKD_UNSPECIFIED)


def _diabetes_conditions(raw: dict[str, float]) -> tuple:
    """Pick the diabetes code the drawn labs actually support.

    ICD-10-CM distinguishes diabetes *with* named complications from diabetes without
    them. Emitting E11.9 "without complications" next to an eGFR of 45 is a
    contradiction inside one bundle — the kind a reviewer spots immediately — so the
    code is selected from the values rather than fixed by the profile.
    """
    egfr = raw.get("egfr", float("inf"))
    hba1c = raw.get("hba1c", 0.0)

    if egfr < CKD_EGFR_THRESHOLD:
        found = [codes.T2DM_WITH_CKD, _ckd_code_for(egfr)]
    elif raw.get("uacr", 0.0) >= ALBUMINURIA_UACR_THRESHOLD:
        # Raised albumin:creatinine with preserved eGFR is diabetic nephropathy
        # before it is diabetic CKD — the earliest stage the coding distinguishes.
        found = [codes.T2DM_WITH_NEPHROPATHY]
    elif hba1c >= HYPERGLYCEMIA_HBA1C_THRESHOLD:
        found = [codes.T2DM_WITH_HYPERGLYCEMIA]
    else:
        found = [codes.T2DM_NO_COMPLICATIONS]

    return (*found, *_metabolic_conditions(raw))


def type2_diabetes(sex: str) -> ClinicalProfile:
    """Diagnosed, moderately controlled type 2 diabetes."""
    hba1c = Marginal("hba1c", mean=7.8, sd=0.90, low=6.5, high=12.0)
    glucose, rho = _adag_calibrated_glucose(hba1c)
    cholesterol, triglycerides = DYSLIPIDAEMIC
    height, weight = ANTHROPOMETRICS_RAISED_BMI[sex]

    return ClinicalProfile(
        key="type2_diabetes",
        display="Type 2 diabetes (moderately controlled)",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *HYPERTENSIVE,
            cholesterol, triglycerides, HDL_LOW_BY_SEX[sex], height, weight,
            *ALBUMINURIA, *_routine_marginals(sex),
            correlations=[
                ("hba1c", "glucose", rho),
                ("systolic", "diastolic", BP_CORRELATION),
                *_lipid_and_body_correlations(),
                *_routine_correlations(),
            ],
        ),
        # No fixed primary condition: the diabetes code depends on the draw.
        derived_conditions=_diabetes_conditions,
        # ~70% hypertension comorbidity is a realistic co-occurrence rate for this
        # population, not decoration.
        comorbidities=(
            ComorbidityRule(codes.ESSENTIAL_HYPERTENSION, 0.70),
            *BACKGROUND_COMORBIDITIES,
        ),
        medications=(
            MedicationRule(codes.METFORMIN_500, 0.60),
            # Escalation follows poor control rather than a bare coin flip.
            MedicationRule(
                codes.METFORMIN_1000, 0.35, requires=lambda a: a["hba1c"] > 8.5
            ),
            MedicationRule(
                codes.GLIPIZIDE_5, 0.18, requires=lambda a: a["hba1c"] > 8.0
            ),
            MedicationRule(
                codes.SITAGLIPTIN_100, 0.15, requires=lambda a: a["hba1c"] > 8.0
            ),
            MedicationRule(
                codes.GLIMEPIRIDE_2, 0.10, requires=lambda a: a["hba1c"] > 9.0
            ),
            MedicationRule(codes.EMPAGLIFLOZIN_10, 0.14),
            # Diabetes lowers the statin threshold; guidelines treat it as a
            # cardiovascular risk equivalent.
            MedicationRule(
                codes.ATORVASTATIN_20, 0.55, requires=lambda a: a.get("ldl", 0.0) >= 100.0
            ),
            MedicationRule(
                codes.ATORVASTATIN_40, 0.30, requires=lambda a: a.get("ldl", 0.0) >= 160.0
            ),
            *ANTIHYPERTENSIVES,
            *BACKGROUND_MEDICATIONS,
        ),
        allergies=COMMON_DRUG_ALLERGIES,
        egfr_mode=EGFR_FROM_CREATININE,
    )


def hypertension(sex: str) -> ClinicalProfile:
    hba1c, glucose = NORMOGLYCAEMIC
    cholesterol, triglycerides = NORMOLIPIDAEMIC
    height, weight = ANTHROPOMETRICS_TYPICAL[sex]
    return ClinicalProfile(
        key="hypertension",
        display="Essential hypertension",
        joint=_joint(
            hba1c, glucose, CREATININE_BY_SEX[sex], *HYPERTENSIVE,
            cholesterol, triglycerides, HDL_BY_SEX[sex], height, weight,
            *ALBUMINURIA_NORMAL, *_routine_marginals(sex),
            correlations=[
                ("hba1c", "glucose", 0.55),
                ("systolic", "diastolic", BP_CORRELATION),
                *_lipid_and_body_correlations(),
                *_routine_correlations(),
            ],
        ),
        primary_conditions=(codes.ESSENTIAL_HYPERTENSION,),
        derived_conditions=_metabolic_conditions,
        medications=(
            *ANTIHYPERTENSIVES,
            MedicationRule(
                codes.ATORVASTATIN_20, 0.60, requires=lambda a: a.get("ldl", 0.0) >= 160.0
            ),
            MedicationRule(
                codes.ROSUVASTATIN_10, 0.25, requires=lambda a: a.get("ldl", 0.0) >= 190.0
            ),
            *BACKGROUND_MEDICATIONS,
        ),
        comorbidities=BACKGROUND_COMORBIDITIES,
        allergies=COMMON_DRUG_ALLERGIES,
        egfr_mode=EGFR_FROM_CREATININE,
    )


def _ckd_conditions(raw: dict[str, float]) -> tuple:
    """The ICD-10-CM stage code matching the eGFR actually drawn, plus metabolics."""
    return (_ckd_code_for(raw["egfr"]), *_metabolic_conditions(raw))


def ckd_stage3(sex: str) -> ClinicalProfile:
    """CKD stage 3.

    eGFR is sampled inside the stage-3 band and creatinine is *inverted* from it, so
    the constraint holds by construction instead of by rejection sampling.
    """
    hba1c, glucose = NORMOGLYCAEMIC
    cholesterol, triglycerides = NORMOLIPIDAEMIC
    height, weight = ANTHROPOMETRICS_TYPICAL[sex]
    return ClinicalProfile(
        key="ckd_stage3",
        display="Chronic kidney disease, stage 3",
        joint=_joint(
            Marginal("egfr_target", mean=45.0, sd=8.0, low=30.0, high=59.9),
            hba1c, glucose, *HYPERTENSIVE,
            cholesterol, triglycerides, HDL_BY_SEX[sex], height, weight,
            *ALBUMINURIA, *_routine_marginals(sex),
            correlations=[
                ("systolic", "diastolic", BP_CORRELATION),
                *_lipid_and_body_correlations(),
                *_routine_correlations(has_creatinine=False),
            ],
        ),
        derived_conditions=_ckd_conditions,
        comorbidities=(
            ComorbidityRule(codes.ESSENTIAL_HYPERTENSION, 0.80),
            *BACKGROUND_COMORBIDITIES,
        ),
        medications=(
            *ANTIHYPERTENSIVES,
            MedicationRule(codes.FUROSEMIDE_40, 0.30),
            MedicationRule(
                codes.ATORVASTATIN_20, 0.45, requires=lambda a: a.get("ldl", 0.0) >= 100.0
            ),
            *BACKGROUND_MEDICATIONS,
        ),
        allergies=COMMON_DRUG_ALLERGIES,
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
