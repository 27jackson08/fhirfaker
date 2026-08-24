"""Calibrating a profile to a caller's own population (ROADMAP.md Phase 11).

The capability is only worth having if it keeps the guarantees that make the built-in
profiles trustworthy — correlations, computed identities, conformance — while changing
the numbers. Most of this file tests that, plus the one place it deliberately cannot:
overriding an analyte another marginal was derived from.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from carebundle import generate_bundle
from carebundle.calibration.custom import (
    BUILT_IN_PROFILES,
    Quartiles,
    calibrate_profile,
    forget_profile,
)
from carebundle.core.bundle import dangling_references, to_json
from carebundle.correlation import relations
from carebundle.profiles.library import PROFILES, get_profile

# type2_diabetes samples creatinine directly. `ckd_stage3` does not — it samples
# egfr_target and computes creatinine by inverting CKD-EPI, so creatinine has no
# marginal there to replace. There is a test below for that error.
RENAL = {"creatinine": Quartiles(median=2.1, q1=1.6, q3=2.9, low=0.9, high=6.0)}


@pytest.fixture
def clinic():
    name = calibrate_profile("test_clinic", base="type2_diabetes", marginals=RENAL)
    yield name
    forget_profile(name)


# --- it does what it says ------------------------------------------------------------

def test_the_supplied_distribution_is_reproduced(clinic):
    rng = np.random.default_rng(3)
    drawn = get_profile(clinic, "M").joint.sample(rng, size=20_000)["creatinine"]
    assert float(np.median(drawn)) == pytest.approx(2.1, abs=0.08)


def test_the_base_profile_is_not_modified(clinic):
    rng = np.random.default_rng(3)
    base = get_profile("type2_diabetes", "M").joint.sample(rng, size=5_000)["creatinine"]
    assert float(np.median(base)) < 1.5, (
        "registering a calibrated profile must not mutate the profile it derives from"
    )


def test_correlations_survive_the_override():
    """Replacing a marginal by name must leave the dependency structure intact."""
    name = calibrate_profile(
        "test_corr",
        base="type2_diabetes",
        marginals={"triglycerides": Quartiles(median=200, q1=150, q3=280, low=60, high=370)},
    )
    try:
        rng = np.random.default_rng(5)
        sample = get_profile(name, "M").joint.sample(rng, size=20_000)
        observed = float(np.corrcoef(sample["triglycerides"], sample["hdl"])[0, 1])
        assert observed < -0.15, "the TG/HDL relationship must not be lost"
    finally:
        forget_profile("test_corr")


def test_computed_identities_still_hold(clinic):
    """eGFR is computed from creatinine, so it must track a changed creatinine."""
    from carebundle.profiles.base import draw

    rng = np.random.default_rng(7)
    for _ in range(50):
        drawn = draw(get_profile(clinic, "M"), rng=rng, age_years=58.0, sex="M")
        expected = relations.ckd_epi_2021_egfr(
            creatinine_mg_dl=drawn.raw["creatinine"], age_years=58.0, sex="M"
        )
        assert drawn.raw["egfr"] == pytest.approx(expected, rel=1e-9)


def test_a_calibrated_profile_generates_a_usable_bundle(clinic):
    bundle = generate_bundle(profile=clinic, seed=42)
    assert not dangling_references(bundle)
    payload = json.loads(to_json(bundle))
    assert payload["resourceType"] == "Bundle"
    assert payload["entry"]


# --- the honest limitation -----------------------------------------------------------

def test_overriding_hba1c_alone_warns_because_it_breaks_adag():
    """The glucose marginal is calibrated against HbA1c's, so this cannot silently work.

    Warned rather than blocked: it is the caller's population and they may know their own
    relationship differs. Shipping a broken ADAG correlation without saying so would
    undermine the single claim this project most asks to be trusted on.
    """
    with pytest.warns(UserWarning, match="hba1c"):
        calibrate_profile(
            "test_adag",
            base="type2_diabetes",
            marginals={"hba1c": Quartiles(median=9.5, q1=8.6, q3=11.0, low=6.5, high=14.0)},
        )
    try:
        rng = np.random.default_rng(11)
        sample = get_profile("test_adag", "F").joint.sample(rng, size=20_000)
        slope = float(np.polyfit(sample["hba1c"], sample["glucose"], 1)[0])
        assert abs(slope - relations.ADAG_SLOPE) > 1.0, (
            "this test documents that ADAG genuinely breaks; if it now holds, the "
            "warning is wrong and should be removed rather than left misleading"
        )
    finally:
        forget_profile("test_adag")


def test_overriding_both_sides_does_not_warn():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        calibrate_profile(
            "test_both",
            base="type2_diabetes",
            marginals={
                "hba1c": Quartiles(median=8.4, q1=7.5, q3=9.8, low=6.0, high=13.5),
                "glucose": Quartiles(median=190, q1=155, q3=240, low=90, high=420),
            },
        )
    forget_profile("test_both")


# --- validation ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"median": 5.0, "q1": 6.0, "q3": 7.0, "low": 1.0, "high": 9.0},   # median below q1
    {"median": 5.0, "q1": 4.0, "q3": 6.0, "low": 4.5, "high": 9.0},   # low inside q1
    {"median": 5.0, "q1": 4.0, "q3": 6.0, "low": 1.0, "high": 5.5},   # high inside q3
])
def test_incoherent_quartiles_are_rejected(bad):
    with pytest.raises(ValueError):
        Quartiles(**bad)


def test_unknown_analyte_is_rejected():
    with pytest.raises(ValueError, match="no sampled analyte"):
        calibrate_profile(
            "test_bad", base="healthy",
            marginals={"unobtainium": Quartiles(median=2, q1=1, q3=3, low=0.5, high=4)},
        )


def test_a_computed_analyte_cannot_be_overridden():
    """`ckd_stage3` computes creatinine from a sampled eGFR, so it has no marginal.

    Found by writing this suite: the obvious way to demo the feature — a renal clinic
    overriding creatinine — fails on the one profile where creatinine is derived. The
    error names the sampled analytes rather than just saying no.
    """
    with pytest.raises(ValueError, match="computed from other values"):
        calibrate_profile("test_derived", base="ckd_stage3", marginals=RENAL)


def test_unknown_base_is_rejected():
    with pytest.raises(ValueError, match="unknown base profile"):
        calibrate_profile("test_bad2", base="not_a_profile", marginals=RENAL)


def test_registering_over_an_existing_name_requires_overwrite(clinic):
    with pytest.raises(ValueError, match="already exists"):
        calibrate_profile(clinic, base="type2_diabetes", marginals=RENAL)
    calibrate_profile(clinic, base="type2_diabetes", marginals=RENAL, overwrite=True)


def test_empty_marginals_are_rejected():
    with pytest.raises(ValueError, match="no marginals"):
        calibrate_profile("test_empty", base="healthy", marginals={})


@pytest.mark.parametrize("built_in", sorted(BUILT_IN_PROFILES))
def test_built_in_profiles_cannot_be_removed(built_in):
    with pytest.raises(ValueError, match="built-in"):
        forget_profile(built_in)
    assert built_in in PROFILES


def test_registering_a_profile_invalidates_the_profile_cache():
    """`get_profile` is cached, so a re-registered name must not serve the old build.

    The cache exists because building the diabetes profile costs ~10 ms — a 50,000
    sample bisection for its HbA1c/glucose latent correlation — and it was paid once per
    generated patient for an answer that never changes. Caching a registry lookup is
    only safe if the registry tells the cache when it changes.
    """
    from carebundle.calibration.custom import calibrate_profile, forget_profile
    from carebundle.profiles.library import get_profile

    name = "cache_invalidation_probe"
    try:
        calibrate_profile(
            name=name, base="healthy",
            marginals={"hba1c": Quartiles(median=5.5, q1=5.2, q3=5.8, low=4.6, high=6.4)},
        )
        first = get_profile(name, "F")
        assert first is get_profile(name, "F"), "cache is not serving repeat calls"

        # Re-register the same name with a different distribution.
        forget_profile(name)
        calibrate_profile(
            name=name, base="healthy",
            marginals={"hba1c": Quartiles(median=6.1, q1=5.9, q3=6.3, low=5.2, high=7.0)},
        )
        second = get_profile(name, "F")
        assert second is not first, "stale profile served after re-registration"

        def median_of(profile):
            marginal = next(m for m in profile.joint.marginals if m.name == "hba1c")
            return marginal.moments()[0]

        assert median_of(second) > median_of(first), (
            "re-registered profile did not take effect"
        )
    finally:
        forget_profile(name)


def test_forgetting_a_profile_clears_it_from_the_cache():
    """A removed profile must stop resolving, not linger in the cache."""
    from carebundle.calibration.custom import calibrate_profile, forget_profile
    from carebundle.profiles.library import get_profile

    name = "cache_removal_probe"
    calibrate_profile(
        name=name, base="healthy",
        marginals={"hba1c": Quartiles(median=5.5, q1=5.2, q3=5.8, low=4.6, high=6.4)},
    )
    get_profile(name, "F")
    forget_profile(name)
    with pytest.raises(ValueError, match="unknown profile"):
        get_profile(name, "F")
