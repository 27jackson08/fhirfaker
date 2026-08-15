"""Published clinical relationships, implemented verbatim and cited.

This module is the deterministic half of the correlation engine (build doc Section 8).
Values here are *computed*, never sampled: eGFR is a function of creatinine, age and
sex, so sampling both independently would let a bundle contradict itself. Sampling
belongs in `engine.py`.

Every function names its source. If a formula is not cited it does not belong here.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# --- ADAG ------------------------------------------------------------------------
# Nathan DM et al., "Translating the A1C Assay Into Estimated Average Glucose Values",
# Diabetes Care 31(8):1473-1478, 2008.  eAG (mg/dL) = 28.7 x A1C - 46.7,  R^2 = 0.84.
#
# The R^2 is as load-bearing as the coefficients. A generator that derives glucose
# deterministically from HbA1c reproduces the line with R^2 = 1.0, which is visibly
# artificial. `engine.py` uses ADAG_R_SQUARED to reproduce the residual scatter.
ADAG_SLOPE = 28.7
ADAG_INTERCEPT = -46.7
ADAG_R_SQUARED = 0.84


def estimated_average_glucose(hba1c_percent: float) -> float:
    """Mean glucose in mg/dL implied by an HbA1c, per ADAG.

    Note this is *average* glucose over ~3 months, not a fasting measurement.
    """
    return ADAG_SLOPE * hba1c_percent + ADAG_INTERCEPT


# --- Antihypertensive treatment response -----------------------------------------
# Law MR, Wald NJ, Morris JK, "Value of low dose combination treatment with blood
# pressure lowering drugs: analysis of 354 randomised trials", BMJ 2003;326:1427.
#
# One standard-dose agent lowers blood pressure by 9.1 systolic / 5.5 diastolic,
# averaged across thiazides, beta blockers, ACE inhibitors, ARBs and calcium channel
# blockers. A 2025 Lancet meta-analysis of 484 trials puts standard-dose monotherapy
# at 8.7 systolic (95% CI 8.2-9.2), which brackets the same figure.
#
# Two published properties of the effect are load-bearing here and both are implemented:
#
#   * The reduction is larger from a higher pre-treatment pressure — "for a 10 mm Hg
#     higher blood pressure the reduction was 1.0 mm Hg systolic and 1.1 mm Hg
#     diastolic greater". Law's trials standardise to a pre-treatment 154/97.
#   * Effects of drugs from different classes are additive, which is the evidence base
#     for combination therapy.
#
# Applying the per-drug effect *sequentially* rather than multiplying it by the agent
# count implements both at once: each additional agent acts on the pressure the
# previous one left behind, so the published baseline-dependence produces diminishing
# returns by construction instead of by a fudge factor.
LAW_SYSTOLIC_REDUCTION = 9.1
LAW_DIASTOLIC_REDUCTION = 5.5
LAW_REFERENCE_SYSTOLIC = 154.0
LAW_REFERENCE_DIASTOLIC = 97.0
LAW_SYSTOLIC_PER_MMHG = 0.10
LAW_DIASTOLIC_PER_MMHG = 0.11

# Treatment lowers pressure; it does not abolish it. Real treated patients are not
# found at 70/40, and without a floor a patient on four agents would be. These are
# physiological bounds of the same kind as the marginals' truncation limits, not a
# tuning knob — no benchmark in this project depends on their exact value.
TREATED_SYSTOLIC_FLOOR = 95.0
TREATED_DIASTOLIC_FLOOR = 55.0


def antihypertensive_response(
    *,
    systolic: float,
    diastolic: float,
    agent_count: int,
) -> tuple[float, float]:
    """Observed blood pressure after `agent_count` standard-dose agents, per Law 2003.

    `systolic`/`diastolic` are the *pre-treatment* pressure. Returns the pressure a
    clinic would actually record. With `agent_count == 0` the pressure is returned
    unchanged, which is what an untreated diagnosed hypertensive looks like.

    Raises on a negative agent count: that is a caller bug, and silently treating it
    as zero would hide a miscount behind plausible-looking output.
    """
    if agent_count < 0:
        raise ValueError(f"agent_count must be non-negative, got {agent_count}")

    for _ in range(agent_count):
        systolic -= LAW_SYSTOLIC_REDUCTION + LAW_SYSTOLIC_PER_MMHG * (
            systolic - LAW_REFERENCE_SYSTOLIC
        )
        diastolic -= LAW_DIASTOLIC_REDUCTION + LAW_DIASTOLIC_PER_MMHG * (
            diastolic - LAW_REFERENCE_DIASTOLIC
        )
        systolic = max(systolic, TREATED_SYSTOLIC_FLOOR)
        diastolic = max(diastolic, TREATED_DIASTOLIC_FLOOR)

    return systolic, diastolic


# --- Dose titration ----------------------------------------------------------------
# "Blood pressure-lowering efficacy of antihypertensive drugs and their combinations",
# Lancet 2025 (484 trials): each doubling of dose confers an additional 1.5 mm Hg
# systolic (95% CI 1.2-1.7) beyond the standard-dose effect.
#
# Why this exists. `antihypertensive_response` models a regimen at *standard* dose,
# which is what a newly-treated patient receives. It is not what a measure like HEDIS
# CBP scores: that takes the most recent reading of a year in which the clinician
# re-measures and escalates until the patient reaches goal. An established patient's
# recorded pressure reflects a titrated regimen, not a starting one.
#
# Escalation is conditional on being above goal, which is what titration *is*. A
# patient already at target is not escalated, so this cannot push a controlled
# population further down and inflate a control rate from the wrong end.
LANCET_SYSTOLIC_PER_DOUBLING = 1.5
# Law's standard-dose systolic:diastolic ratio, applied to keep the doubling effect
# internally consistent rather than introducing a second unsourced constant.
_SYSTOLIC_TO_DIASTOLIC = LAW_DIASTOLIC_REDUCTION / LAW_SYSTOLIC_REDUCTION

# Standard dose to twice to four times: two doublings is the practical ceiling for most
# antihypertensives before a further agent is preferred to a further dose. This bounds
# titration clinically; it is not fitted to any benchmark.
MAX_DOSE_DOUBLINGS_PER_AGENT = 2

GOAL_SYSTOLIC = 140.0
GOAL_DIASTOLIC = 90.0


def titrated_response(
    *,
    systolic: float,
    diastolic: float,
    agent_count: int,
    max_doublings: int = MAX_DOSE_DOUBLINGS_PER_AGENT,
) -> tuple[float, float]:
    """Blood pressure after a regimen is escalated toward goal, per Lancet 2025.

    Applies `antihypertensive_response` first (standard dose), then doubles doses while
    the patient remains above 140/90 and doublings remain. An untreated patient
    (`agent_count == 0`) has no dose to escalate and is returned unchanged.
    """
    systolic, diastolic = antihypertensive_response(
        systolic=systolic, diastolic=diastolic, agent_count=agent_count
    )
    if agent_count == 0:
        return systolic, diastolic

    for _ in range(max_doublings):
        if systolic < GOAL_SYSTOLIC and diastolic < GOAL_DIASTOLIC:
            break
        systolic -= LANCET_SYSTOLIC_PER_DOUBLING * agent_count
        diastolic -= LANCET_SYSTOLIC_PER_DOUBLING * _SYSTOLIC_TO_DIASTOLIC * agent_count
        systolic = max(systolic, TREATED_SYSTOLIC_FLOOR)
        diastolic = max(diastolic, TREATED_DIASTOLIC_FLOOR)

    return systolic, diastolic


# --- CKD-EPI 2021 (race-free) ----------------------------------------------------
# Inker LA et al., NEJM 2021; endorsed by NKF/ASN.
#   eGFR = 142 x min(Scr/K, 1)^a x max(Scr/K, 1)^-1.200 x 0.9938^age x 1.012 [female]
CKD_EPI_COEFFICIENT = 142.0
CKD_EPI_AGE_BASE = 0.9938
CKD_EPI_FEMALE_FACTOR = 1.012
CKD_EPI_UPPER_EXPONENT = -1.200
_KAPPA = {"F": 0.7, "M": 0.9}
_ALPHA = {"F": -0.302, "M": -0.241}


def _ckd_epi_constants(sex: str) -> tuple[float, float, float]:
    if sex not in _KAPPA:
        raise ValueError(f"sex must be 'F' or 'M', got {sex!r}")
    female_factor = CKD_EPI_FEMALE_FACTOR if sex == "F" else 1.0
    return _KAPPA[sex], _ALPHA[sex], female_factor


def ckd_epi_2021_egfr(*, creatinine_mg_dl: float, age_years: float, sex: str) -> float:
    """eGFR in mL/min/1.73m^2 from serum creatinine (CKD-EPI 2021, race-free)."""
    if creatinine_mg_dl <= 0:
        raise ValueError(f"creatinine must be positive, got {creatinine_mg_dl}")
    kappa, alpha, female_factor = _ckd_epi_constants(sex)
    ratio = creatinine_mg_dl / kappa
    return (
        CKD_EPI_COEFFICIENT
        * min(ratio, 1.0) ** alpha
        * max(ratio, 1.0) ** CKD_EPI_UPPER_EXPONENT
        * CKD_EPI_AGE_BASE**age_years
        * female_factor
    )


def ckd_epi_2021_creatinine(*, egfr: float, age_years: float, sex: str) -> float:
    """Invert CKD-EPI 2021: the creatinine that yields a target eGFR.

    Used by the CKD profile. Sampling a target eGFR and inverting guarantees the
    stage constraint holds exactly; sampling creatinine and hoping eGFR lands in range
    would need rejection sampling and could still drift.

    The equation is piecewise at Scr = K, so the branch is selected by comparing the
    target against the eGFR at that hinge.
    """
    if egfr <= 0:
        raise ValueError(f"egfr must be positive, got {egfr}")
    kappa, alpha, female_factor = _ckd_epi_constants(sex)
    base = CKD_EPI_COEFFICIENT * CKD_EPI_AGE_BASE**age_years * female_factor

    # eGFR when Scr == kappa (both min and max terms equal 1).
    hinge = base
    exponent = CKD_EPI_UPPER_EXPONENT if egfr < hinge else alpha
    return kappa * (egfr / base) ** (1.0 / exponent)


# --- Friedewald ------------------------------------------------------------------
# Friedewald WT, Levy RI, Fredrickson DS, Clin Chem 18(6):499-502, 1972.
#   LDL-C = TC - HDL-C - (TG / 5)      [mg/dL]
#
# Another deterministic identity, not a correlation: a lipid panel that samples LDL
# independently of its three inputs can contradict itself inside one bundle.
FRIEDEWALD_TRIGLYCERIDE_DIVISOR = 5.0

# The equation is not valid at high triglycerides — the VLDL-cholesterol estimate
# TG/5 breaks down. Labs suppress the calculated LDL above this threshold.
FRIEDEWALD_MAX_TRIGLYCERIDES = 400.0


def friedewald_ldl(
    *, total_cholesterol: float, hdl: float, triglycerides: float
) -> float:
    """Calculated LDL cholesterol in mg/dL (Friedewald 1972).

    Raises above the validity threshold rather than returning a number a laboratory
    would refuse to report. Profiles bound their triglyceride marginal below it, so
    the truncation bound enforces the formula's domain by construction.
    """
    if triglycerides >= FRIEDEWALD_MAX_TRIGLYCERIDES:
        raise ValueError(
            f"Friedewald is not valid at triglycerides >= "
            f"{FRIEDEWALD_MAX_TRIGLYCERIDES} mg/dL (got {triglycerides}); a laboratory "
            "would suppress the calculated LDL rather than report one."
        )
    return total_cholesterol - hdl - (triglycerides / FRIEDEWALD_TRIGLYCERIDE_DIVISOR)


# --- Body mass index -------------------------------------------------------------
# WHO definition. BMI = kg / m^2; obesity is BMI >= 30.
OBESITY_BMI_THRESHOLD = 30.0
OVERWEIGHT_BMI_THRESHOLD = 25.0


def body_mass_index(*, weight_kg: float, height_cm: float) -> float:
    if height_cm <= 0:
        raise ValueError(f"height must be positive, got {height_cm}")
    return weight_kg / (height_cm / 100.0) ** 2


# --- CKD staging -----------------------------------------------------------------
# KDIGO 2012 GFR categories, as half-open intervals [low, high).
#
# Written as inclusive ranges (…, 44.9) and (45.0, …) this leaves a gap: a continuous
# eGFR of 44.988 belongs to no stage. Boundaries must tile the line exactly.
CKD_STAGE_LOWER_BOUNDS = (
    ("G1", 90.0),
    ("G2", 60.0),
    ("G3a", 45.0),
    ("G3b", 30.0),
    ("G4", 15.0),
    ("G5", 0.0),
)


def ckd_stage_for(egfr: float) -> str:
    """KDIGO GFR category for an eGFR, in mL/min/1.73m^2."""
    if egfr < 0:
        raise ValueError(f"egfr cannot be negative, got {egfr}")
    for stage, lower in CKD_STAGE_LOWER_BOUNDS:
        if egfr >= lower:
            return stage
    raise ValueError(f"no CKD stage covers eGFR {egfr}")


# --- rounding --------------------------------------------------------------------
# Labs report to fixed precision. Rounding at the edge keeps FHIR decimals honest
# about significant figures rather than emitting float noise.
REPORTING_PRECISION = {
    "hba1c": "0.1",
    "glucose": "1",
    "creatinine": "0.01",
    "egfr": "1",
    "blood_pressure": "1",
    "cholesterol_total": "1",
    "hdl": "1",
    "ldl": "1",
    "triglycerides": "1",
    "height_cm": "1",
    "weight_kg": "0.1",
    "bmi": "0.1",
    "sodium": "1", "potassium": "0.1", "chloride": "1", "co2": "1",
    "calcium": "0.1", "albumin": "0.1", "bun": "1",
    "alt": "1", "ast": "1", "alkaline_phosphatase": "1", "bilirubin_total": "0.1",
    "hemoglobin": "0.1", "hematocrit": "0.1", "rbc": "0.01",
    "wbc": "0.1", "platelets": "1",
    "heart_rate": "1", "respiratory_rate": "1",
    "body_temperature": "0.1", "oxygen_saturation": "1",
    "uacr": "1", "microalbumin_urine": "1",
}


def to_reported(value: float, analyte: str) -> Decimal:
    """Round a sampled value to the precision a laboratory would report."""
    quantum = Decimal(REPORTING_PRECISION[analyte])
    return Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP)
