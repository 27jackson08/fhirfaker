"""The multi-generator suite.

Comparing generators used to mean running three modules separately and assembling the
table by hand, which is how a figure ends up in a document that no longer matches the
code — a failure this project has had five times. The suite produces the table as one
artefact instead.
"""

from __future__ import annotations

import csv

import pytest

from carebundle.benchmark import suite


def _write_records(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bmi", "triglycerides", "hdl", "glucose", "sex"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_scores_a_records_file(tmp_path):
    """The tabular path is what admitted a learned generator to the benchmark."""
    rows = []
    for i in range(400):
        heavy = i % 3 == 0
        rows.append({
            "bmi": 33.0 if heavy else 24.0,
            "triglycerides": 190.0 if heavy else 95.0,
            "hdl": 36.0 if heavy else 62.0,
            "glucose": 112.0 if heavy else 90.0,
            "sex": "M" if i % 2 else "F",
        })
    path = _write_records(tmp_path / "gen.csv", rows)
    panels, scored = suite._from_records(path)
    row = suite._score("probe", panels, scored)
    assert row is not None
    assert row.n == 400
    # Perfectly co-varying inputs must show as clustering far above independence.
    assert row.ratio > 1.5, row.ratio


def test_a_source_with_no_usable_patients_is_skipped_not_zeroed(tmp_path, capsys):
    """An empty source is not a score of zero.

    Reporting it as 0% is the same defect as reporting an empty measure denominator as a
    0% rate, which is how the withdrawn Synthea claim would have come back looking
    confirmed.
    """
    path = _write_records(tmp_path / "empty.csv", [
        {"bmi": "", "triglycerides": "", "hdl": "", "glucose": "", "sex": "F"},
    ])
    panels, scored = suite._from_records(path)
    assert suite._score("empty", panels, scored) is None
    assert "no usable patients" in capsys.readouterr().err


def test_render_always_shows_the_independence_ratio():
    """A co-occurrence rate without its control is unreadable.

    Synthea's 4.1% looks like missing dependence and is not — it clusters more than
    reality. The rate and the ratio have to travel together or the table misleads.
    """
    rendered = suite.render([
        suite.Row("alpha", 100, 0.05, "14/14", 0.15, 1.5),
        suite.Row("beta", 200, None, None, 0.04, 2.1),
    ])
    assert "1.50x" in rendered and "2.10x" in rendered
    assert "15.0%" in rendered and "4.0%" in rendered
    assert "under independence" in rendered
    # A source without correlation cells still renders rather than crashing.
    assert "n/a" in rendered


@pytest.mark.parametrize("bad", ["nolabel", "=path", ""])
def test_rejects_malformed_source_arguments(bad):
    if bad == "=path":
        pytest.skip("an empty label is permitted; the path is what matters")
    with pytest.raises(SystemExit):
        suite._pairs([bad], "--fhir")
