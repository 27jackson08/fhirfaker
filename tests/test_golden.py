"""Golden-file snapshots — the determinism contract's enforcement mechanism.

`test_determinism.py` proves output is stable *within* a run. That is not the promise
users build CI on. The promise is that `seed=42` produces the same bytes next month,
after a refactor, on someone else's machine — and only a committed artifact can catch
a change to that.

A diff here is not necessarily a bug. It means generated output changed, which is a
MAJOR version event under the stability policy (see README). If the change is
intended, regenerate with:

    pytest tests/test_golden.py --update-golden

and review the diff as part of the change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from carebundle.calibration.custom import BUILT_IN_PROFILES
from carebundle.core.bundle import to_json
from carebundle.generate import generate_bundle, generate_patient

GOLDEN_DIR = Path(__file__).parent / "golden"
# Derived from the profile registry rather than listed here. When this was a hardcoded
# tuple, `anaemia` shipped in 0.2.0 with no golden file at all — the determinism
# contract covers every profile, but only the four somebody remembered to type were
# actually pinned. Deriving it means a new profile cannot escape the contract by
# omission; it fails until its golden exists.
PROFILES = tuple(sorted(BUILT_IN_PROFILES))
GOLDEN_SEED = 42


def _check(name: str, rendered: str, update: bool) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    if update:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        pytest.skip(f"regenerated {path.name}")
    if not path.exists():
        pytest.fail(
            f"missing golden file {path}. Create it with:\n"
            "  pytest tests/test_golden.py --update-golden"
        )
    assert rendered == path.read_text(encoding="utf-8"), (
        f"{name} no longer matches its golden file.\n"
        "Generated output changed. Under the stability policy that is a MAJOR version\n"
        "event: users pin fixtures to seeds. If intended, regenerate with\n"
        "  pytest tests/test_golden.py --update-golden\n"
        "and review the diff."
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_bundle_matches_golden(profile, update_golden):
    rendered = to_json(generate_bundle(profile=profile, seed=GOLDEN_SEED, sex="F"))
    _check(f"bundle-{profile}", rendered, update_golden)


@pytest.mark.parametrize("sex", ["F", "M"])
def test_patient_matches_golden(sex, update_golden):
    rendered = to_json(generate_patient(seed=GOLDEN_SEED, sex=sex))
    _check(f"patient-{sex}", rendered, update_golden)


def test_golden_files_are_committed():
    """A silently-absent golden file would make this whole suite vacuous."""
    expected = {f"bundle-{p}.json" for p in PROFILES} | {"patient-F.json", "patient-M.json"}
    actual = {p.name for p in GOLDEN_DIR.glob("*.json")}
    assert expected <= actual, f"missing golden files: {sorted(expected - actual)}"
