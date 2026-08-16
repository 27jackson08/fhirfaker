"""Statistical evidence that the generated data reproduces published relationships.

This is the moat (build doc Section 3, Layer 2). Anyone can claim clinical coherence;
this module regenerates the evidence for it on every run and fails when it drifts.

Run:  python -m carebundle.fidelity.report
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from carebundle.correlation import relations
from carebundle.profiles import library
from carebundle.profiles.base import draw
from carebundle.profiles.library import get_profile

DEFAULT_SAMPLE_SIZE = 10_000
DEFAULT_SEED = 20260101  # Fixed: a fidelity suite that flakes gets ignored.


# How much a passing check actually proves. These are not equivalent, and a flat
# "37/37 passed" implies far stronger evidence than most of them carry — which is the
# exact criticism levelled at synthetic-data evaluation in arXiv:2606.08903, that
# statistical-similarity reporting is dominated by measures which do not establish
# clinical validity. Grading them is cheap and makes the report honest.
EVIDENCE = {
    "identity": (
        "Computed from its own inputs. Cannot fail unless the code is broken, so it is "
        "a regression test, not evidence of fidelity."
    ),
    "round_trip": (
        "Verifies the sampler reproduces a value it was configured with. Proves the "
        "engine works; proves nothing about whether the configured value is right."
    ),
    "calibration": (
        "Verifies a marginal fitted to a published source survived truncation and the "
        "copula. Meaningful — this is where truncation attenuation was caught — but "
        "in-sample by construction."
    ),
    "out_of_sample": (
        "A published relationship the model was NOT fitted to. This is the only "
        "category that is evidence of fidelity in the sense the word implies."
    ),
}


@dataclass(frozen=True)
class Check:
    name: str
    observed: float
    expected: float
    tolerance: float
    unit: str
    source: str
    # Defaults to the conservative middle grade. Anything claiming to be out_of_sample
    # has to say so explicitly, because that is the claim worth over-stating and the
    # one a reader will lean on.
    evidence: str = "calibration"

    def __post_init__(self) -> None:
        if self.evidence not in EVIDENCE:
            raise ValueError(
                f"unknown evidence grade {self.evidence!r}; known: {sorted(EVIDENCE)}"
            )

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
              "KDIGO 2012", evidence="round_trip"),
        Check("eGFR consistent with creatinine", round_trip_error, 0.0, 1e-9,
              "mL/min/1.73m2", "CKD-EPI 2021", evidence="identity"),
        Check("ICD-10 stage code matches eGFR", code_agrees / size, 1.0, 0.0,
              "fraction", "ICD-10-CM", evidence="identity"),
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
        Check("T2DM hypertension comorbidity", observed,
              library.T2DM_HYPERTENSION_PREVALENCE_BY_SEX["F"], tolerance,
              "fraction", "NHANES 2017-2020", evidence="calibration")
    ]


def vitals_checks(size: int, seed: int) -> list[Check]:
    """Systolic and diastolic must move together, or the pairs are absurd."""
    rng = np.random.default_rng(seed + 3)
    sample = get_profile("hypertension", "M").joint.sample(rng, size=size)
    observed = float(np.corrcoef(sample["systolic"], sample["diastolic"])[0, 1])
    return [
        Check("systolic/diastolic correlation", observed,
              library.BP_CORRELATION_BY_SEX["M"], 0.06, "",
              "NHANES 2017-2020", evidence="calibration")
    ]


def lipid_checks(size: int, seed: int) -> list[Check]:
    """The lipid panel must be internally consistent and clinically patterned."""
    rng = np.random.default_rng(seed + 4)
    profile = get_profile("type2_diabetes", "M")

    worst_error = 0.0
    for _ in range(size):
        drawn = draw(profile, rng=rng, age_years=55.0, sex="M")
        expected = relations.friedewald_ldl(
            total_cholesterol=drawn.raw["cholesterol_total"],
            hdl=drawn.raw["hdl"],
            triglycerides=drawn.raw["triglycerides"],
        )
        worst_error = max(worst_error, abs(expected - drawn.raw["ldl"]))

    sample = profile.joint.sample(np.random.default_rng(seed + 5), size=size)
    tg_hdl = float(np.corrcoef(sample["triglycerides"], sample["hdl"])[0, 1])

    return [
        Check("LDL consistent with panel (Friedewald)", worst_error, 0.0, 1e-9,
              "mg/dL", "Friedewald 1972", evidence="identity"),
        # Inverse by construction: high-triglyceride/high-HDL patients barely exist.
        Check("triglyceride/HDL correlation", tg_hdl,
              library.TG_HDL_CORRELATION_BY_SEX["M"], 0.06, "",
              "NHANES 2017-2020", evidence="calibration"),
    ]


def anthropometric_checks(size: int, seed: int) -> list[Check]:
    """BMI must follow from height and weight, and differ by profile."""
    rng = np.random.default_rng(seed + 6)

    worst_error = 0.0
    obese = 0
    drawn_count = 0
    # Both sexes: the weight marginals differ, so a single-sex sample would not
    # describe the population the profile actually generates.
    for sex in ("F", "M"):
        diabetic = get_profile("type2_diabetes", sex)
        for _ in range(size // 2):
            drawn = draw(diabetic, rng=rng, age_years=55.0, sex=sex)
            expected = relations.body_mass_index(
                weight_kg=drawn.raw["weight_kg"], height_cm=drawn.raw["height_cm"]
            )
            worst_error = max(worst_error, abs(expected - drawn.raw["bmi"]))
            obese += drawn.raw["bmi"] >= relations.OBESITY_BMI_THRESHOLD
            drawn_count += 1

    healthy_profile = get_profile("healthy", "F")
    healthy_bmi = np.median([
        draw(healthy_profile, rng=rng, age_years=55.0, sex="F").raw["bmi"]
        for _ in range(size)
    ])

    return [
        Check("BMI consistent with height and weight", worst_error, 0.0, 1e-9,
              "kg/m2", "WHO", evidence="identity"),
        # Both figures are measured from NHANES 45-65, not chosen. They previously
        # sat at 0.60 and 26.5 — my own estimates — and calibrating the marginals
        # made the suite flag the disagreement. The data is the authority here, so
        # the expectations moved to it rather than the marginals being bent back.
        Check("diabetic obesity rate", obese / drawn_count, 0.612, 0.05, "fraction",
              "NHANES 2017-2020"),
        Check("typical-adult median BMI", float(healthy_bmi), 28.8, 1.5, "kg/m2",
              "NHANES 2017-2020"),
    ]


NHANES_TARGETS = (
    Path(__file__).resolve().parents[1] / "calibration" / "data" / "nhanes_targets.json"
)

# Analytes calibrated per stratum, and how far the generated median may drift from
# the NHANES one. Tolerances are relative, sized to be loose enough that the copula's
# dependence structure does not trip them and tight enough to catch a real change.
NHANES_CHECKS = (
    ("healthy", "nondiabetic", "hba1c", 0.03),
    ("healthy", "nondiabetic", "triglycerides", 0.12),
    ("healthy", "nondiabetic", "cholesterol_total", 0.06),
    ("healthy", "nondiabetic", "hdl", 0.08),
    ("healthy", "nondiabetic", "creatinine", 0.08),
    ("healthy", "nondiabetic", "weight_kg", 0.06),
    ("healthy", "nondiabetic", "height_cm", 0.02),
    # HbA1c is checked against the `diagnosed` stratum (DIQ010 == 1) because that is
    # the population the profile now draws from and the one an `E11.9` code denotes.
    ("type2_diabetes", "diagnosed", "hba1c", 0.05),
    # The rest still reference the lab-defined `diabetic` stratum, which is where their
    # marginals came from. Deliberate rather than overlooked: between the two strata
    # these medians differ by 1-5%, comfortably inside the tolerances below, so
    # re-deriving them would churn every golden file to move numbers that no check can
    # distinguish. HbA1c was the one where the definition genuinely mattered — it moved
    # the median 7.4 to 7.1 and added the entire sub-6.5 quarter of the population.
    ("type2_diabetes", "diabetic", "triglycerides", 0.12),
    ("type2_diabetes", "diabetic", "hdl", 0.08),
    ("type2_diabetes", "diabetic", "weight_kg", 0.08),
)


def nhanes_checks(size: int, seed: int) -> list[Check]:
    """Generated marginals against the NHANES medians they were calibrated to.

    Reads a committed targets file rather than the network, so the check runs
    offline. Regenerate it with `carebundle/calibration/nhanes.py` when the source release
    changes — and expect this to fail if it does, which is the point.
    """
    if not NHANES_TARGETS.exists():
        return []
    targets = json.loads(NHANES_TARGETS.read_text())["strata"]

    checks = []
    for profile_key, stratum, analyte, tolerance in NHANES_CHECKS:
        for sex in ("F", "M"):
            key = f"{sex}/{stratum}/{analyte}"
            if key not in targets:
                continue
            expected = targets[key]["median"]
            rng = np.random.default_rng([seed, 7, hash_free_index(analyte, sex)])
            drawn = [
                draw(get_profile(profile_key, sex), rng=rng, age_years=55.0, sex=sex)
                for _ in range(size)
            ]
            values = [d.raw[analyte] for d in drawn if analyte in d.raw]
            if not values:
                continue
            checks.append(
                Check(
                    f"{analyte} median ({profile_key}/{sex})",
                    float(np.median(values)),
                    expected,
                    abs(expected) * tolerance,
                    "",
                    "NHANES 2017-2020",
                )
            )
    return checks


def hash_free_index(analyte: str, sex: str) -> int:
    """A stable per-check stream id. Python's hash() is salted per process."""
    from carebundle.core.ids import stable_digest

    return stable_digest(f"{analyte}:{sex}", bits=16)


