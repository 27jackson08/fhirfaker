"""Every figure in the preprint, checked against the committed records.

This project has found five separate cases of a number in prose drifting from the
artefact that produced it. A preprint is the worst possible place for a sixth: it is the
one document a reader cannot regenerate, and the one whose figures get quoted onward.

So the paper does not get to hold a number the repository cannot produce.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs/paper/joint-structure-preprint.md"
DATA = ROOT / "carebundle/benchmark/data"


@pytest.fixture(scope="module")
def paper() -> str:
    return PAPER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flat(paper) -> str:
    """The paper with line wrapping removed.

    A phrase that happens to straddle a line break is still present in the document, and
    a test that says otherwise is testing the wrap column.
    """
    return re.sub(r"\s+", " ", paper)


def _record(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_synthea_figures_match_the_recorded_comparison(paper):
    record = _record("synthea_comparison.json")
    cbp = record["controlling_high_blood_pressure"]["synthea"]["rate"]
    assert f"{cbp * 100:.1f}%" in paper, "CBP rate drifted from the record"

    dependence = record["dependence"]["synthea"]["mean_deviation"]
    assert f"{dependence:.3f}" in paper, "Synthea dependence deviation drifted"
    assert record["dependence"]["synthea"]["sign_agreement"] in paper

    amputation = record["diabetic_amputation"]["synthea_rate"]
    assert f"{amputation * 100:.2f}%" in paper, "amputation rate drifted"
    assert record["synthea"]["version"] in paper, "the Synthea build is not named"


def test_learned_model_table_matches_the_sweep(paper):
    record = _record("learned_generator_sweep.json")["results"]
    for key, entry in record.items():
        if key.endswith("_full_data"):
            continue
        rate, ratio = entry["p_ge3"], entry["dependence_ratio"]
        assert f"{rate * 100:.1f}%" in paper, f"{key}: P(>=3) {rate:.1%} missing from paper"
        assert f"{ratio:.2f}×" in paper, f"{key}: ratio {ratio} missing from paper"


def test_pysynthea_exclusion_matches_its_assessment(paper):
    record = _record("pysynthea_assessment.json")
    fraction = record["measurability"]["with_value_quantity_fraction"]
    assert f"{fraction * 100:.0f}%" in paper, "the valued-observation fraction drifted"
    assert str(record["hl7_validator"]["errors"]) in paper
    assert str(record["hl7_validator"]["warnings"]) in paper
    assert record["version"] in paper, "the assessed version is not named"


def test_the_conflict_of_interest_is_declared_in_the_abstract(paper):
    """It is declared or the paper is not honest, and the abstract is where it counts.

    Burying it in a footnote would be technically compliant and practically evasive.
    """
    abstract = re.sub(r"\s+", " ", paper.split("## 1. Introduction")[0])
    assert "Conflict of interest" in abstract
    assert "withdrawn" in abstract, "the retraction belongs in the abstract too"


def test_every_negative_result_is_present(flat):
    """The refutations are the paper's distinguishing feature and must not be trimmed.

    A methods paper that reports only what worked is less credible, not more, and these
    four each cost a wrong implementation that was not written.
    """
    for phrase in ("no separable difference", "inverted",
                   "closes about a third", "the wrong direction"):
        assert phrase in flat, f"negative result missing: {phrase!r}"


def test_no_figure_is_quoted_without_a_reference_population(flat):
    """Denominator errors are this project's most repeated mistake.

    NHANES reports blood-pressure control over all hypertensives at <130/80 and HEDIS
    over diagnosed patients at <140/90 — 20.7% and ~70% for the same country. Any paper
    quoting a rate has to say whose.
    """
    assert "ages 45–65" in flat and "stratified by sex" in flat
    assert "not ATP III prevalence" in flat, (
        "the co-occurrence rate must disclaim comparison to published ATP III figures"
    )


def test_reproduction_command_names_a_real_module(paper):
    match = re.search(r"python -m (carebundle[\w.]+)", paper)
    assert match, "the paper gives no reproduction command"
    module = match.group(1).replace("carebundle.", "")
    assert (ROOT / "carebundle" / Path(*module.split("."))).with_suffix(".py").exists(), (
        f"paper names {match.group(1)}, which does not exist"
    )


def test_every_numbered_citation_has_a_reference(flat, paper):
    """A citation marker with no entry is a broken claim.

    Worth a test because a citation in this paper was wrong on the first draft: the
    JAMIA Open amputation result was attributed to the wrong authors, from memory,
    across five documents. Misattributing someone's work is the kind of error a preprint
    cannot recover from, and it was found by checking rather than by rereading.
    """
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", paper)}
    assert cited, "the paper makes no numbered citations"
    references = paper.split("## References", 1)
    assert len(references) == 2, "the paper has no References section"
    listed = {int(m) for m in re.findall(r"^(\d+)\. ", references[1], re.MULTILINE)}
    missing = cited - listed
    assert not missing, f"cited without a reference entry: {sorted(missing)}"


def test_no_reference_names_an_author_the_repository_has_not_verified(paper):
    """Guards the specific mistake made, not the general category.

    'Kartoun' was the wrong attribution for reference 2 and appeared in five files. If it
    reappears anywhere, someone has reintroduced it from the same faulty memory.
    """
    for name in ("Kartoun",):
        assert name not in paper, (
            f"{name!r} is a misattribution corrected on 2026-08-26; reference 2 is "
            "Hodges, Tokunaga and LeGrand"
        )


def test_prior_multivariate_benchmarks_are_cited(flat):
    """The novelty claim depends on these two being described accurately.

    An earlier draft asserted that the field validates marginally. Two 2026 benchmarks
    already score multivariate dependency — SFSF across 17 generators, and a
    PyHealth-based framework across five — and the claim was simply false. A prior-art
    sweep found them two weeks after one of them was posted and before this was.

    The build document's rule is that the sweep runs before every launch, not once. This
    test is the standing version of that rule: the paper may not claim novelty without
    naming what it is novel against.
    """
    assert "SFSF" in flat, "the paper must cite the benchmark that scores 17 generators"
    assert "PyHealth" in flat, "the paper must cite the reproducible-generation framework"
    assert "That framing is withdrawn" in flat, (
        "the retraction of the earlier marginal-validation framing must stay visible"
    )
    # The contribution has to be stated as narrower than 'first benchmark'.
    assert "pairwise is not enough" in flat or "Pairwise validation is necessary" in flat


def test_the_paper_does_not_claim_to_be_first(flat):
    """Guards the specific overclaim that the sweep caught.

    'First reproducible fidelity benchmark' was the framing before SFSF was found. It is
    not recoverable by rewording — it is untrue — so the phrase is banned outright.
    """
    for phrase in ("the first reproducible fidelity benchmark",
                   "first benchmark", "we are the first"):
        assert phrase.lower() not in flat.lower(), f"overclaim reintroduced: {phrase!r}"
