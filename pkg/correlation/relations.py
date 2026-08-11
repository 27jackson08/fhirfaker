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
}


def to_reported(value: float, analyte: str) -> Decimal:
    """Round a sampled value to the precision a laboratory would report."""
    quantum = Decimal(REPORTING_PRECISION[analyte])
    return Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP)
