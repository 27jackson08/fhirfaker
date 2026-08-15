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

from carebundle.correlation import relations
from carebundle.correlation.engine import JointModel
from carebundle.terminology import codes as codes_module
from carebundle.terminology.codes import Code

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
    # An ICD-10-CM code that must already be on the problem list. Without this a
    # patient can be prescribed levothyroxine with no thyroid diagnosis anywhere in
    # the bundle — individually plausible, collectively incoherent.
    requires_condition: str | None = None

    def applies(
        self,
        analytes: dict[str, float],
        rng: np.random.Generator,
        conditions: frozenset[str] = frozenset(),
    ) -> bool:
        if self.requires is not None and not self.requires(analytes):
            return False
        if self.requires_condition is not None and self.requires_condition not in conditions:
            return False
        return bool(rng.random() < self.probability)


@dataclass(frozen=True)
class AllergyRule:
    """A recorded drug allergy and how often it appears."""

    code: Code
    probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"{self.code.display}: probability out of range")


@dataclass(frozen=True)
class ProfileDraw:
    """One patient's worth of jointly-drawn clinical facts."""

    analytes: dict[str, Decimal]
    raw: dict[str, float]
    conditions: tuple[Code, ...]
    medications: tuple[Code, ...]
    allergies: tuple[Code, ...] = ()


@dataclass(frozen=True)
class ClinicalProfile:
    key: str
    display: str
    joint: JointModel
    primary_conditions: tuple[Code, ...] = ()
    comorbidities: tuple[ComorbidityRule, ...] = ()
    medications: tuple[MedicationRule, ...] = ()
    allergies: tuple[AllergyRule, ...] = ()
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

    # LDL is calculated from the rest of the panel, never sampled beside it — a lipid
    # panel whose four numbers disagree is the exact incoherence this engine exists
    # to prevent. The triglyceride marginal is bounded below Friedewald's validity
    # threshold, so the formula's domain holds by construction.
    if {"cholesterol_total", "hdl", "triglycerides"} <= raw.keys():
        raw["ldl"] = relations.friedewald_ldl(
            total_cholesterol=raw["cholesterol_total"],
            hdl=raw["hdl"],
            triglycerides=raw["triglycerides"],
        )

    if {"weight_kg", "height_cm"} <= raw.keys():
        raw["bmi"] = relations.body_mass_index(
            weight_kg=raw["weight_kg"], height_cm=raw["height_cm"]
        )

    conditions = list(profile.primary_conditions)
    if profile.derived_conditions is not None:
        conditions.extend(profile.derived_conditions(raw))
    for rule in profile.comorbidities:
        if rng.random() < rule.probability:
            conditions.append(rule.code)

    coded = frozenset(c.code for c in conditions)
    medications = [
        rule.code for rule in profile.medications if rule.applies(raw, rng, coded)
    ]
    allergies = [rule.code for rule in profile.allergies if rng.random() < rule.probability]

    # Blood pressure is the one analyte whose *observed* value depends on what was
    # prescribed, so it is finalised here rather than at sampling time. The copula
    # draws the pre-treatment pressure; the recorded pressure is that value after the
    # regimen this patient actually received.
    #
    # This ordering is deliberate and clinically correct in both directions: the
    # medication rules escalate on the pre-treatment pressure (you add an agent
    # because the patient is uncontrolled), and the recorded pressure then reflects
    # the agents added. Sampling an "observed" pressure independently of the drug list
    # would let a bundle prescribe three antihypertensives beside an untreated-looking
    # 168/102 — exactly the class of contradiction this engine exists to prevent.
    if {"systolic", "diastolic"} <= raw.keys():
        raw["pretreatment_systolic"] = raw["systolic"]
        raw["pretreatment_diastolic"] = raw["diastolic"]
        raw["antihypertensive_classes"] = float(
            codes_module.antihypertensive_class_count(medications)
        )
        raw["systolic"], raw["diastolic"] = relations.antihypertensive_response(
            systolic=raw["systolic"],
            diastolic=raw["diastolic"],
            agent_count=int(raw["antihypertensive_classes"]),
        )

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
        allergies=tuple(allergies),
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
