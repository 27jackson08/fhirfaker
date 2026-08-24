"""Measure cross-domain dependence in any FHIR source, against NHANES.

Why this exists
---------------
`BENCHMARK.md` used to rest on an outcome-measure claim that turned out to be false —
Synthea was cited at 0% on blood-pressure control and measures at 74.8%. What survived
that correction was a narrower architectural claim: that a per-condition module graph
represents dependence *within* a condition and not *between* body systems, so a heavier
patient is no likelier to have a low HDL.

That claim is checked here rather than asserted, because the last unchecked competitive
claim in this repository was wrong.

What it measures
----------------
Seven analyte pairs spanning adiposity, glycaemia and lipids, within sex, on patients
aged 45-65, from one contemporaneous panel per patient — the date carrying the most of
the analytes, so weight and lipids are compared as they were measured, not across a
decade of a simulated life. Targets are the committed NHANES extraction, `all` stratum.

Reading the output honestly
---------------------------
* **Deviation, not CI coverage.** A small sample gives wide confidence intervals that
  cover the target by luck; scoring "cells whose CI covers NHANES" rewards having less
  data. Mean absolute deviation is reported instead, and CIs are shown so the reader can
  see how much of a gap is noise.
* **Synthea simulates Massachusetts; NHANES is national.** Correlations are far less
  population-sensitive than prevalences, but this is not a like-for-like population and
  a small part of any gap belongs to that.
* **Pooling adds covariance.** This package fits correlations *within* stratum and then
  mixes profiles into a cohort. A mixture of groups with different means carries
  between-group covariance on top of the within-group value, which is why its pooled
  glucose/triglyceride correlation lands above the pooled NHANES figure it is compared
  to here. That is a real limitation of the comparison, not a fitting error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

NHANES_TARGETS = (
    Path(__file__).resolve().parents[1] / "calibration" / "data" / "nhanes_targets.json"
)

# LOINC to analyte name. Two glucose codes because sources differ on whether the
# specimen is blood or serum/plasma; both are the fasting-ish value the pairs need.
ANALYTE_LOINC = {
    "29463-7": "weight_kg",
    "39156-5": "bmi",
    "2085-9": "hdl",
    "2571-8": "triglycerides",
    "2339-0": "glucose",
    "2345-7": "glucose",
    "4548-4": "hba1c",
}

PAIRS = (
    ("weight_kg", "hdl"),
    ("glucose", "triglycerides"),
    ("glucose", "hdl"),
    ("hba1c", "hdl"),
    ("hba1c", "triglycerides"),
    ("bmi", "hdl"),
    ("triglycerides", "hdl"),
)

AGE_LOW, AGE_HIGH = 45, 65
MIN_PAIRS = 31  # below this a correlation is noise; reported as unmeasurable
_SEX = {"female": "F", "male": "M"}


@dataclass(frozen=True)
class Cell:
    pair: tuple[str, str]
    sex: str
    observed: float
    low: float
    high: float
    target: float
    n: int

    @property
    def deviation(self) -> float:
        return abs(self.observed - self.target)

    @property
    def sign_agrees(self) -> bool:
        return np.sign(self.observed) == np.sign(self.target)


def _age_on(birth: str, iso_date: str) -> int:
    birth_y, birth_m, birth_d = (int(p) for p in birth.split("-"))
    y, m, d = (int(p) for p in iso_date[:10].split("-"))
    return y - birth_y - ((m, d) < (birth_m, birth_d))


def panel_of(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """One contemporaneous analyte panel for a patient, or None.

    Picks the date carrying the most analytes, most recent breaking ties. Comparing
    values measured years apart would understate dependence for a longitudinal source
    and leave a single-visit source unaffected — a bias in favour of this package.
    """
    patient: dict[str, Any] | None = None
    by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        kind = resource.get("resourceType")
        if kind == "Patient" and patient is None:
            patient = resource
        if kind != "Observation":
            continue
        for coding in resource.get("code", {}).get("coding", []):
            name = ANALYTE_LOINC.get(coding.get("code"))
            if not name:
                continue
            value = resource.get("valueQuantity", {}).get("value")
            when = (resource.get("effectiveDateTime") or "")[:10]
            if value is not None and when:
                by_date[when][name] = float(value)
    if not patient or not by_date:
        return None
    birth, sex = patient.get("birthDate"), _SEX.get(patient.get("gender", ""))
    if not birth or not sex:
        return None
    when, values = max(by_date.items(), key=lambda kv: (len(kv[1]), kv[0]))
    if not (AGE_LOW <= _age_on(birth, when) <= AGE_HIGH):
        return None
    return {**values, "sex": sex}


def panels(bundles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in (panel_of(b) for b in bundles) if p]


def _confidence(r: float, n: int) -> tuple[float, float]:
    """Fisher z 95% interval."""
    z, se = np.arctanh(r), 1.0 / np.sqrt(n - 3)
    return float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))


def measure(rows: list[dict[str, Any]]) -> list[Cell]:
    targets = json.loads(NHANES_TARGETS.read_text(encoding="utf-8"))["correlations"]
    cells: list[Cell] = []
    for first, second in PAIRS:
        for sex in ("F", "M"):
            xy = [
                (r[first], r[second])
                for r in rows
                if r["sex"] == sex and first in r and second in r
            ]
            target = targets.get(f"{sex}/all/{first}~{second}", {}).get("pearson")
            if len(xy) < MIN_PAIRS or target is None:
                continue
            r = float(np.corrcoef([p[0] for p in xy], [p[1] for p in xy])[0, 1])
            low, high = _confidence(r, len(xy))
            cells.append(Cell((first, second), sex, r, low, high, target, len(xy)))
    return cells


def render(name: str, cells: list[Cell]) -> str:
    lines = [
        f"{name}: {len(cells)} measurable cells",
        f"{'pair':26} {'sex':4}{'NHANES':>8}{'observed':>10}  {'95% CI':^18}{'dev':>7}",
        "-" * 76,
    ]
    for c in cells:
        lines.append(
            f"{c.pair[0] + ' ~ ' + c.pair[1]:26} {c.sex:4}{c.target:8.3f}"
            f"{c.observed:10.3f}  [{c.low:6.3f},{c.high:6.3f}]{c.deviation:7.3f}"
            + ("" if c.sign_agrees else "  SIGN")
        )
    if cells:
        deviations = [c.deviation for c in cells]
        agree = sum(c.sign_agrees for c in cells)
        lines += [
            "",
            f"  mean |deviation|   {np.mean(deviations):.3f}",
            f"  median |deviation| {np.median(deviations):.3f}",
            f"  worst cell         {max(deviations):.3f}",
            f"  sign agreement     {agree}/{len(cells)}",
        ]
    return "\n".join(lines)


def load_dir(fhir_dir: Path) -> Iterator[dict[str, Any]]:
    for path in sorted(fhir_dir.glob("*.json")):
        if path.name.lower().startswith(("hospital", "practitioner")):
            continue
        try:
            yield json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - corrupt export
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carebundle.benchmark.dependence",
        description="Measure cross-domain analyte dependence against NHANES.",
    )
    parser.add_argument(
        "--fhir-dir", type=Path,
        help="directory of FHIR bundles to measure (e.g. a Synthea export). "
             "Omit to measure this package's own mixed cohort.",
    )
    parser.add_argument("--count", type=int, default=3000,
                        help="cohort size when measuring this package (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if args.fhir_dir:
        if not args.fhir_dir.is_dir():
            print(f"error: {args.fhir_dir} is not a directory", file=sys.stderr)
            return 2
        rows = panels(load_dir(args.fhir_dir))
        label = str(args.fhir_dir)
    else:
        from carebundle.core.bundle import to_json
        from carebundle.generate import generate_cohort

        rows = panels(
            json.loads(to_json(b))
            for b in generate_cohort(count=args.count, seed=args.seed, sex="mixed")
        )
        label = f"carebundle mixed cohort (n={args.count}, seed={args.seed})"

    if not rows:
        print("error: no usable panels found", file=sys.stderr)
        return 1
    print(render(label, measure(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
