"""The public API surface, exactly as the README advertises it.

Documentation drifts from code silently. These tests execute the README's examples so
a rename or signature change breaks the build instead of the docs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import carebundle

README = Path(__file__).resolve().parents[1] / "README.md"


def test_top_level_imports_match_the_documented_surface():
    from carebundle import (  # noqa: F401
        generate_bundle,
        generate_draw,
        generate_patient,
        to_json,
    )

    assert set(carebundle.__all__) >= {
        "generate_bundle", "generate_draw", "generate_patient", "to_json"
    }


def test_readme_first_example_runs():
    bundle = carebundle.generate_bundle(profile="type2_diabetes", seed=42, sex="F")
    assert bundle.entry


def test_readme_usage_block_runs():
    bundle = carebundle.generate_bundle(
        profile="type2_diabetes", seed=42, sex="F", age_range=(45, 65)
    )
    patient = carebundle.generate_patient(seed=42, sex="M")
    drawn = carebundle.generate_draw(profile="ckd_stage3", seed=42, sex="F", age_years=58)

    assert json.loads(carebundle.to_json(bundle))["resourceType"] == "Bundle"
    assert patient.gender == "male"
    assert "egfr" in drawn.analytes
    assert drawn.conditions


def test_version_is_exposed():
    assert carebundle.__version__.count(".") == 2


def test_version_is_single_sourced_and_cannot_drift():
    """0.1.1 shipped with metadata saying 0.1.1 and `__version__` saying 0.1.0.

    The old test only checked the string had two dots, so it could not have caught that.
    `pyproject.toml` now declares the version dynamic and reads it from
    `carebundle/__init__.py`, which makes the two impossible to disagree — this asserts
    the configuration that guarantees it, since a future edit could reintroduce a
    literal and silently restore the failure mode.
    """
    pyproject = (README.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject, (
        "pyproject must derive the version rather than duplicate it"
    )
    assert 'path = "carebundle/__init__.py"' in pyproject, (
        "the dynamic version must be sourced from the module that defines __version__"
    )
    assert not re.search(r'^version\s*=', pyproject, re.MULTILINE), (
        "a literal version in pyproject can drift from __version__; that is the bug"
    )


def test_installed_metadata_matches_the_module_version():
    """When installed, the distribution version and `__version__` must agree.

    Skipped in a bare source checkout, where there is no installed distribution to
    compare against.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        installed = version("carebundle")
    except PackageNotFoundError:
        pytest.skip("carebundle is not installed in this environment")
    assert installed == carebundle.__version__


@pytest.mark.parametrize("profile", ["healthy", "hypertension", "type2_diabetes", "ckd_stage3"])
def test_every_documented_profile_is_generable(profile):
    assert profile in carebundle.PROFILES
    assert carebundle.generate_bundle(profile=profile, seed=1).entry


def test_unknown_profile_names_are_rejected():
    with pytest.raises(ValueError, match="unknown profile"):
        carebundle.generate_bundle(profile="not_a_profile", seed=1)


# --- README claims that must stay true -------------------------------------------

def test_readme_documents_the_profiles_that_actually_exist():
    text = README.read_text(encoding="utf-8")
    for profile in carebundle.PROFILES:
        assert f"`{profile}`" in text, f"README does not document profile {profile}"


def test_readme_declares_only_the_real_runtime_dependencies():
    """The install-weight claim is part of the pitch; it has to stay honest."""
    pyproject = (README.parent / "pyproject.toml").read_text(encoding="utf-8")
    runtime = pyproject.split("dependencies = [")[1].split("]")[0]
    assert "scipy" not in runtime
    for declared in ("pydantic", "numpy"):
        assert declared in runtime


def test_typed_classifier_is_backed_by_a_py_typed_marker():
    """A `Typing :: Typed` classifier without the marker ships types nobody can read.

    PEP 561 requires the marker file; without it type checkers ignore the annotations
    entirely and the classifier is a claim the package does not honour.
    """
    pyproject = (README.parent / "pyproject.toml").read_text(encoding="utf-8")
    if "Typing :: Typed" not in pyproject:
        pytest.skip("package does not advertise inline types")
    marker = Path(carebundle.__file__).parent / "py.typed"
    assert marker.exists(), "pyproject claims 'Typing :: Typed' but carebundle/py.typed is missing"


def test_htest_label_claim_in_readme_holds():
    bundle = json.loads(carebundle.to_json(carebundle.generate_bundle(profile="healthy", seed=3)))
    for entry in bundle["entry"]:
        codes = [c["code"] for c in entry["resource"]["meta"]["security"]]
        assert "HTEST" in codes


def test_synthetic_narrative_claim_in_readme_holds():
    bundle = json.loads(carebundle.to_json(carebundle.generate_bundle(profile="healthy", seed=3)))
    for entry in bundle["entry"]:
        assert "SYNTHETIC TEST DATA" in entry["resource"]["text"]["div"]


# --- documentation consistency ----------------------------------------------------
# Numbers in prose drift silently. The README claimed "104 codes (42 LOINC, 29
# RxNorm, 22 ICD-10-CM)" against an actual 102 (…21) because the figure was typed
# rather than measured. These make that a build failure.

CONFORMANCE_DOC = README.parent / "CONFORMANCE.md"

_COUNT_CLAIM = re.compile(
    r"(\d+) codes \((\d+) LOINC, (\d+) RxNorm, (\d+) ICD-10-CM\)"
)
_TABLE_ROW = re.compile(r"^\|\s*(\w+)\s*\|\s*(\d+)\s*\|", re.MULTILINE)


