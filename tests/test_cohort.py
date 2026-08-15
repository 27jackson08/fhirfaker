"""Mixed cohorts and recorded allergies."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from carebundle.core.bundle import dangling_references, to_json
from carebundle.generate import DEFAULT_COHORT_PREVALENCE, generate_cohort, generate_draw


def _resource_types(bundle) -> list[str]:
    return [e["resource"]["resourceType"] for e in json.loads(to_json(bundle))["entry"]]


# --- cohorts ---------------------------------------------------------------------

def test_cohort_returns_the_requested_number_of_bundles():
    assert len(generate_cohort(count=25, seed=1)) == 25


def test_cohort_is_deterministic_including_profile_assignment():
    first = [to_json(b) for b in generate_cohort(count=15, seed=3)]
    second = [to_json(b) for b in generate_cohort(count=15, seed=3)]
    assert first == second


def test_cohort_patients_are_distinct():
    rendered = {to_json(b) for b in generate_cohort(count=20, seed=4)}
    assert len(rendered) == 20


def test_cohort_mix_tracks_the_configured_prevalence():
    """A cohort that ignores its weights is just a slow single-profile generator."""
    bundles = generate_cohort(
        count=400, seed=9, prevalence={"healthy": 0.75, "ckd_stage3": 0.25}
    )
    with_ckd = sum(
        any(
            coding["code"].startswith("N18")
            for entry in json.loads(to_json(b))["entry"]
            if entry["resource"]["resourceType"] == "Condition"
            for coding in entry["resource"]["code"]["coding"]
        )
        for b in bundles
    )
    assert 0.18 <= with_ckd / len(bundles) <= 0.32


def test_every_cohort_bundle_is_referentially_intact():
    for bundle in generate_cohort(count=12, seed=5):
        assert dangling_references(bundle) == set()


def test_default_prevalence_sums_to_one():
    assert sum(DEFAULT_COHORT_PREVALENCE.values()) == pytest.approx(1.0)


def test_prevalence_need_not_be_normalised():
    """Weights are normalised, so callers can pass counts or ratios."""
    bundles = generate_cohort(count=10, seed=6, prevalence={"healthy": 3, "hypertension": 1})
    assert len(bundles) == 10


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"count": 0, "seed": 1}, "count must be at least 1"),
        ({"count": 5, "seed": 1, "prevalence": {"nope": 1.0}}, "unknown profile"),
        ({"count": 5, "seed": 1, "prevalence": {"healthy": 0.0}}, "positive number"),
    ],
)
def test_invalid_cohort_arguments_are_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        generate_cohort(**kwargs)


def test_cohort_alternates_sex_when_mixed():
    bundles = generate_cohort(count=4, seed=8, sex="mixed")
    genders = [
        next(
            e["resource"]["gender"]
            for e in json.loads(to_json(b))["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        for b in bundles
    ]
    assert genders == ["female", "male", "female", "male"]


# --- allergies -------------------------------------------------------------------

def test_allergy_prevalence_matches_configuration():
    counts = Counter()
    trials = 2_000
    for seed in range(trials):
        for allergy in generate_draw(profile="healthy", seed=seed).allergies:
            counts[allergy.code] += 1
    # Penicillin is configured at 10%; 4 binomial SEs keeps this from flaking.
    observed = counts["7980"] / trials
    tolerance = 4.0 * (0.10 * 0.90 / trials) ** 0.5
    assert abs(observed - 0.10) <= tolerance, f"penicillin allergy rate {observed:.3f}"


def test_allergies_use_rxnorm_ingredients_not_snomed():
    """SNOMED is excluded by design, so drug allergies must be RxNorm-coded."""
    seen = {
        a.system
        for seed in range(200)
        for a in generate_draw(profile="healthy", seed=seed).allergies
    }
    assert seen == {"http://www.nlm.nih.gov/research/umls/rxnorm"}


def test_allergy_resources_appear_in_the_bundle_when_drawn():
    from carebundle.generate import generate_bundle

    seed = next(
        s for s in range(60) if generate_draw(profile="healthy", seed=s).allergies
    )
    assert "AllergyIntolerance" in _resource_types(generate_bundle(profile="healthy", seed=seed))


def test_sulfamethoxazole_is_not_the_veterinary_sulfonamide():
    """RxNav's approximate search returns 10178 sulfamethazine for this query."""
    from carebundle.terminology import codes

    assert codes.ALLERGEN_SULFAMETHOXAZOLE.code == "10180"
    assert codes.ALLERGEN_SULFAMETHOXAZOLE.display == "sulfamethoxazole"


# --- panel selection --------------------------------------------------------------

def test_panel_selection_shrinks_the_bundle():
    from carebundle.generate import ALL_PANELS, LEAN_PANELS, generate_bundle

    sizes = {
        label: len(json.loads(to_json(generate_bundle(seed=42, **kwargs)))["entry"])
        for label, kwargs in (
            ("full", {"panels": ALL_PANELS}),
            ("lean", {"panels": LEAN_PANELS}),
            ("none", {"panels": (), "include_vitals": False}),
        )
    }
    assert sizes["full"] > sizes["lean"] > sizes["none"]


def test_narrowing_panels_does_not_change_the_clinical_draw():
    """Emitting less must never change what was generated, only what is reported."""
    from carebundle.generate import generate_bundle

    def observation_values(**kwargs):
        payload = json.loads(to_json(generate_bundle(seed=42, **kwargs)))
        return {
            entry["resource"]["code"]["coding"][0]["code"]:
                entry["resource"]["valueQuantity"]["value"]
            for entry in payload["entry"]
            if entry["resource"]["resourceType"] == "Observation"
            and "valueQuantity" in entry["resource"]
        }

    full = observation_values()
    lean = observation_values(panels=("lipid",), include_vitals=False)
    assert lean, "lean selection should still emit the lipid panel"
    for code, value in lean.items():
        assert full[code] == value, f"{code} changed when panels were narrowed"


def test_unknown_panel_is_rejected():
    from carebundle.generate import generate_bundle

    with pytest.raises(ValueError, match="unknown panel"):
        generate_bundle(seed=1, panels=("not_a_panel",))


def test_cli_accepts_panel_shortcuts(tmp_path, capsys):
    from carebundle.cli import main

    for value in ("all", "lean", "none", "cmp,lipid"):
        assert main(["generate", "--panels", value, "--out", str(tmp_path)]) == 0
    capsys.readouterr()


def test_cli_rejects_unknown_panel():
    from carebundle.cli import main

    with pytest.raises(SystemExit, match="unknown panel"):
        main(["generate", "--panels", "bogus"])


@pytest.mark.parametrize(
    "age_range,match",
    [((70, 40), "exceeds high"), ((-5, 40), "cannot be negative")],
)
def test_library_validates_age_range_with_its_own_message(age_range, match):
    """Previously this surfaced as numpy's "low >= high" from inside the sampler,
    which says nothing about which argument was wrong."""
    from carebundle.generate import generate_bundle

    with pytest.raises(ValueError, match=match):
        generate_bundle(seed=1, age_range=age_range)
