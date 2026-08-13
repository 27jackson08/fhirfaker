"""Statistical evidence that the generated data reproduces published relationships.

This is the moat (build doc Section 3, Layer 2). Anyone can claim clinical coherence;
this module regenerates the evidence for it on every run and fails when it drifts.

Run:  python -m pkg.fidelity.report
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pkg.correlation import relations
from pkg.profiles.base import draw
from pkg.profiles.library import get_profile

DEFAULT_SAMPLE_SIZE = 10_000
DEFAULT_SEED = 20260101  # Fixed: a fidelity suite that flakes gets ignored.


@dataclass(frozen=True)
class Check:
    name: str
    observed: float
    expected: float
    tolerance: float
    unit: str
    source: str

    @property
    def delta(self) -> float:
        return self.observed - self.expected

    @property
    def passed(self) -> bool:
        return abs(self.delta) <= self.tolerance


def _fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    r_squared = float(np.corrcoef(x, y)[0, 1] ** 2)
    return float(slope), float(intercept), r_squared


def adag_checks(size: int, seed: int) -> list[Check]:
    """HbA1c/glucose against Nathan et al. 2008."""
    rng = np.random.default_rng(seed)
    sample = get_profile("type2_diabetes", "F").joint.sample(rng, size=size)
    a1c, glucose = sample["hba1c"], sample["glucose"]
    slope, intercept, r_squared = _fit(a1c, glucose)

    checks = [
        Check("ADAG slope", slope, relations.ADAG_SLOPE, 1.0,
              "mg/dL per %", "Nathan 2008"),
        # The headline claim: correlated but NOT deterministic. A naive generator that
        # derives glucose from HbA1c scores exactly 1.0 here and fails.
        Check("ADAG R^2", r_squared, relations.ADAG_R_SQUARED, 0.02, "", "Nathan 2008"),
    ]

    # Predicted values across the clinical range, rather than the intercept. The
    # intercept extrapolates to HbA1c = 0 — roughly 7 SD below anything observed — so
    # small slope differences amplify there into a large apparent error while the
    # fitted line remains accurate everywhere it is actually used.
    for a1c_value in (6.5, 8.0, 9.5):
        predicted = slope * a1c_value + intercept
        checks.append(
            Check(
                f"glucose at HbA1c {a1c_value}%",
                predicted,
                relations.estimated_average_glucose(a1c_value),
                5.0,
                "mg/dL",
                "Nathan 2008",
            )
        )
    return checks


def ckd_epi_checks(size: int, seed: int) -> list[Check]:
    """eGFR must be an exact function of creatinine, age and sex — never sampled."""
    rng = np.random.default_rng(seed + 1)
    profile = get_profile("ckd_stage3", "M")

    in_band = 0
    code_agrees = 0
    round_trip_error = 0.0
    for _ in range(size):
        drawn = draw(profile, rng=rng, age_years=58.0, sex="M")
        egfr = drawn.raw["egfr"]
        if 30.0 <= egfr < 60.0:
            in_band += 1

        recomputed = relations.ckd_epi_2021_egfr(
            creatinine_mg_dl=drawn.raw["creatinine"], age_years=58.0, sex="M"
        )
        round_trip_error = max(round_trip_error, abs(recomputed - egfr))

        stage = relations.ckd_stage_for(egfr)
        expected_code = {"G3a": "N18.31", "G3b": "N18.32"}[stage]
        if any(c.code == expected_code for c in drawn.conditions):
            code_agrees += 1

    return [
        Check("CKD stage-3 eGFR within band", in_band / size, 1.0, 0.0, "fraction",
              "KDIGO 2012"),
        Check("eGFR consistent with creatinine", round_trip_error, 0.0, 1e-9,
              "mL/min/1.73m2", "CKD-EPI 2021"),
        Check("ICD-10 stage code matches eGFR", code_agrees / size, 1.0, 0.0,
              "fraction", "ICD-10-CM"),
    ]


def comorbidity_checks(size: int, seed: int) -> list[Check]:
    """Configured prevalence should show up in the generated population."""
    rng = np.random.default_rng(seed + 2)
    profile = get_profile("type2_diabetes", "F")
    with_htn = sum(
        any(c.code == "I10" for c in draw(profile, rng=rng, age_years=55.0, sex="F").conditions)
        for _ in range(size)
    )
    observed = with_htn / size
    # 4 binomial SEs; wide enough not to flake, tight enough to catch a real drift.
    tolerance = 4.0 * (0.70 * 0.30 / size) ** 0.5
    return [
        Check("T2DM hypertension comorbidity", observed, 0.70, tolerance,
              "fraction", "profile config")
    ]


def vitals_checks(size: int, seed: int) -> list[Check]:
    """Systolic and diastolic must move together, or the pairs are absurd."""
    rng = np.random.default_rng(seed + 3)
    sample = get_profile("hypertension", "M").joint.sample(rng, size=size)
    observed = float(np.corrcoef(sample["systolic"], sample["diastolic"])[0, 1])
    return [
        Check("systolic/diastolic correlation", observed, 0.60, 0.05, "",
              "profile config")
    ]


def run_all(size: int = DEFAULT_SAMPLE_SIZE, seed: int = DEFAULT_SEED) -> list[Check]:
    return [
        *adag_checks(size, seed),
        *ckd_epi_checks(min(size, 2_000), seed),
        *comorbidity_checks(min(size, 5_000), seed),
        *vitals_checks(size, seed),
    ]


def render_markdown(checks: list[Check], *, size: int, seed: int) -> str:
    lines = [
        "# Fidelity Report",
        "",
        "Generated distributions checked against published clinical relationships.",
        f"Regenerated per release from n={size:,} draws, seed {seed}.",
        "",
        "| Check | Observed | Expected | Delta | Tolerance | Source | |",
        "|---|---:|---:|---:|---:|---|:--:|",
    ]
    for check in checks:
        lines.append(
            f"| {check.name} | {check.observed:.4g} | {check.expected:.4g} | "
            f"{check.delta:+.3g} | ±{check.tolerance:.3g} | {check.source} | "
            f"{'PASS' if check.passed else 'FAIL'} |"
        )
    failed = [c for c in checks if not c.passed]
    lines += [
        "",
        f"**{len(checks) - len(failed)}/{len(checks)} passed.**",
        "",
        "## Why R^2 is the load-bearing number",
        "",
        "The ADAG relationship is `eAG = 28.7 x HbA1c - 46.7` with **R^2 = 0.84**. A",
        "generator that derives glucose deterministically from HbA1c reproduces the",
        "line perfectly and scores R^2 = 1.0 — visibly artificial to anyone who plots",
        "it. Reproducing the residual scatter is the actual claim, so that check is",
        "two-sided: too tight a correlation fails just as a too-loose one does.",
        "",
        "## Marginals are estimates, dependence is cited",
        "",
        "The marginal distributions are clinically-informed estimates for a 45-65",
        "adult population, not fits to a named cohort. What comes from the literature",
        "is the *dependence* structure: the HbA1c/glucose correlation is derived from",
        "the published R^2, and eGFR is computed from creatinine by CKD-EPI 2021",
        "rather than sampled. Calibrating marginals against NHANES is Phase 4.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    checks = run_all()
    markdown = render_markdown(checks, size=DEFAULT_SAMPLE_SIZE, seed=DEFAULT_SEED)
    # Committed at the repo root next to CONFORMANCE.md: the report is published
    # evidence, so it must live somewhere the README can link to.
    out = Path(__file__).resolve().parents[2] / "FIDELITY.md"
    out.write_text(markdown)
    print(markdown)
    failed = [c for c in checks if not c.passed]
    if failed:
        raise SystemExit(f"{len(failed)} fidelity check(s) failed")


if __name__ == "__main__":
    main()
