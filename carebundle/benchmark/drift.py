"""Detect that the measured Synthea comparison has gone stale.

The failure this guards against
-------------------------------
This project asserted for a long time that Synthea scores 0% on Controlling High Blood
Pressure. It came from a 2019 paper, it was false by the time anyone checked, and it
survived because a citation cannot fail in CI.

Replacing it with a measurement fixes nothing on its own: a measurement taken once and
never repeated goes stale exactly the same way, just with a more convincing provenance
attached. So the comparison is recorded with the Synthea build that produced it, and
this module re-runs it and reports what moved.

Two kinds of staleness, and they are different
-----------------------------------------------
* **Synthea published a new build.** The recorded figures describe software nobody runs
  any more. This is not an error in this repository — it is a notice that the numbers
  in `BENCHMARK.md` now have a shelf life.
* **The same build produces different figures.** Either the harness changed behaviour or
  the recorded numbers were wrong. That is a defect here.

The scheduled workflow reports both and fails on either, on the principle that the last
time this repository stopped checking, it was wrong for years.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

RECORD = Path(__file__).resolve().parent / "data" / "synthea_comparison.json"

# A rate is a proportion; a correlation deviation is on the same 0-1 scale. Both move a
# little with the population Synthea happens to generate, so an exact match is the wrong
# test. One point is far tighter than the 74-point error this exists to catch.
RATE_TOLERANCE = 0.01
DEVIATION_TOLERANCE = 0.02


def load_record(path: Path = RECORD) -> dict[str, Any]:
    return json.loads(path.read_text())


def jar_version(jar: Path) -> tuple[str | None, str | None]:
    """(version, build timestamp) from a Synthea JAR, or (None, None).

    Read from the JAR rather than from the download URL, because the URL is
    `master-branch-latest` and says nothing about what it served.
    """
    try:
        with zipfile.ZipFile(jar) as z:
            version = z.read("version.txt").decode().strip()
            manifest = z.read("META-INF/MANIFEST.MF").decode()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"  could not read version from {jar}: {exc}", file=sys.stderr)
        return None, None
    stamp = re.search(r"^Build-Timestamp:\s*(.+)$", manifest, re.MULTILINE)
    return version, (stamp.group(1).strip() if stamp else None)


def _compare(label: str, recorded: float, observed: float, tolerance: float) -> str | None:
    if abs(observed - recorded) <= tolerance:
        print(f"  ok    {label:44} {recorded:.3f} -> {observed:.3f}")
        return None
    print(f"  DRIFT {label:44} {recorded:.3f} -> {observed:.3f}")
    return f"{label}: recorded {recorded:.3f}, measured {observed:.3f}"


def check(fhir_dir: Path, jar: Path | None, record: dict[str, Any]) -> list[str]:
    """Re-measure and return a list of human-readable drift descriptions."""
    from carebundle.benchmark.cqm import MEASURES, MeasureResult
    from carebundle.benchmark.dependence import measure, panel_of
    from carebundle.benchmark.synthea import load_bundles

    problems: list[str] = []

    if jar is not None:
        version, stamp = jar_version(jar)
        expected = record["synthea"]["version"]
        if version and version != expected:
            print(f"  NEW   Synthea build {expected} -> {version} (built {stamp})")
            problems.append(
                f"Synthea has published {version} (built {stamp}); the recorded "
                f"comparison describes {expected} and BENCHMARK.md may be stale"
            )
        elif version:
            print(f"  ok    Synthea build {version} unchanged")

    # One streaming pass feeding both measures. Both obvious alternatives are worse, and
    # this was measured rather than reasoned: parsing the directory once per measure
    # doubles the work, while materialising the population into a list to share it holds
    # ~1,500 lifetime bundles of ~1,000 resources at once and did not finish inside ten
    # minutes on the machine this was written on. Streaming the same population runs in
    # **51 seconds**. Each bundle is decoded once, contributes to both measures, and is
    # released. This job has to stay cheap enough that nobody turns it off.
    numerator = denominator = 0
    rows: list[dict[str, Any]] = []
    count = 0
    for bundle in load_bundles(fhir_dir):
        count += 1
        in_denominator, in_numerator = MEASURES["controlling_high_blood_pressure"](bundle)
        denominator += in_denominator
        numerator += in_numerator
        panel = panel_of(bundle)
        if panel:
            rows.append(panel)
    print(f"  read  {count} bundles")

    result = MeasureResult(
        measure="controlling_high_blood_pressure",
        numerator=numerator,
        denominator=denominator,
    )
    if result.denominator == 0:
        # The terminology trap. An empty denominator is not a rate of zero, and treating
        # it as one is how the original error would come back.
        problems.append(
            "CBP denominator is empty — the export codes conditions in a vocabulary the "
            "measure does not recognise. This is not a rate of 0%."
        )
        print("  DRIFT CBP denominator empty — not a rate of zero")
    else:
        problems.extend(filter(None, [_compare(
            "CBP rate (Synthea)",
            record["controlling_high_blood_pressure"]["synthea"]["rate"],
            result.rate, RATE_TOLERANCE,
        )]))

    cells = measure(rows)
    if cells:
        observed = sum(c.deviation for c in cells) / len(cells)
        problems.extend(filter(None, [_compare(
            "dependence mean |deviation| (Synthea)",
            record["dependence"]["synthea"]["mean_deviation"],
            observed, DEVIATION_TOLERANCE,
        )]))
    else:
        problems.append("no measurable dependence cells in the export")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carebundle.benchmark.drift",
        description="Re-run the recorded Synthea comparison and report what moved.",
    )
    parser.add_argument("--fhir-dir", type=Path, required=True,
                        help="freshly generated Synthea export directory")
    parser.add_argument("--jar", type=Path,
                        help="the synthea JAR, to compare build versions")
    args = parser.parse_args(argv)

    if not args.fhir_dir.is_dir():
        print(f"error: {args.fhir_dir} is not a directory", file=sys.stderr)
        return 2

    record = load_record()
    print(f"Recorded comparison from {record['measured_on']}, "
          f"Synthea {record['synthea']['version']}\n")
    problems = check(args.fhir_dir, args.jar, record)

    print()
    if not problems:
        print("No drift. BENCHMARK.md still describes the software it claims to.")
        return 0
    print("The recorded comparison no longer holds:\n")
    for p in problems:
        print(f"  - {p}")
    print(
        "\nRe-measure, update carebundle/benchmark/data/synthea_comparison.json and the\n"
        "figures in BENCHMARK.md, and say in the changelog that a competitor's number\n"
        "moved. Do not quietly widen the tolerance."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