def _documented_entry_counts(text: str) -> dict[str, int]:
    return {
        name: int(count)
        for name, count in _TABLE_ROW.findall(text)
        if name in carebundle.PROFILES
    }


def test_readme_code_counts_match_the_terminology_tables():
    from carebundle.terminology import systems
    from carebundle.terminology.verify import registered_codes

    match = _COUNT_CLAIM.search(README.read_text(encoding="utf-8"))
    assert match, "README no longer states a terminology count"
    total, loinc, rxnorm, icd10 = (int(g) for g in match.groups())

    codes = registered_codes()
    actual = {
        "total": len(codes),
        "loinc": sum(1 for c in codes if c.system == systems.LOINC),
        "rxnorm": sum(1 for c in codes if c.system == systems.RXNORM),
        "icd10": sum(1 for c in codes if c.system == systems.ICD10CM),
    }
    assert (total, loinc, rxnorm, icd10) == (
        actual["total"], actual["loinc"], actual["rxnorm"], actual["icd10"]
    ), f"README claims {match.group(0)}, actual is {actual}"


@pytest.mark.parametrize("document", ["README.md", "CONFORMANCE.md"])
def test_documented_bundle_sizes_match_generated_bundles(document):
    from carebundle.core.bundle import to_json

    text = (README.parent / document).read_text(encoding="utf-8")
    documented = _documented_entry_counts(text)
    assert documented, f"{document} no longer tabulates bundle sizes"

    for profile, claimed in documented.items():
        actual = len(json.loads(to_json(carebundle.generate_bundle(profile=profile, seed=42)))["entry"])
        assert claimed == actual, (
            f"{document} claims {profile} has {claimed} entries; it has {actual}"
        )


def test_readme_and_conformance_doc_agree_with_each_other():
    readme = _documented_entry_counts(README.read_text(encoding="utf-8"))
    conformance = _documented_entry_counts(CONFORMANCE_DOC.read_text(encoding="utf-8"))
    shared = readme.keys() & conformance.keys()
    assert shared, "the two documents no longer share a profile table"
    for profile in shared:
        assert readme[profile] == conformance[profile], (
            f"{profile}: README says {readme[profile]}, "
            f"CONFORMANCE.md says {conformance[profile]}"
        )


def test_readme_has_no_relative_links_because_it_is_the_pypi_page():
    """Relative links resolve against pypi.org there, not against the repository.

    Found live on the 0.1.0 page: every evidence document — BENCHMARK.md,
    CONFORMANCE.md, FIDELITY.md, ROADMAP.md, LICENSE — was a dead link on the page
    where "go and check the evidence" is the entire pitch. `twine check` does not catch
    this, because the markup is valid; only the destinations are wrong.
    """
    import re

    targets = re.findall(r"\]\(([^)]+)\)", README.read_text(encoding="utf-8"))
    relative = [
        t for t in targets
        if not t.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert not relative, (
        f"README is published as the PyPI long description, so these would 404 there: "
        f"{relative}. Use absolute https://github.com/... URLs."
    )


def test_every_runnable_module_is_documented():
    """A module with a CLI is a feature, and an undocumented feature does not exist.

    Four benchmark modules shipped in one session — `synthea`, `dependence`,
    `cooccurrence`, `drift` — and none of them appeared in `README.md` or
    `CONTRIBUTING.md`. Nothing failed, because nothing was checking. This is the same
    defect as the README denying a capability the package had, pointed the other way:
    capability the package has and nobody can find.

    "Runnable" means the module guards `__main__` and defines `main`, which is this
    project's convention for a command-line entry point. Documented means named in the
    README or the contributor guide — the two places a user or contributor looks.
    """
    import re

    root = README.parent
    package = root / "carebundle"

    # Parsed by regex rather than with tomllib, which is stdlib only from 3.11 and this
    # package supports 3.10 — the CI matrix caught that, not local testing. Same reason
    # `release.yml` reads `__version__` with a regex: the check should not need anything
    # installed to run.
    scripts_block = re.search(
        r"^\[project\.scripts\]\s*$(.*?)^\[", 
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    console_scripts: dict[str, list[str]] = {}
    for name, target in re.findall(
        r"^\s*([\w.-]+)\s*=\s*[\"']([^\"']+)[\"']",
        scripts_block.group(1) if scripts_block else "",
        re.MULTILINE,
    ):
        console_scripts.setdefault(target.split(":")[0], []).append(name)
    readme = README.read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")

    undocumented = []
    for path in sorted(package.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if '__name__ == "__main__"' not in source or not re.search(r"^def main\(", source, re.MULTILINE):
            continue
        dotted = ".".join(path.relative_to(root).with_suffix("").parts)
        if dotted.endswith(".__main__"):
            continue
        # A module is documented under either name it can be invoked by: the dotted
        # path for `python -m`, or its console-script name if pyproject declares one.
        # `carebundle.cli` is documented everywhere as `carebundle generate ...` and
        # nowhere as `python -m carebundle.cli`, which is correct and which the first
        # version of this test flagged as missing.
        names = [dotted, *console_scripts.get(dotted, ())]
        if not any(name in readme or name in contributing for name in names):
            undocumented.append(dotted)

    assert not undocumented, (
        "runnable modules absent from both README.md and CONTRIBUTING.md: "
        f"{undocumented}. Shipping a command nobody can discover is the same as not "
        "shipping it."
    )