def quality_measure_checks(size: int, seed: int) -> list[Check]:
    """CMS/HEDIS Controlling High Blood Pressure — the one out-of-sample check.

    Everything else in this report is in-sample: identities verify their own formula,
    round-trips verify the sampler reproduces a configured value, and the NHANES
    medians verify that a marginal fitted to NHANES survived truncation. None of them
    can tell you the model is *right*, only that it is self-consistent.

    This one can. The inputs are NHANES treatment prevalence and Law 2003 effect sizes;
    the control rate is not fitted to anything, and it is checked against a rate
    published by somebody else. Synthea scores 0% on the same measure. `BENCHMARK.md`
    is the authoritative version — it computes the measure from emitted FHIR rather
    than from draws — and this row exists so the report says out loud that it has
    exactly one such check.
    """
    rng = np.random.default_rng(seed + 6)
    profile = get_profile("hypertension", "F")
    controlled = 0
    for _ in range(size):
        drawn = draw(profile, rng=rng, age_years=58.0, sex="F")
        if drawn.raw["systolic"] < 140.0 and drawn.raw["diastolic"] < 90.0:
            controlled += 1
    # Band spans the published US (69.7%) and Massachusetts (74.5%) comparators, plus
    # room for sampling noise. Wide on purpose: a fidelity suite that flakes is ignored.
    return [
        Check(
            "CMS Controlling High Blood Pressure",
            controlled / size,
            0.72,
            0.09,
            "fraction",
            "Chen 2019 (CMS/HEDIS)",
            evidence="out_of_sample",
        )
    ]


