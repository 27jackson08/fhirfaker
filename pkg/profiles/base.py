"""Clinical profile definition and drawing.

A profile declares what a patient population looks like: the joint distribution over
analytes, which conditions attach and how often, and which medications follow. Drawing
is a single pass so that conditions, values and prescriptions all come from one
coherent draw rather than being decided independently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np

from pkg.correlation import relations
from pkg.correlation.engine import JointModel
from pkg.terminology.codes import Code

# How eGFR is obtained. Both paths end with eGFR consistent with creatinine; they
# differ in which one is sampled and which is computed.
EGFR_FROM_CREATININE = "from_creatinine"  # sample creatinine, compute eGFR
EGFR_FROM_TARGET = "from_target"  # sample target eGFR, invert to creatinine


@dataclass(frozen=True)
class ComorbidityRule:
    """A condition that attaches with a given prevalence."""

    code: Code
    probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"{self.code.display}: probability out of range")


@dataclass(frozen=True)
class MedicationRule:
    """A prescription, optionally gated on the analytes actually drawn.

    `requires` is what makes prescribing responsive to the patient rather than
    decorative: a second agent should follow from poor control, not a coin flip.
    """

    code: Code
    probability: float = 1.0
    requires: Callable[[dict[str, float]], bool] | None = None

    def applies(self, analytes: dict[str, float], rng: np.random.Generator) -> bool:
        if self.requires is not None and not self.requires(analytes):
            return False
        return bool(rng.random() < self.probability)


@dataclass(frozen=True)
class ProfileDraw:
    """One patient's worth of jointly-drawn clinical facts."""

    analytes: dict[str, Decimal]
    raw: dict[str, float]
    conditions: tuple[Code, ...]
    medications: tuple[Code, ...]


@dataclass(frozen=True)
class ClinicalProfile:
    key: str
    display: str
    joint: JointModel
    primary_conditions: tuple[Code, ...] = ()
    comorbidities: tuple[ComorbidityRule, ...] = ()
    medications: tuple[MedicationRule, ...] = ()
    egfr_mode: str = EGFR_FROM_CREATININE
    reported_precision: dict[str, str] = field(default_factory=dict)
    # Conditions whose *code* depends on the values drawn — e.g. CKD stage 3a vs 3b
    # is determined by eGFR, so emitting a fixed code would let the coded diagnosis
    # disagree with the lab result in the same bundle.
    derived_conditions: Callable[[dict[str, float]], tuple[Code, ...]] | None = None


def draw(
    profile: ClinicalProfile,
    *,
    rng: np.random.Generator,
    age_years: float,
    sex: str,
) -> ProfileDraw:
    """Draw one patient from a profile.

    Order matters: analytes are sampled jointly first, then derived values are
    computed from them, then conditions and medications are decided against the
    values that were actually drawn.
    """
    raw = profile.joint.sample_one(rng)

    # Derived values — computed, never sampled (build doc Section 8).
    if profile.egfr_mode == EGFR_FROM_CREATININE:
        raw["egfr"] = relations.ckd_epi_2021_egfr(
            creatinine_mg_dl=raw["creatinine"], age_years=age_years, sex=sex
        )
    elif profile.egfr_mode == EGFR_FROM_TARGET:
        # Sampling the target and inverting guarantees the stage constraint holds
        # exactly; sampling creatinine and hoping would need rejection sampling.
        raw["creatinine"] = relations.ckd_epi_2021_creatinine(
            egfr=raw["egfr_target"], age_years=age_years, sex=sex
        )
        raw["egfr"] = relations.ckd_epi_2021_egfr(
            creatinine_mg_dl=raw["creatinine"], age_years=age_years, sex=sex
        )
    else:
        raise ValueError(f"unknown egfr_mode {profile.egfr_mode!r}")

    conditions = list(profile.primary_conditions)
    if profile.derived_conditions is not None:
        conditions.extend(profile.derived_conditions(raw))
    for rule in profile.comorbidities:
        if rng.random() < rule.probability:
            conditions.append(rule.code)

    medications = [rule.code for rule in profile.medications if rule.applies(raw, rng)]

    analytes = {
        name: relations.to_reported(value, _precision_key(profile, name))
        for name, value in raw.items()
        if _precision_key(profile, name) in relations.REPORTING_PRECISION
    }

    return ProfileDraw(
        analytes=analytes,
        raw=raw,
        conditions=tuple(conditions),
        medications=tuple(medications),
    )


def _precision_key(profile: ClinicalProfile, analyte: str) -> str:
    """Map an analyte name onto a laboratory reporting precision."""
    if analyte in profile.reported_precision:
        return profile.reported_precision[analyte]
    if analyte in ("systolic", "diastolic"):
        return "blood_pressure"
    if analyte == "egfr_target":
        return "egfr"
    return analyte
