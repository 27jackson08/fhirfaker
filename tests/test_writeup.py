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