def run_all(size: int = DEFAULT_SAMPLE_SIZE, seed: int = DEFAULT_SEED) -> list[Check]:
    return [
        *adag_checks(size, seed),
        *ckd_epi_checks(min(size, 2_000), seed),
        *comorbidity_checks(min(size, 5_000), seed),
        *vitals_checks(size, seed),
        *lipid_checks(min(size, 2_000), seed),
        *anthropometric_checks(min(size, 2_000), seed),
        *nhanes_checks(min(size, 1_500), seed),
        *quality_measure_checks(min(size, 3_000), seed),
    ]


def render_markdown(checks: list[Check], *, size: int, seed: int) -> str:
    by_grade = {grade: [c for c in checks if c.evidence == grade] for grade in EVIDENCE}
    failed = [c for c in checks if not c.passed]

    lines = [
        "# Fidelity Report",
        "",
        "Generated distributions checked against published clinical relationships.",
        f"Regenerated per release from n={size:,} draws, seed {seed}.",
        "",
        "## How much each check proves",
        "",
        (
            "Checks are **graded by evidential strength**, because they are not "
            "equivalent and a flat pass count implies more than most of them carry. "
            "Reporting statistical similarity as though it established clinical "
            "validity is the specific criticism levelled at synthetic-data evaluation "
            "in [arXiv:2606.08903](https://arxiv.org/abs/2606.08903), and it is easier "
            "to avoid by grading than by adding more checks."
        ),
        "",
        "| Grade | Checks | What a pass means |",
        "|---|---:|---|",
    ]
    order = ("out_of_sample", "calibration", "round_trip", "identity")
    for grade in order:
        lines.append(
            f"| **{grade}** | {len(by_grade[grade])} | {EVIDENCE[grade]} |"
        )
    lines += [
        "",
        (
            f"**Read the top row first.** Only {len(by_grade['out_of_sample'])} of "
            f"{len(checks)} checks is genuinely out-of-sample. The rest establish "
            "self-consistency, which is necessary but is a weaker claim than the "
            "phrase 'fidelity report' suggests on its own."
        ),
        "",
    ]

    for grade in order:
        graded = by_grade[grade]
        if not graded:
            continue
        lines += [
            f"### {grade} ({len(graded)})",
            "",
            "| Check | Observed | Expected | Delta | Tolerance | Source | |",
            "|---|---:|---:|---:|---:|---|:--:|",
        ]
        for check in graded:
            lines.append(
                f"| {check.name} | {check.observed:.4g} | {check.expected:.4g} | "
                f"{check.delta:+.3g} | ±{check.tolerance:.3g} | {check.source} | "
                f"{'PASS' if check.passed else 'FAIL'} |"
            )
        lines.append("")

    lines += [
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
