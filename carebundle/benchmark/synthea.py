"""Run this project's quality measures against a Synthea export.

Why this exists
---------------
`BENCHMARK.md` used to compare this package against a **published** Synthea figure —
the 0% blood-pressure control reported by Chen et al. in 2019. That is a citation, not
a measurement, and it was seven years old. Citing a competitor's worst published number
indefinitely is the kind of claim this project exists not to make.

So it is measured instead. Point this module at a Synthea FHIR export and it runs the
same `carebundle.benchmark.cqm` code that scores this package's own output. One
implementation sees both, which is the only way the two numbers mean the same thing.

The first run refuted the claim: current Synthea scores **74.8%** on CBP, not 0%.

Getting a population to measure
-------------------------------
Synthea is not vendored — it is a 197 MB JAR belonging to MITRE, and a stale copy here
would be worse than none, exactly as with the NHANES files::

    curl -sSL -o synthea.jar \\
      https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
    java -jar synthea.jar -p 1200 -s 42 -a 18-85 \\
      --exporter.fhir.export=true \\
      --exporter.hospital.fhir.export=false \\
      --exporter.practitioner.fhir.export=false \\
      --exporter.baseDirectory=./pop
    python -m carebundle.benchmark.synthea --fhir-dir ./pop/fhir

Two differences between the generators matter to a measure, and both are handled in
`cqm` rather than here, because they are corrections rather than adapters:

* **Terminology.** Synthea codes conditions in SNOMED CT; this package emits ICD-10-CM
  and cannot ship SNOMED. A measure recognising only one vocabulary scores the other at
  zero — and would have "reproduced" the 2019 finding for entirely the wrong reason.
* **Shape.** Synthea emits a lifetime, this package a visit. "Most recent blood
  pressure" therefore has to mean latest by date, and "aged 18-85" has to mean age at
  that reading rather than at the first encounter in the file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from carebundle.benchmark.cqm import MEASURES, run_measure

# Synthea writes provider directories into the same folder as patients. They carry no
# Patient resource, so they would not enter a denominator anyway, but skipping them by
# name keeps the reported bundle count meaning "patients".
NON_PATIENT_PREFIXES = ("hospital", "practitioner")


def load_bundles(fhir_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield each patient bundle in a Synthea FHIR export directory."""
    for path in sorted(fhir_dir.glob("*.json")):
        if path.name.lower().startswith(NON_PATIENT_PREFIXES):
            continue
        try:
            yield json.loads(path.read_text())
        except json.JSONDecodeError as exc:  # pragma: no cover - corrupt export
            print(f"  skipped {path.name}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carebundle.benchmark.synthea",
        description="Run carebundle's quality measures against a Synthea FHIR export.",
    )
    parser.add_argument(
        "--fhir-dir", type=Path, required=True,
        help="Synthea export directory, usually <baseDirectory>/fhir",
    )
    parser.add_argument(
        "--measure", default="controlling_high_blood_pressure",
        choices=sorted(MEASURES),
        help="measure to evaluate (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if not args.fhir_dir.is_dir():
        print(f"error: {args.fhir_dir} is not a directory", file=sys.stderr)
        return 2

    bundles = list(load_bundles(args.fhir_dir))
    if not bundles:
        print(f"error: no patient bundles found in {args.fhir_dir}", file=sys.stderr)
        return 1

    result = run_measure(args.measure, bundles)
    print(f"Synthea export: {args.fhir_dir}")
    print(f"  bundles read   {len(bundles)}")
    print(f"  measure        {result.measure}")
    print(f"  denominator    {result.denominator}")
    print(f"  numerator      {result.numerator}")
    if result.denominator == 0:
        # The failure mode this whole module was written to avoid. An empty denominator
        # is not a rate of zero, and reporting it as one is how a terminology mismatch
        # gets published as a clinical finding.
        print("  rate           n/a — empty denominator, not 0%")
        print("\n  An empty denominator usually means the export codes conditions in a")
        print("  vocabulary the measure does not recognise. Check cqm.HYPERTENSION_SNOMED.")
        return 1
    print(f"  rate           {result.rate:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
