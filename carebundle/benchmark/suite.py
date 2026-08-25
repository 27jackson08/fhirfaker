"""One command, one table: score any set of generators on the same measures.

Why a suite rather than four modules
------------------------------------
`dependence`, `cooccurrence` and `cqm` each answer one question, and each was written to
answer it about one source at a time. Comparing generators meant running them separately
and assembling the table by hand, which is how a figure ends up in a document that no
longer matches the code — a failure this project has already had five times.

This runs them together, over as many sources as you name, and prints the comparison as
a single artefact.

Sources
-------
FHIR, for generators that emit it::

    python -m carebundle.benchmark.suite --fhir Synthea=./pop/fhir

Records, for the tabular family — CTGAN, TVAE, copula and diffusion models — which
produce a row per patient and would otherwise need an adapter written only to be parsed
back out::

    python -m carebundle.benchmark.suite --records CTGAN=./ctgan.csv

This package is always included as a reference row unless `--no-self` is passed. It is
not the standard: NHANES is, and the point of the table is distance from it.

Reading the output
------------------
**The independence ratio is not optional.** A co-occurrence rate on its own is
unreadable: a generator can produce too few multi-criteria patients because its
components are independent, or because its marginals are mild, and those need opposite
fixes. Synthea's 4.1% looks like missing dependence and is not — it clusters *more* than
reality at 2.10x, and the low rate comes from a glucose marginal that is abnormal in 8.7%
of its patients against 47.4% of real ones. Every row here prints both.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from carebundle.benchmark import cooccurrence as co
from carebundle.benchmark.dependence import load_dir, panels
from carebundle.benchmark.dependence import measure as measure_dependence


@dataclass(frozen=True)
class Row:
    label: str
    n: int
    dependence: float | None
    sign: str | None
    rate3: float
    ratio: float


def _from_fhir(path: Path) -> tuple[list, list]:
    bundles = list(load_dir(path))
    return panels(bundles), list(co.rows_from_bundles(bundles))


def _from_records(path: Path) -> tuple[list, list]:
    with path.open(encoding="utf-8", newline="") as handle:
        records = [dict(r) for r in csv.DictReader(handle)]
    rows = list(co.rows_from_records(records))
    # The dependence measure wants panels keyed by analyte with a `sex` field.
    panels_ = [{**panel, "sex": sex} for panel, sex in rows]
    return panels_, rows


def _score(label: str, panels_: list, rows: list) -> Row | None:
    if not rows:
        print(f"  {label}: no usable patients — skipped", file=sys.stderr)
        return None
    cells = measure_dependence(panels_)
    result = co.measure(rows)
    return Row(
        label=label,
        n=result.n,
        dependence=float(np.mean([c.deviation for c in cells])) if cells else None,
        sign=(f"{sum(c.sign_agrees for c in cells)}/{len(cells)}" if cells else None),
        rate3=result.rate(3),
        ratio=result.dependence_ratio(3),
    )


def _self_rows(count: int, seed: int) -> tuple[list, list]:
    from carebundle.core.bundle import to_json
    from carebundle.generate import generate_cohort

    bundles = [json.loads(to_json(b))
               for b in generate_cohort(count=count, seed=seed, sex="mixed")]
    return panels(bundles), list(co.rows_from_bundles(bundles))


def render(rows: Iterable[Row]) -> str:
    lines = [
        f"{'generator':30}{'n':>7}{'dep |dev|':>11}{'sign':>8}{'P(>=3)':>9}{'ratio':>8}",
        "-" * 73,
    ]
    for r in rows:
        dep = f"{r.dependence:.3f}" if r.dependence is not None else "  n/a"
        lines.append(
            f"{r.label:30}{r.n:7}{dep:>11}{(r.sign or 'n/a'):>8}"
            f"{r.rate3:9.1%}{r.ratio:7.2f}x"
        )
    lines += [
        "",
        "  dep |dev|  mean absolute deviation from the NHANES correlation targets",
        "  ratio      observed co-occurrence / what this population's own marginals imply",
        "             under independence. 1.00 = independent. Real NHANES is 1.76x.",
    ]
    return "\n".join(lines)


def _pairs(values: list[str], flag: str) -> list[tuple[str, Path]]:
    out = []
    for item in values:
        if "=" not in item:
            raise SystemExit(f"error: {flag} wants LABEL=PATH, got {item!r}")
        label, _, path = item.partition("=")
        out.append((label, Path(path)))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carebundle.benchmark.suite",
        description="Score generators on shared fidelity measures and print one table.",
    )
    parser.add_argument("--fhir", action="append", default=[], metavar="LABEL=DIR",
                        help="a directory of FHIR bundles (repeatable)")
    parser.add_argument("--records", action="append", default=[], metavar="LABEL=CSV",
                        help="a CSV of per-patient records (repeatable)")
    parser.add_argument("--no-self", action="store_true",
                        help="omit this package's reference row")
    parser.add_argument("--count", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    scored: list[Row] = []
    for label, path in _pairs(args.fhir, "--fhir"):
        if not path.is_dir():
            print(f"error: {path} is not a directory", file=sys.stderr)
            return 2
        scored.append(_score(label, *_from_fhir(path)))
    for label, path in _pairs(args.records, "--records"):
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            return 2
        scored.append(_score(label, *_from_records(path)))
    if not args.no_self:
        scored.append(_score(f"carebundle (n={args.count})",
                             *_self_rows(args.count, args.seed)))

    present = [r for r in scored if r is not None]
    if not present:
        print("error: nothing scorable", file=sys.stderr)
        return 1
    print(render(present))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
