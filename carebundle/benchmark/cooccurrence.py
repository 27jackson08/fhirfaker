"""How often do several abnormalities land in the same patient?

Why this exists, and why TSTR did not answer it
-----------------------------------------------
`carebundle.benchmark.dependence` showed Synthea's cross-domain correlations are absent
or backwards. The obvious next question is what that costs, and the obvious instrument
was the Train-on-Synthetic-Test-on-Real task this project already had.

It answered nothing. Measured over ten disjoint folds each, median AUC retention was
92.5% for Synthea and 92.3% here, with overlapping interquartile ranges — **no separable
difference**. The reason is instructive: a logistic model fits one weight per feature, so
it reads each feature's association with the *label* and barely uses the dependence
*between* features. Cross-domain dependence and single-label predictive utility are
dissociable, and a generator can get the first badly wrong while scoring normally on the
second.

A multi-criteria phenotype is the instrument that does depend on it. Asking for three or
more abnormalities *in the same patient* makes the answer a function of how they
co-occur rather than of any single marginal.

**Always report the independence control with the rate.** The hypothesis that motivated
this module — that Synthea would under-produce the phenotype because it draws components
independently — is wrong, and only the control showed it. Synthea's 3-of-4 rate is 4.1%
against a real 19.7%, which looks like exactly the predicted failure. But dividing each
population's observed rate by what its *own* marginals would give under independence:

    NHANES 1.59x      Synthea 2.10x      carebundle 1.45x

Synthea clusters *more* than reality, not less. Its low rate comes from mild marginals —
glucose >= 100 in 8.7% of its patients against 47.4% of real ones — and this is coherent
with `dependence.py`, which found its glucose/triglyceride correlation over-coupled at
roughly double the real value while weight/HDL was absent. Synthea's dependence is not
missing, it is **shaped by module co-membership**: tight inside a module, absent across
them.

Without the control, a correct-looking headline number would have been published with an
inverted mechanism behind it.

What is measured
----------------
Four abnormalities, scored identically on every population:

    BMI >= 30 · triglycerides >= 150 · HDL < 40 (M) / < 50 (F) · glucose >= 100

These are the ATP III metabolic syndrome criteria with waist circumference replaced by
BMI, because neither generator emits a waist measurement. **The resulting rate is
therefore not ATP III metabolic syndrome and is not comparable to a published ATP III
prevalence.** It is an internal yardstick: three populations, one rule, NHANES as the
reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from carebundle.benchmark.dependence import load_dir, panel_of

REQUIRED = ("bmi", "triglycerides", "hdl", "glucose")

BMI_OBESE = 30.0
TRIGLYCERIDES_HIGH = 150.0
HDL_LOW = {"F": 50.0, "M": 40.0}
GLUCOSE_HIGH = 100.0


@dataclass(frozen=True)
class Cooccurrence:
    n: int
    mean_criteria: float
    at_least: dict[int, float]
    marginals: tuple[float, ...]
    independent: dict[int, float]

    def rate(self, k: int) -> float:
        return self.at_least[k]

    def dependence_ratio(self, k: int) -> float:
        """Observed rate divided by what this population's own marginals imply.

        1.0 means the components behave independently. Above 1.0 they cluster. Comparing
        this against the same ratio for real data separates "different marginals" from
        "different dependence", which the raw rate cannot do — and getting that backwards
        is the specific error this module exists to have caught.
        """
        expected = self.independent[k]
        return self.at_least[k] / expected if expected else float("nan")


def criteria_met(row: dict[str, float], sex: str) -> int:
    """How many of the four abnormalities this patient meets.

    HDL is the only strict inequality, matching the clinical definitions: low HDL is
    *below* the threshold while the others are at-or-above.
    """
    return int(
        (row["bmi"] >= BMI_OBESE)
        + (row["triglycerides"] >= TRIGLYCERIDES_HIGH)
        + (row["hdl"] < HDL_LOW[sex])
        + (row["glucose"] >= GLUCOSE_HIGH)
    )


def _flags(row: dict[str, float], sex: str) -> tuple[bool, bool, bool, bool]:
    return (
        row["bmi"] >= BMI_OBESE,
        row["triglycerides"] >= TRIGLYCERIDES_HIGH,
        row["hdl"] < HDL_LOW[sex],
        row["glucose"] >= GLUCOSE_HIGH,
    )


def _independent_rates(marginals: tuple[float, ...]) -> dict[int, float]:
    """P(at least k) if the four criteria were mutually independent.

    Enumerated exactly over the sixteen combinations rather than approximated: with four
    binary components the exact answer is cheap, and this number is the denominator of
    the claim, so an approximation here would be an approximation in the finding.
    """
    rates = {k: 0.0 for k in (1, 2, 3, 4)}
    for bits in product((False, True), repeat=len(marginals)):
        probability = 1.0
        for p, on in zip(marginals, bits, strict=True):
            probability *= p if on else 1.0 - p
        met = sum(bits)
        for k in rates:
            if met >= k:
                rates[k] += probability
    return rates


def measure(rows: Iterable[tuple[dict[str, float], str]]) -> Cooccurrence:
    flags = [_flags(row, sex) for row, sex in rows]
    if not flags:
        return Cooccurrence(0, 0.0, dict.fromkeys((1, 2, 3, 4), 0.0), (),
                            dict.fromkeys((1, 2, 3, 4), 0.0))
    n = len(flags)
    counts = [sum(f) for f in flags]
    marginals = tuple(sum(f[i] for f in flags) / n for i in range(4))
    return Cooccurrence(
        n=n,
        mean_criteria=sum(counts) / n,
        at_least={k: sum(c >= k for c in counts) / n for k in (1, 2, 3, 4)},
        marginals=marginals,
        independent=_independent_rates(marginals),
    )


def rows_from_bundles(bundles: Iterable[dict[str, Any]]):
    """Contemporaneous panels carrying all four analytes, with sex."""
    for bundle in bundles:
        panel = panel_of(bundle)
        if panel and all(k in panel for k in REQUIRED):
            yield panel, panel["sex"]


def render(name: str, result: Cooccurrence) -> str:
    if not result.n:
        return f"  {name} — no usable panels"
    labels = ("BMI>=30", "TG>=150", "low HDL", "glucose>=100")
    lines = [
        f"  {name}  (n={result.n})",
        "    marginals   " + "  ".join(
            f"{lab} {p:.1%}" for lab, p in zip(labels, result.marginals, strict=True)),
        "    mean criteria met " + f"{result.mean_criteria:.2f}",
    ]
    for k in (1, 2, 3, 4):
        lines.append(
            f"    P(>={k})  observed {result.at_least[k]:6.1%}   "
            f"if independent {result.independent[k]:6.1%}   "
            f"ratio {result.dependence_ratio(k):5.2f}x"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carebundle.benchmark.cooccurrence",
        description="Multi-criteria abnormality co-occurrence in any FHIR source.",
    )
    parser.add_argument("--fhir-dir", type=Path,
                        help="directory of FHIR bundles; omit to measure this package")
    parser.add_argument("--count", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if args.fhir_dir:
        if not args.fhir_dir.is_dir():
            print(f"error: {args.fhir_dir} is not a directory", file=sys.stderr)
            return 2
        rows = rows_from_bundles(load_dir(args.fhir_dir))
        label = str(args.fhir_dir)
    else:
        from carebundle.core.bundle import to_json
        from carebundle.generate import generate_cohort

        rows = rows_from_bundles(
            json.loads(to_json(b))
            for b in generate_cohort(count=args.count, seed=args.seed, sex="mixed")
        )
        label = f"carebundle (n={args.count}, seed={args.seed})"

    result = measure(rows)
    if not result.n:
        print("error: no panels carrying all four analytes", file=sys.stderr)
        return 1
    print("Patients meeting N of 4 metabolic abnormalities, ages 45-65\n")
    print(render(label, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
