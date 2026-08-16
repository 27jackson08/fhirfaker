"""The four v1 clinical profiles.

Marginals marked NHANES are derived from the NHANES 2017-March 2020 pre-pandemic
public files, restricted to ages 45-65 and stratified by sex and glycaemic status.
Centre and spread come from the median and IQR/1.349 rather than the mean and SD:
creatinine, triglycerides and HbA1c are all right-skewed (raw SD up to 3.8x the
robust one), so a symmetric truncated normal fitted to the raw moments would match
neither the centre nor the spread. Regenerate with `carebundle/calibration/nhanes.py`.

Two things are NOT NHANES-derived, deliberately:
  * Blood pressure marginals are clinical definitions. "Normotensive" and
    "hypertensive" are the populations the profiles mean, and NHANES is not
    stratified that way here.
  * The diabetic glucose marginal is ADAG-anchored, because reproducing that
    published relationship is the point. ADAG describes *average* glucose, which
    sits above a fasting measurement, so it is intentionally not matched to the
    NHANES serum glucose figure.

What comes from the literature is the *dependence* structure: the HbA1c/glucose
correlation is derived from the ADAG R^2 rather than hand-tuned, and eGFR, LDL and
BMI are computed from their inputs rather than sampled.
"""

from __future__ import annotations

import math

from carebundle.correlation import relations
from carebundle.correlation.distributions import (
    Marginal,
    calibrate_latent_correlation,
    correlation_from_r_squared,
    lognormal_from_quartiles,
    sd_from_regression_slope,
)
from carebundle.correlation.engine import JointModel
from carebundle.profiles.base import (
    EGFR_FROM_CREATININE,
    EGFR_FROM_TARGET,
    AllergyRule,
    ClinicalProfile,
    ComorbidityRule,
    MedicationRule,
)
from carebundle.terminology import codes
from carebundle.terminology.codes import Code

# --- shared marginals ------------------------------------------------------------
# Creatinine reference intervals are sex-specific; using one distribution for both
# would put half the population outside their own reference range.
# NHANES, nondiabetic 45-65.
CREATININE_BY_SEX = {
    "F": Marginal("creatinine", mean=0.73, sd=0.1483, low=0.51, high=1.134),
    "M": Marginal("creatinine", mean=0.97, sd=0.1853, low=0.65, high=1.528),
}
NORMOTENSIVE = (
    Marginal("systolic", mean=120.0, sd=11.0, low=85.0, high=160.0),
    Marginal("diastolic", mean=76.0, sd=8.0, low=50.0, high=100.0),
)
HYPERTENSIVE = (
    Marginal("systolic", mean=146.0, sd=12.0, low=125.0, high=200.0),
    Marginal("diastolic", mean=90.0, sd=8.0, low=70.0, high=120.0),
)
# NHANES 45-65, stratum `diagnosed` (DIQ010 == 1) — people a doctor has told they have
# diabetes, which is the population an `E11.9` code denotes. Distinct from the
# lab-defined `hba1c >= 6.5` stratum, which excludes the quarter of diagnosed diabetics
# whose treatment has brought them under the diagnostic threshold.
DIAGNOSED_DIABETIC_HBA1C_BY_SEX = {
    "F": lognormal_from_quartiles(
        "hba1c", median=7.1, q1=6.4, q3=8.3, low=5.4, high=12.5
    ),
    "M": lognormal_from_quartiles(
        "hba1c", median=7.3, q1=6.4, q3=8.7, low=5.3, high=12.47
    ),
}

# NHANES, nondiabetic 45-65, by sex. Lab-defined (`hba1c < 6.5`) rather than
# diagnosis-defined on purpose: undiagnosed diabetes is common, so "has not been told
# they have diabetes" carries a long tail of undiagnosed hyperglycaemia that a healthy
# baseline should not have.
NORMOGLYCAEMIC_BY_SEX = {
    "F": (
        Marginal("hba1c", mean=5.6, sd=0.2965, low=4.9, high=6.3),
        Marginal("glucose", mean=92.0, sd=8.895, low=76.0, high=123.0),
    ),
    "M": (
        Marginal("hba1c", mean=5.6, sd=0.3706, low=4.8, high=6.4),
        Marginal("glucose", mean=94.0, sd=9.637, low=75.0, high=126.8),
    ),
}

# Dependence structure, measured from NHANES 45-65 rather than estimated.
#
# These were hand-set until they were checked against the data, and all three were
# wrong: 0.60/-0.40/0.45 against measured values that also differ by sex. Height and
# weight was the instructive one — 0.45 is close to the *pooled* figure (0.41) and far
# from the within-sex one for women (0.30), because men are both taller and heavier so
# pooling the sexes manufactures correlation. These profiles are sex-stratified, so the
# within-sex figure is the only one they can legitimately use.
#
# Taken from the `all` stratum, which has the largest samples and spans the
# normotensive and hypertensive populations that different profiles draw from. Per-
# stratum values are in the committed targets file if a profile ever needs to refine
# this. A test asserts these match that file, so they cannot drift from the extraction.
BP_CORRELATION_BY_SEX = {"F": 0.6771, "M": 0.743}

