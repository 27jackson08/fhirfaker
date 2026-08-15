"""Fidelity gate.

Marked `fidelity` and run nightly: n=10,000 draws per profile is too slow for a PR
gate. Seeds are fixed — a statistical suite that flakes gets ignored, and an ignored
gate is worse than none.
"""

from __future__ import annotations

import pytest

from carebundle.fidelity.report import DEFAULT_SEED, render_markdown, run_all

pytestmark = pytest.mark.fidelity


@pytest.fixture(scope="module")
def checks():
    return run_all(size=10_000, seed=DEFAULT_SEED)


def test_every_fidelity_check_passes(checks):
    failed = [c for c in checks if not c.passed]
    assert not failed, "fidelity drift:\n" + "\n".join(
        f"  {c.name}: observed {c.observed:.4g}, expected {c.expected:.4g} "
        f"(delta {c.delta:+.3g}, tolerance ±{c.tolerance:.3g})"
        for c in failed
    )


def test_report_covers_the_relationships_that_justify_the_claim(checks):
    names = " ".join(c.name for c in checks)
    for required in ("ADAG slope", "ADAG R^2", "eGFR consistent", "comorbidity"):
        assert required in names, f"fidelity report lost its {required} check"


def test_r_squared_check_is_two_sided(checks):
    """A perfect correlation must fail, not pass. This is the whole differentiator."""
    r_squared = next(c for c in checks if c.name == "ADAG R^2")
    assert abs(1.0 - r_squared.expected) > r_squared.tolerance


def test_report_renders(checks):
    markdown = render_markdown(checks, size=10_000, seed=DEFAULT_SEED)
    assert "| Check |" in markdown
    assert "PASS" in markdown
