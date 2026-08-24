"""The write-up cites numbers; those numbers must stay true.

`docs/outcome-measures.md` is the piece that argues this project's central claim, quoting
figures from the benchmark, the fidelity report and the calibration. Prose drifts from
code silently — the README once claimed 104 terminology codes against an actual 102 —
and a write-up that has drifted is worse than no write-up, because it is the document a
reader is most likely to check.

These tests do not re-derive the science. They assert that every figure the write-up
quotes still appears in the artefact it came from.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRITEUP = ROOT / "docs" / "outcome-measures.md"
BENCHMARK = ROOT / "BENCHMARK.md"
FIDELITY = ROOT / "FIDELITY.md"


@pytest.fixture(scope="module")
def writeup() -> str:
    return WRITEUP.read_text()


# Each figure, and the document that is its source of truth.
CITED = [
    ("71.5%", BENCHMARK, "the headline control rate"),
    ("64.1%", BENCHMARK, "the rate before titration was modelled"),
    ("69.7%", BENCHMARK, "the US real-world comparator"),
    ("74.5%", BENCHMARK, "the Massachusetts comparator"),
    ("50.4%", BENCHMARK, "the refuted binary-adherence result"),
    ("49.3%", BENCHMARK, "the refuted PDC-scaled result"),
    ("11.70%", BENCHMARK, "CMS122 via Medicare Part B claims"),
    ("43.53%", BENCHMARK, "CMS122 via eCQM"),
    ("86.5%", BENCHMARK, "treated fraction of diagnosed hypertensives"),
    ("0.621", FIDELITY, "train-on-synthetic AUC"),
    ("0.677", FIDELITY, "train-on-real ceiling AUC"),
    ("91.7%", FIDELITY, "transfer retention"),
]


@pytest.mark.parametrize("figure,source,description", CITED)
def test_every_cited_figure_still_appears_in_its_source(writeup, figure, source, description):
    assert figure in writeup, f"write-up no longer quotes {figure} ({description})"
    assert figure in source.read_text(), (
        f"write-up quotes {figure} ({description}) but {source.name} no longer contains "
        f"it — one of the two has drifted"
    )


def test_the_out_of_sample_count_matches_the_fidelity_report(writeup):
    """The write-up's most self-critical claim, and so the one most worth pinning."""
    claimed = re.search(r"\*\*(\d+) of (\d+) is genuinely out-of-sample\*\*", writeup)
    assert claimed, "the write-up no longer states the out-of-sample count"
    actual = re.search(r"Only (\d+) of (\d+) checks is genuinely out-of-sample", FIDELITY.read_text())
    assert actual, "FIDELITY.md no longer states the out-of-sample count"
    assert claimed.groups() == actual.groups(), (
        f"write-up says {claimed.group(0)}, fidelity report says {actual.group(0)}"
    )


def test_writeup_links_are_absolute_or_repo_relative_but_not_broken():
    """Relative links must point at files that exist, since this ships in the repo."""
    targets = re.findall(r"\]\(([^)]+)\)", WRITEUP.read_text())
    for target in targets:
        if target.startswith(("http://", "https://", "#")):
            continue
        assert (WRITEUP.parent / target).resolve().exists(), f"broken link: {target}"


def test_every_shipped_document_is_reachable_from_the_readme():
    """A document nobody can find does no work.

    `docs/outcome-measures.md` sat in the repository unreferenced until this test was
    written. The README is the only entry point most readers get — GitHub renders it on
    the landing page and PyPI renders it as the project description — so anything not
    linked from it is effectively unpublished.
    """
    readme = (ROOT / "README.md").read_text()
    shipped = [
        "BENCHMARK.md", "CONFORMANCE.md", "FIDELITY.md", "ROADMAP.md",
        "CHANGELOG.md", "CONTRIBUTING.md", "RELEASING.md",
        "docs/outcome-measures.md",
    ]
    unreachable = [name for name in shipped if name not in readme]
    assert not unreachable, (
        f"these documents ship but are not linked from the README: {unreachable}"
    )


def test_readme_obesity_figures_match_the_fidelity_report():
    """The README quotes the diabetic obesity rate; it has drifted twice.

    First when the anthropometrics moved to the diagnosed stratum, then again when the
    red cell correlations shifted every profile's RNG stream. Both times the figure was
    a hand-typed copy of a number the fidelity report already computes.
    """
    readme = (ROOT / "README.md").read_text()
    row = re.search(r"\| diabetic obesity rate \| ([0-9.]+) \| ([0-9.]+) \|", FIDELITY.read_text())
    assert row, "FIDELITY.md no longer reports the diabetic obesity rate"
    observed, expected = float(row.group(1)), float(row.group(2))

    claim = re.search(r"([0-9.]+)% obese against\s*\n?\s*NHANES's ([0-9.]+)%", readme)
    assert claim, "README no longer states the obesity comparison"
    assert float(claim.group(1)) == pytest.approx(observed * 100, abs=0.05), (
        f"README says {claim.group(1)}% obese, fidelity report computes {observed:.1%}"
    )
    assert float(claim.group(2)) == pytest.approx(expected * 100, abs=0.05), (
        f"README says NHANES {claim.group(2)}%, fidelity report target is {expected:.1%}"
    )