# Triglycerides and HDL are inversely related — the classic dyslipidaemia pattern.
# Drawing them independently would produce high-TG/high-HDL patients that essentially
# do not exist. The sexes genuinely differ here (-0.43 against -0.30).
TG_HDL_CORRELATION_BY_SEX = {"F": -0.4332, "M": -0.2969}
HEIGHT_WEIGHT_CORRELATION_BY_SEX = {"F": 0.3036, "M": 0.446}

# NHANES 45-65: share of *diagnosed* diabetics who report having been told they have
# high blood pressure (BPQ020). Diagnosed on both sides, matching the `E11.9` and
# `I10` codes the profile emits rather than a measured-BP definition.
T2DM_HYPERTENSION_PREVALENCE_BY_SEX = {"F": 0.6997, "M": 0.6939}

# Upper bound sits below Friedewald's validity threshold (400 mg/dL), so the
# calculated LDL is always one a laboratory would actually report.
_TG_MAX = 380.0

# NHANES, nondiabetic 45-65. Triglyceride upper bounds are clamped below
# Friedewald's validity threshold so the calculated LDL is always reportable.
NORMOLIPIDAEMIC_BY_SEX = {
    "F": (
        Marginal("cholesterol_total", mean=198.0, sd=36.32, low=129.0, high=287.0),
        lognormal_from_quartiles("triglycerides", median=88.0, q1=64.0, q3=127.0,
                                 low=33.05, high=271.9),
    ),
    "M": (
        Marginal("cholesterol_total", mean=188.5, sd=38.55, low=117.0, high=273.0),
        lognormal_from_quartiles("triglycerides", median=94.0, q1=67.2, q3=138.8,
                                 low=34.0, high=332.3),
    ),
}
# NHANES, diabetic 45-65. The characteristic pattern shows up in the data itself:
# higher triglycerides and lower HDL at slightly *lower* total cholesterol.
DYSLIPIDAEMIC_BY_SEX = {
    "F": (
        Marginal("cholesterol_total", mean=190.0, sd=43.74, low=121.0, high=292.0),
        lognormal_from_quartiles("triglycerides", median=122.0, q1=86.5, q3=165.5,
                                 low=42.7, high=_TG_MAX),
    ),
    "M": (
        Marginal("cholesterol_total", mean=183.0, sd=44.48, low=112.0, high=296.0),
        lognormal_from_quartiles("triglycerides", median=132.0, q1=99.5, q3=195.5,
                                 low=45.0, high=_TG_MAX),
    ),
}
HDL_BY_SEX = {
    "F": Marginal("hdl", mean=57.0, sd=16.31, low=35.0, high=97.0),
    "M": Marginal("hdl", mean=47.0, sd=12.6, low=30.0, high=84.62),
}
HDL_LOW_BY_SEX = {
    "F": Marginal("hdl", mean=49.0, sd=11.12, low=32.0, high=83.0),
    "M": Marginal("hdl", mean=42.0, sd=10.38, low=28.0, high=76.0),
}
# Height is the same population either way; only weight shifts. Giving every profile
# one weight distribution left diabetic patients with the same BMI as everyone else,
# which contradicts the single strongest association in type 2 diabetes.
_HEIGHT_BY_SEX = {
    "F": Marginal("height_cm", mean=160.1, sd=7.042, low=146.5, high=173.9),
    "M": Marginal("height_cm", mean=173.6, sd=7.784, low=158.9, high=190.0),
}
# NHANES, nondiabetic 45-65. Materially heavier than the estimates these replaced:
# a US adult in this band really does sit near BMI 29, not 26.
ANTHROPOMETRICS_TYPICAL = {
    sex: (
        _HEIGHT_BY_SEX[sex],
        Marginal("weight_kg", mean=weight, sd=sd, low=low, high=high),
    )
    for sex, weight, sd, low, high in (
        ("F", 74.9, 19.64, 47.54, 133.7),
        ("M", 85.0, 18.9, 57.78, 142.3),
    )
}
# NHANES, diabetic 45-65 — no longer a tuned target. The data puts this group
# roughly 8 kg heavier than their non-diabetic peers.
ANTHROPOMETRICS_RAISED_BMI = {
    sex: (
        _HEIGHT_BY_SEX[sex],
        Marginal("weight_kg", mean=weight, sd=sd, low=low, high=high),
    )
    # NHANES 45-65, stratum `diagnosed` — the same population the profile's HbA1c now
    # comes from. Previously taken from the lab-defined `diabetic` stratum; the two
    # differ by under 1% on weight, so this is for consistency rather than accuracy.
    for sex, weight, sd, low, high in (
        ("F", 82.85, 21.83, 51.15, 131.8),
        ("M", 93.4, 25.76, 61.7, 157.4),
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
# NHANES, August 2021-August 2023 (NCHS Data Brief): 59.2% of US adults with
# hypertension are aware of it and 51.2% are taking medication to lower it, so
# 51.2/59.2 = 86.5% of *diagnosed* hypertensives are on treatment. Diagnosed-and-in-care
# is exactly the population these profiles represent — every one of them carries a
# coded hypertension diagnosis and an encounter — so that is the fraction to match.
NHANES_TREATED_FRACTION_OF_DIAGNOSED = 0.512 / 0.592

# Relative preference between classes: ACE inhibitor most common, beta blocker least,
# which is the usual first-line ordering. Only the *ratios* here are asserted; the
# absolute level is solved for below so the modelled treated fraction reproduces
# NHANES rather than whatever these numbers happened to multiply out to.
_ANTIHYPERTENSIVE_PREFERENCE: dict[Code, float] = {
    codes.LISINOPRIL_10: 0.45,
    codes.AMLODIPINE_5: 0.28,
    codes.HYDROCHLOROTHIAZIDE_25: 0.24,
    codes.LOSARTAN_50: 0.18,
    codes.CARVEDILOL_12_5: 0.11,
}


def _scaled_to_treated_fraction(
    preferences: dict[Code, float], target_treated: float
) -> dict[Code, float]:
    """Scale independent per-drug probabilities so P(at least one) hits a target.

    Raising each survival probability to a common exponent preserves the relative
    ordering between classes while moving only the overall treated fraction — one
    free parameter solved against one cited number, rather than five hand-tuned ones.

    Deriving it instead of writing the scaled values down keeps the cited target and
    the emitted probabilities from drifting apart, which is the failure mode Section 18
    records for every other number that was typed rather than computed.
    """
    untreated = math.prod(1.0 - p for p in preferences.values())
    exponent = math.log(1.0 - target_treated) / math.log(untreated)
    return {code: 1.0 - (1.0 - p) ** exponent for code, p in preferences.items()}


_SCALED_ANTIHYPERTENSIVES = _scaled_to_treated_fraction(
    _ANTIHYPERTENSIVE_PREFERENCE, NHANES_TREATED_FRACTION_OF_DIAGNOSED
)

ANTIHYPERTENSIVES = (
    *(MedicationRule(code, p) for code, p in _SCALED_ANTIHYPERTENSIVES.items()),
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


def _lipid_and_body_correlations(sex: str) -> list[tuple[str, str, float]]:
    return [
        ("triglycerides", "hdl", TG_HDL_CORRELATION_BY_SEX[sex]),
        ("height_cm", "weight_kg", HEIGHT_WEIGHT_CORRELATION_BY_SEX[sex]),
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
    hba1c, glucose = NORMOGLYCAEMIC_BY_SEX[sex]
    cholesterol, triglycerides = NORMOLIPIDAEMIC_BY_SEX[sex]
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
                ("systolic", "diastolic", BP_CORRELATION_BY_SEX[sex]),
                *_lipid_and_body_correlations(sex),
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
    """Diagnosed type 2 diabetes, across the range of control seen in practice."""
    # NHANES 45-65, stratum **diagnosed** (DIQ010 == 1), not the lab-defined
    # `hba1c >= 6.5` stratum this used to draw from. The profile emits `E11.9`, a
    # diagnosed code, and a quarter of diagnosed diabetics in this age band sit below
    # 6.5 because their treatment works. Calibrating to the lab threshold excluded all
    # of them and made the bound look empirically supported when it was really the
    # selection criterion reflected back.
    #
    # Log-normal, not normal: a long upper tail with the mass low, and
    # `fit_truncated_normal` refuses these targets outright rather than returning a bad
    # fit. The hand estimate this originally replaced had sd=0.90, barely half the real
    # spread, so every generated diabetic looked alike.
    hba1c = DIAGNOSED_DIABETIC_HBA1C_BY_SEX[sex]
    glucose, rho = _adag_calibrated_glucose(hba1c)
    cholesterol, triglycerides = DYSLIPIDAEMIC_BY_SEX[sex]
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
                ("systolic", "diastolic", BP_CORRELATION_BY_SEX[sex]),
                *_lipid_and_body_correlations(sex),
                *_routine_correlations(),
            ],
        ),
        # No fixed primary condition: the diabetes code depends on the draw.
        derived_conditions=_diabetes_conditions,
        # Measured, not assumed: NHANES 45-65, share of diagnosed diabetics who have
        # been told they have high blood pressure (BPQ020). The estimate this replaced
        # was 0.70, which turned out to be right — worth recording, because the three
        # correlations checked at the same time were all wrong and it would be easy to
        # conclude every hand-set number was.
        comorbidities=(
            ComorbidityRule(
                codes.ESSENTIAL_HYPERTENSION,
                T2DM_HYPERTENSION_PREVALENCE_BY_SEX[sex],
            ),
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
    hba1c, glucose = NORMOGLYCAEMIC_BY_SEX[sex]
    cholesterol, triglycerides = NORMOLIPIDAEMIC_BY_SEX[sex]
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
                ("systolic", "diastolic", BP_CORRELATION_BY_SEX[sex]),
                *_lipid_and_body_correlations(sex),
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
    hba1c, glucose = NORMOGLYCAEMIC_BY_SEX[sex]
    cholesterol, triglycerides = NORMOLIPIDAEMIC_BY_SEX[sex]
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
                ("systolic", "diastolic", BP_CORRELATION_BY_SEX[sex]),
                *_lipid_and_body_correlations(sex),
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
