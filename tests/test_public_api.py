"""The public API surface, exactly as the README advertises it.

Documentation drifts from code silently. These tests execute the README's examples so
a rename or signature change breaks the build instead of the docs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import pkg

README = Path(__file__).resolve().parents[1] / "README.md"


def test_top_level_imports_match_the_documented_surface():
    from pkg import (  # noqa: F401
        generate_bundle,
        generate_draw,
        generate_patient,
        to_json,
    )

    assert set(pkg.__all__) >= {
        "generate_bundle", "generate_draw", "generate_patient", "to_json"
    }


def test_readme_first_example_runs():
    bundle = pkg.generate_bundle(profile="type2_diabetes", seed=42, sex="F")
    assert bundle.entry


def test_readme_usage_block_runs():
    bundle = pkg.generate_bundle(
        profile="type2_diabetes", seed=42, sex="F", age_range=(45, 65)
    )
    patient = pkg.generate_patient(seed=42, sex="M")
    drawn = pkg.generate_draw(profile="ckd_stage3", seed=42, sex="F", age_years=58)

    assert json.loads(pkg.to_json(bundle))["resourceType"] == "Bundle"
    assert patient.gender == "male"
    assert "egfr" in drawn.analytes
    assert drawn.conditions


def test_version_is_exposed():
    assert pkg.__version__.count(".") == 2


@pytest.mark.parametrize("profile", ["healthy", "hypertension", "type2_diabetes", "ckd_stage3"])
def test_every_documented_profile_is_generable(profile):
    assert profile in pkg.PROFILES
    assert pkg.generate_bundle(profile=profile, seed=1).entry


def test_unknown_profile_names_are_rejected():
    with pytest.raises(ValueError, match="unknown profile"):
        pkg.generate_bundle(profile="not_a_profile", seed=1)


# --- README claims that must stay true -------------------------------------------

def test_readme_documents_the_profiles_that_actually_exist():
    text = README.read_text()
    for profile in pkg.PROFILES:
        assert f"`{profile}`" in text, f"README does not document profile {profile}"


def test_readme_declares_only_the_real_runtime_dependencies():
    """The install-weight claim is part of the pitch; it has to stay honest."""
    pyproject = (README.parent / "pyproject.toml").read_text()
    runtime = pyproject.split("dependencies = [")[1].split("]")[0]
    assert "scipy" not in runtime
    for declared in ("pydantic", "numpy"):
        assert declared in runtime


def test_htest_label_claim_in_readme_holds():
    bundle = json.loads(pkg.to_json(pkg.generate_bundle(profile="healthy", seed=3)))
    for entry in bundle["entry"]:
        codes = [c["code"] for c in entry["resource"]["meta"]["security"]]
        assert "HTEST" in codes


def test_synthetic_narrative_claim_in_readme_holds():
    bundle = json.loads(pkg.to_json(pkg.generate_bundle(profile="healthy", seed=3)))
    for entry in bundle["entry"]:
        assert "SYNTHETIC TEST DATA" in entry["resource"]["text"]["div"]
