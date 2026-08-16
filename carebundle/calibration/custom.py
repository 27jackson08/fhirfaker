"""Calibrate a profile to *your* population.

The marginals shipped here are NHANES: US adults aged 45-65. Your patients are not that
population, and for a lot of testing that matters — a renal clinic's creatinine
distribution, a paediatric service's everything, a UK cohort's HbA1c reporting units.

This lets you supply the summary statistics you *can* share — a median and quartiles per
analyte, which are not disclosive — and get a profile that reproduces them while keeping
the correlation structure, the computed identities and the conformance guarantees
intact. It is the one capability in this project that a population simulator
structurally cannot offer: Synthea's distributions come from its modules, and there is
no place to put your own.

    from carebundle import calibrate_profile, generate_bundle

    calibrate_profile(
        "our_clinic",
        base="type2_diabetes",
        marginals={"hba1c": Quartiles(median=8.4, q1=7.5, q3=9.8, low=6.0, high=13.5)},
    )
    bundle = generate_bundle(profile="our_clinic", seed=42)

**What this does not do is re-derive anything downstream.** Read `calibrate_profile`'s
docstring before overriding an analyte that participates in a published relationship —
there is a test in the suite demonstrating that overriding HbA1c alone breaks the ADAG
correlation, because it must.
"""

from __future__ import annotations

from dataclasses import dataclass

from carebundle.correlation.distributions import (
    AnyMarginal,
    lognormal_from_quartiles,
)
from carebundle.correlation.engine import JointModel
from carebundle.profiles.base import ClinicalProfile
from carebundle.profiles.library import PROFILES, get_profile

# Analytes whose marginal is derived from another analyte's, so overriding one without
# the other leaves a published relationship no longer holding. Overriding these is
# allowed — it is your population — but it is worth being told.
DERIVED_FROM = {
    "glucose": "hba1c",  # ADAG: the glucose marginal is calibrated against HbA1c's.
}


@dataclass(frozen=True)
class Quartiles:
    """The summary a site can usually share, because it discloses no individual.

    `low` and `high` are truncation bounds — use the 2.5th and 97.5th percentiles if you
    have them, or clinically defensible limits if you do not.
    """

    median: float
    q1: float
    q3: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if not self.q1 < self.median < self.q3:
            raise ValueError(
                f"quartiles must satisfy q1 < median < q3, got "
                f"{self.q1} / {self.median} / {self.q3}"
            )
        if not self.low < self.q1 or not self.q3 < self.high:
            raise ValueError(
                f"bounds must lie outside the quartiles, got low={self.low} "
                f"q1={self.q1} q3={self.q3} high={self.high}"
            )

    def to_marginal(self, name: str) -> AnyMarginal:
        """Fit a log-normal to these quartiles.

        Log-normal rather than normal because clinical analytes are overwhelmingly
        right-skewed, and a symmetric fit to a skewed target matches neither the centre
        nor the spread — the error that made every generated diabetic look alike before
        the NHANES calibration (build doc Section 18).
        """
        return lognormal_from_quartiles(
            name,
            median=self.median,
            q1=self.q1,
            q3=self.q3,
            low=self.low,
            high=self.high,
        )


def _replace_marginals(
    model: JointModel, replacements: dict[str, AnyMarginal]
) -> JointModel:
    """Swap marginals by name, leaving the correlation structure untouched.

    Correlations reference analytes by name, so replacing a marginal in place preserves
    every dependency the copula was given. That is the property that makes this safe:
    you change what a value looks like, not what it is related to.
    """
    unknown = set(replacements) - set(model.names)
    if unknown:
        # Worth being specific: several analytes are *computed* rather than sampled and
        # so have no marginal to replace. eGFR, LDL and BMI are derived from their
        # inputs, and `ckd_stage3` inverts CKD-EPI — it samples `egfr_target` and
        # computes creatinine from it, so creatinine is not overridable there. Override
        # the input instead; the identity will follow.
        raise ValueError(
            f"profile has no sampled analyte(s) {sorted(unknown)} to replace — they may "
            f"be computed from other values rather than drawn. Sampled analytes are: "
            f"{sorted(model.names)}"
        )
    return JointModel(
        marginals=tuple(
            replacements.get(marginal.name, marginal) for marginal in model.marginals
        ),
        correlations=model.correlations,
    )