def test_readme_does_not_deny_capabilities_the_library_has():
    """The README claimed 'no longitudinal history' after `generate_history` shipped.

    Understating is as much a documentation defect as overstating, and this one
    contradicted a section of the same file — a reader hitting the limits list would
    conclude the feature above it did not exist.
    """
    readme = (ROOT / "README.md").read_text()
    from carebundle import __all__ as exported

    if "generate_history" in exported:
        assert "No longitudinal history —" not in readme, (
            "README denies longitudinal support while generate_history is exported"
        )


def test_every_readme_evidence_row_matches_the_fidelity_report():
    """The README's evidence table is hand-copied from FIDELITY.md, so it drifts.

    Five of its ten rows were stale when this test was written: the ADAG slope, the
    glucose value at HbA1c 8.0%, both medians, and the obesity rate — the last of which
    contradicted the README's own prose about the same figure two sections away. It is
    the most persuasive table in the project, and it was the least checked.

    Matching is by exact row label, which is why the README now uses the report's
    labels verbatim rather than friendlier paraphrases. A row that cannot be found is a
    failure, not a skip: a renamed check must not silently drop out of the guard.
    """
    readme = (ROOT / "README.md").read_text()
    fidelity = FIDELITY.read_text()

    reported = {
        m.group(1).strip(): m.group(2)
        for m in re.finditer(r"^\| ([^|]+?) \| ([-0-9.e+]+) \|", fidelity, re.MULTILINE)
    }
    assert reported, "FIDELITY.md has no parseable check rows"

    rows = re.findall(r"^\| (?:\*\*)?([^|*]+?)(?:\*\*)? \| (?:\*\*)?([-0-9.e+]+)(?:\*\*)? \|",
                      readme, re.MULTILINE)
    checked = 0
    for label, observed in rows:
        label = label.strip()
        if label not in reported:
            continue
        assert float(observed) == pytest.approx(float(reported[label]), rel=1e-3), (
            f"README row {label!r} says {observed}, FIDELITY.md says {reported[label]}"
        )
        checked += 1
    # Guards the guard: if the README table were reformatted so no label matched, the
    # loop above would pass vacuously.
    assert checked >= 8, f"only matched {checked} README rows against the report"


def _measured_rate() -> str:
    """The canonical Synthea CBP rate, formatted as the documents write it."""
    from carebundle.benchmark.drift import load_record

    return f"{load_record()['controlling_high_blood_pressure']['synthea']['rate'] * 100:.1f}%"

def test_no_document_claims_synthea_scores_zero_in_the_present_tense():
    """The most expensive error in this project's history was a stale citation.

    `BENCHMARK.md`, `README.md` and the write-up all asserted that Synthea scores 0% on
    Controlling High Blood Pressure. That came from Chen et al. 2019 and was repeated
    for years without anyone running the software. Measured in August 2026, Synthea
    scores 74.8% — so the project's headline competitive claim had been false for an
    unknown length of time, and it survived precisely because a citation cannot go
    stale in CI the way a measurement can.

    This asserts the present-tense form is gone. Quoting the 2019 result as history is
    fine and necessary; asserting it as the current state of the software is not, and
    the difference is whether a correction sits beside it.
    """
    # This list is only as good as the phrasings it anticipates, and it has already
    # missed one: the README's opening argument said Synthea "scores **0%** on every
    # *outcome* measure" — present tense, fifteen lines above the correction — and every
    # guard passed, because that wording was not here.
    banned = (
        "Synthea scores 0%",
        "Synthea scores **0%**",
        "against Synthea's published 0%",
        "a pathway simulator scores **0%** on",
        "scores\n**0%** on every",
        "scores **0%** on every",
        "and scores\n**0%**",
    )
    for name in ("BENCHMARK.md", "README.md", "docs/outcome-measures.md"):
        text = (ROOT / name).read_text()
        for phrase in banned:
            if phrase not in text:
                continue
            # Permitted only where the same document carries the correction, so a
            # reader cannot reach the claim without reaching the retraction. The figure
            # is read from the record rather than typed here: this guard used to hardcode
            # 74.8%, and kept passing after the canonical figure became the 74.4% median,
            # which is the drift it exists to prevent showing up inside the guard itself.
            assert _measured_rate() in text, (
                f"{name} still asserts {phrase!r} without the measured correction"
            )


def test_benchmark_states_when_the_synthea_figure_was_measured():
    """A competitor's score is a measurement with a date, not a constant.

    Without the date the number is indistinguishable from the citation it replaced.
    """
    text = BENCHMARK.read_text()
    assert _measured_rate() in text, (
        "BENCHMARK.md no longer reports the measured Synthea rate"
    )
    assert "August 2026" in text or "Aug 2026" in text, (
        "BENCHMARK.md reports a Synthea rate without saying when it was measured"
    )
    assert "carebundle.benchmark.synthea" in text, (
        "BENCHMARK.md reports a measured rate without naming the harness that produced it"
    )
