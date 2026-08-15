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


# --- evidence grading (ROADMAP.md Phase 8) -----------------------------------------

def test_every_check_declares_a_known_evidence_grade(checks):
    from carebundle.fidelity.report import EVIDENCE

    for check in checks:
        assert check.evidence in EVIDENCE, (
            f"{check.name} has no valid evidence grade; a check that has not said what "
            f"it proves will be read as proving more than it does"
        )


def test_identity_checks_really_are_identities(checks):
    """Graded 'identity' means computed from its own inputs — so it must be exact."""
    for check in (c for c in checks if c.evidence == "identity"):
        assert check.tolerance <= 1e-6 or check.expected in (0.0, 1.0), (
            f"{check.name} is graded identity but carries a statistical tolerance; "
            f"either it is not an identity or the grade is wrong"
        )


def test_round_trip_checks_are_not_passed_off_as_external_evidence(checks):
    """A check sourced from our own config must not claim an outside authority."""
    for check in (c for c in checks if c.source == "profile config"):
        assert check.evidence == "round_trip", (
            f"{check.name} is checked against our own configuration, so it cannot be "
            f"graded {check.evidence!r}"
        )


def test_the_out_of_sample_count_cannot_inflate_silently(checks):
    """The headline honesty claim. Raising this number requires changing this test.

    The point of grading is that `out_of_sample` is the only category that evidences
    fidelity rather than self-consistency, which makes it the tempting one to quietly
    grow. Pinning the count means a new out-of-sample claim has to be argued for
    deliberately rather than arrived at by relabelling.
    """
    out_of_sample = [c for c in checks if c.evidence == "out_of_sample"]
    assert len(out_of_sample) == 1, (
        f"expected exactly 1 out-of-sample check, found {len(out_of_sample)}: "
        f"{[c.name for c in out_of_sample]}"
    )
    assert out_of_sample[0].name == "CMS Controlling High Blood Pressure"