def _as_marginal(analyte: str, value: Quartiles | AnyMarginal) -> AnyMarginal:
    """Accept either summary statistics or an already-built marginal."""
    return value.to_marginal(analyte) if isinstance(value, Quartiles) else value


def calibrate_profile(
    name: str,
    *,
    base: str,
    marginals: dict[str, Quartiles | AnyMarginal],
    overwrite: bool = False,
) -> str:
    """Register a profile matching `base` but with `marginals` replaced by yours.

    Returns the registered name, usable anywhere a built-in profile key is:
    `generate_bundle(profile=name, ...)`.

    Everything not overridden is inherited — conditions, medications, allergies, the
    correlation matrix, and the computed identities (eGFR from creatinine, Friedewald
    LDL, BMI). Conformance is unaffected: the resource shapes do not change, only the
    numbers inside them.

    **Two things it deliberately does not do.**

    It does not re-derive dependent marginals. The diabetic glucose marginal is
    calibrated against the HbA1c marginal so that the pair reproduces the ADAG
    regression *including its scatter*; override HbA1c alone and that relationship no
    longer holds. You will get a warning naming the analyte to override alongside. This
    is a warning rather than an error because it is your population and you may well
    know your own HbA1c/glucose relationship differs — but silently shipping a broken
    ADAG correlation would undermine the one thing this project asks to be trusted on.

    It does not check that your numbers are plausible. `Quartiles` validates ordering
    and bounds, and nothing validates clinical sense. Run the fidelity report against
    your profile if the relationships matter to you.
    """
    if name in PROFILES and not overwrite:
        raise ValueError(
            f"profile {name!r} already exists; pass overwrite=True to replace it"
        )
    if base not in PROFILES:
        raise ValueError(f"unknown base profile {base!r}; available: {sorted(PROFILES)}")
    if not marginals:
        raise ValueError("no marginals given; a profile identical to its base is a copy")

    for analyte, source in DERIVED_FROM.items():
        if source in marginals and analyte not in marginals:
            import warnings

            warnings.warn(
                f"overriding {source!r} without {analyte!r}: the {analyte!r} marginal "
                f"is calibrated against {source!r}, so their published relationship no "
                f"longer holds in profile {name!r}. Override both, or check the "
                f"fidelity report before relying on it.",
                UserWarning,
                stacklevel=2,
            )

    # Validate before registering, not on first use. A profile that raises only when
    # somebody eventually generates from it has already been handed out as working, and
    # the traceback surfaces far from the call that was actually wrong.
    for sex in ("F", "M"):
        _replace_marginals(
            get_profile(base, sex).joint,
            {analyte: _as_marginal(analyte, value) for analyte, value in marginals.items()},
        )

    def factory(sex: str) -> ClinicalProfile:
        profile = get_profile(base, sex)
        resolved = {
            analyte: _as_marginal(analyte, value)
            for analyte, value in marginals.items()
        }
        return ClinicalProfile(
            key=name,
            display=f"{profile.display} (calibrated: {name})",
            joint=_replace_marginals(profile.joint, resolved),
            primary_conditions=profile.primary_conditions,
            comorbidities=profile.comorbidities,
            medications=profile.medications,
            allergies=profile.allergies,
            egfr_mode=profile.egfr_mode,
            reported_precision=profile.reported_precision,
            derived_conditions=profile.derived_conditions,
        )

    PROFILES[name] = factory
    return name


def forget_profile(name: str) -> None:
    """Remove a profile registered by `calibrate_profile`.

    Refuses to remove a built-in, so a test that tidies up after itself cannot
    accidentally delete `healthy` for everything that runs afterwards.
    """
    if name in BUILT_IN_PROFILES:
        raise ValueError(f"{name!r} is a built-in profile and cannot be removed")
    PROFILES.pop(name, None)


# Captured at import, before any caller can register anything.
BUILT_IN_PROFILES = frozenset(PROFILES)

__all__ = [
    "BUILT_IN_PROFILES",
    "Quartiles",
    "calibrate_profile",
    "forget_profile",
]
