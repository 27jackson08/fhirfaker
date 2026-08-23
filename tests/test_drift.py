"""The recorded Synthea comparison, and the documents that quote it.

Every figure in this project that lived in prose and in an artefact has eventually
drifted — five times before this file existed. The competitor comparison is the most
consequential instance yet, because the last version of it was wrong for years, so it is
pinned the same way: the record is the source, `BENCHMARK.md` quotes it, and a test
fails when they disagree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from carebundle.benchmark import drift

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "BENCHMARK.md"


@pytest.fixture(scope="module")
def record():
    return drift.load_record()


def test_the_record_carries_enough_provenance_to_be_rechecked(record):
    """A measurement without its version is the citation problem again.

    'Synthea scores 74.8%' is only better than 'Synthea scores 0%' if a reader can tell
    which Synthea, on what date, from which artefact.
    """
    synthea = record["synthea"]
    assert re.fullmatch(r"[0-9a-f]{7,40}", synthea["version"]), (
        "the recorded Synthea version is not a commit identifier"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", synthea["jar_sha256"])
    assert synthea["build_timestamp"] and synthea["generation"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", record["measured_on"])


def test_benchmark_quotes_the_recorded_figures(record):
    """BENCHMARK.md's headline numbers must come from the record, not from memory."""
    text = BENCHMARK.read_text()
    cbp = record["controlling_high_blood_pressure"]
    for label, rate in (("Synthea", cbp["synthea"]["rate"]),
                        ("carebundle", cbp["carebundle"]["rate"])):
        shown = f"{rate * 100:.1f}%"
        assert shown in text, (
            f"BENCHMARK.md does not quote the recorded {label} CBP rate {shown}"
        )
    for who in ("synthea", "carebundle"):
        shown = f"{record['dependence'][who]['mean_deviation']:.3f}"
        assert shown in text, (
            f"BENCHMARK.md does not quote the recorded {who} mean deviation {shown}"
        )
    assert record["synthea"]["version"] in text, (
        "BENCHMARK.md reports a Synthea figure without naming the build it came from"
    )


def test_the_withdrawn_claim_is_recorded_beside_what_replaced_it(record):
    """Keeping the 0% in the record is deliberate.

    A reader who encounters the old number elsewhere — it was in this repository, in
    commit history, and in a published paper — needs to find it here next to the
    measurement that replaced it, rather than find nothing and assume the paper stands.
    """
    assert record["controlling_high_blood_pressure"]["published_2019_synthea"] == 0.0
    assert record["diabetic_amputation"]["published_2023_claim"] == 1.0
    assert record["diabetic_amputation"]["synthea_rate"] < 0.02


def test_tolerances_are_tight_enough_to_catch_the_error_they_exist_for(record):
    """A tolerance wide enough to hide the original defect is decoration.

    The error this guards against was 74 percentage points. Anything near that width
    would have passed while the documentation was false.
    """
    assert drift.RATE_TOLERANCE <= 0.02
    assert drift.DEVIATION_TOLERANCE <= 0.05


def test_an_empty_denominator_is_not_reported_as_a_rate(tmp_path, record):
    """The terminology trap, guarded.

    Synthea codes conditions in SNOMED. A measure recognising only ICD-10-CM returns an
    empty denominator, and reporting that as 0% would have 'confirmed' the withdrawn
    claim. Drift must call it out as a defect rather than as agreement.
    """
    (tmp_path / "patient.json").write_text(json.dumps({
        "resourceType": "Bundle",
        "entry": [{"resource": {"resourceType": "Patient", "gender": "female",
                                "birthDate": "1970-01-01"}}],
    }))
    problems = drift.check(tmp_path, None, record)
    assert any("not a rate of 0%" in p for p in problems), problems
