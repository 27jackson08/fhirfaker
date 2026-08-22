"""Derive marginal distributions from NHANES.

The build doc's honest caveat was that marginals were "clinically-informed estimates,
not fits to a named cohort". This closes that: it reads the NHANES 2017-March 2020
pre-pandemic public files, restricts to the generator's target age band, stratifies by
sex and by glycaemic status, and reports the moments a profile should use.

Offline, like `carebundle/spec/codegen.py` — nothing here runs on the generation path.

    python -m carebundle.calibration.nhanes --data-dir <dir>

Files (https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/):
    P_DEMO P_GHB P_DIQ P_BPQ P_BIOPRO P_TCHOL P_HDL P_TRIGLY P_BMX P_BPXO P_CBC
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from carebundle.calibration.xpt import read_xpt

# NHANES variable -> the analyte name this project uses.
VARIABLES = {
    "P_GHB": {"LBXGH": "hba1c"},
    # Diabetes status by diagnosis rather than by lab threshold — see `in_band`.
    "P_DIQ": {"DIQ010": "diagnosed_diabetes"},
    # BPQ020: "ever told you had high blood pressure". Diagnosed rather than measured,
    # to match the `I10` code the comorbidity rule emits.
    "P_BPQ": {"BPQ020": "diagnosed_hypertension"},
    "P_BIOPRO": {
        "LBXSCR": "creatinine", "LBXSGL": "glucose", "LBXSBU": "bun",
        "LBXSNASI": "sodium", "LBXSKSI": "potassium", "LBXSCLSI": "chloride",
        "LBXSC3SI": "co2", "LBXSCA": "calcium", "LBXSAL": "albumin",
        "LBXSATSI": "alt", "LBXSASSI": "ast", "LBXSAPSI": "alkaline_phosphatase",
        "LBXSTB": "bilirubin_total",
    },
    "P_TCHOL": {"LBXTC": "cholesterol_total"},
    "P_HDL": {"LBDHDD": "hdl"},
    "P_TRIGLY": {"LBXTR": "triglycerides", "LBDLDL": "ldl"},
    "P_BMX": {"BMXHT": "height_cm", "BMXWT": "weight_kg", "BMXBMI": "bmi"},
    "P_BPXO": {"BPXOSY1": "systolic", "BPXODI1": "diastolic"},
    "P_CBC": {
        "LBXHGB": "hemoglobin", "LBXHCT": "hematocrit", "LBXRBCSI": "rbc",
        "LBXWBCSI": "wbc", "LBXPLTSI": "platelets",
    },
}

AGE_LOW, AGE_HIGH = 45, 65
DIABETES_HBA1C = 6.5  # ADA diagnostic threshold, for the lab-defined strata.

# DIQ010: "Other than during pregnancy, has a doctor or other health professional ever
# told you that you have diabetes?" 1 = yes, 2 = no, 3 = borderline, 7/9 = refused/unknown.
DIQ_YES, DIQ_NO = 1.0, 2.0

# NHANES codes sex as 1 = male, 2 = female.
_SEX = {1.0: "M", 2.0: "F"}


# A normal SD equals IQR / 1.349. For a skewed analyte the raw SD is inflated by the
# upper tail, and feeding it to a symmetric truncated normal produces a distribution
# that matches neither the centre nor the spread.
IQR_TO_SD = 1.349


@dataclass(frozen=True)
class Moments:
    analyte: str
    stratum: str
    n: int
    mean: float
    sd: float
    median: float
    robust_sd: float
    q1: float
    q3: float
    p2_5: float
    p97_5: float

    @property
    def skew_ratio(self) -> float:
        """How much the raw SD exceeds the robust one. >1.3 means visibly skewed."""
        return self.sd / self.robust_sd if self.robust_sd else float("inf")

    def as_marginal(self) -> str:
        """The Marginal(...) literal this stratum implies.

        Centre and spread come from the median and IQR so a skewed analyte is not
        modelled around a mean its own tail dragged upward.
        """
        return (
            f'Marginal("{self.analyte}", mean={self.median:.4g}, '
            f"sd={self.robust_sd:.4g}, low={self.p2_5:.4g}, high={self.p97_5:.4g})"
        )


def load(data_dir: Path) -> dict[float, dict[str, float]]:
    """Join every file on SEQN into one record per respondent."""
    people: dict[float, dict[str, float]] = {}

    _, demo = read_xpt(data_dir / "P_DEMO.xpt")
    for row in demo:
        seqn = row.get("SEQN")
        age, sex = row.get("RIDAGEYR"), row.get("RIAGENDR")
        if seqn is None or age is None or sex not in _SEX:
            continue
        people[seqn] = {"age": age, "sex": _SEX[sex]}

    for stem, mapping in VARIABLES.items():
        path = data_dir / f"{stem}.xpt"
        if not path.exists():
            print(f"  (skipping missing {path.name})")
            continue
        _, rows = read_xpt(path)
        for row in rows:
            record = people.get(row.get("SEQN"))
            if record is None:
                continue
            for source, analyte in mapping.items():
                value = row.get(source)
                if isinstance(value, float):
                    record[analyte] = value
    return people


# The strata emitted, and why there are two ways of being diabetic here.
#
# `diabetic` is lab-defined (HbA1c >= 6.5) and `diagnosed` is diagnosis-defined
# (DIQ010 == 1). They are different populations and each is correct for a different
# purpose, so both are emitted rather than one replacing the other:
#
#   * A profile that emits `E11.9` — a *diagnosed* type 2 diabetes code — needs
#     `diagnosed`. 25.5% of diagnosed diabetics aged 45-65 sit below 6.5 because their
#     treatment works, and the lab definition excludes every one of them.
#   * A profile meaning "clinically healthy" needs `nondiabetic`, which is lab-defined.
#     Undiagnosed diabetes is common, so "has not been told they have diabetes" is not
#     the same as "does not have it" — the diagnosis-defined complement carries a long
#     upper tail of undiagnosed hyperglycaemia that a healthy baseline should not have.
#
# A stratum defined by a threshold also cannot validate that threshold: selecting on
# `hba1c >= 6.5` makes the extracted 2.5th percentile come out at exactly 6.5, which
# reads as empirical support for the marginal's lower bound and is the selection
# criterion reflected back.
# WHO haemoglobin thresholds for anaemia in non-pregnant adults: <13.0 g/dL in men,
# <12.0 g/dL in women.
#
# Threshold-defined, and correct here in a way it was not for diabetes. That distinction
# is the whole lesson: "diabetic" must be diagnosis-defined because the diagnosis
# persists once treatment brings HbA1c down, so a lab cut-off excludes a quarter of the
# real population. Anaemia is the opposite — `D64.9` *means* the haemoglobin is low, and
# a patient whose iron deficiency was corrected no longer has anaemia, they have a
# history of it. Match the stratum to what the code means, not to a rule about
# thresholds.
ANAEMIA_HAEMOGLOBIN = {"M": 13.0, "F": 12.0}

STRATA = ("all", "nondiabetic", "diabetic", "diagnosed", "anaemic")


def in_band(people: dict[float, dict], sex: str, stratum: str) -> list[dict]:
    """Respondents in the target age band for one stratum. See `STRATA`.

    Respondents who answer "borderline" (3), refuse, or do not know are excluded from
    `diagnosed` rather than being forced to one side: their status is genuinely unknown
    and guessing would contaminate whichever group they landed in.
    """
    if stratum not in STRATA:
        raise ValueError(f"unknown stratum {stratum!r}; known: {STRATA}")

    selected = []
    for record in people.values():
        if not AGE_LOW <= record["age"] <= AGE_HIGH or record["sex"] != sex:
            continue

        if stratum in ("nondiabetic", "diabetic"):
            hba1c = record.get("hba1c")
            if hba1c is None:
                continue
            if (hba1c >= DIABETES_HBA1C) != (stratum == "diabetic"):
                continue
        elif stratum == "diagnosed":
            if record.get("diagnosed_diabetes") != DIQ_YES:
                continue
        elif stratum == "anaemic":
            haemoglobin = record.get("hemoglobin")
            if haemoglobin is None or haemoglobin >= ANAEMIA_HAEMOGLOBIN[sex]:
                continue

        selected.append(record)
    return selected


def moments(records: list[dict], analyte: str, stratum: str) -> Moments | None:
    values = np.array([r[analyte] for r in records if analyte in r], dtype=float)
    if values.size < 30:
        return None
    q1, q3 = np.percentile(values, [25.0, 75.0])
    return Moments(
        analyte=analyte,
        stratum=stratum,
        n=int(values.size),
        mean=float(values.mean()),
        sd=float(values.std(ddof=1)),
        median=float(np.median(values)),
        robust_sd=float((q3 - q1) / IQR_TO_SD),
        q1=float(q1),
        q3=float(q3),
        # Truncation bounds at the 2.5th/97.5th centiles: wide enough not to distort
        # the moments, tight enough to exclude implausible tail draws.
        p2_5=float(np.percentile(values, 2.5)),
        p97_5=float(np.percentile(values, 97.5)),
    )


# Pulled from the files as a stratification variable, not a measurement. Taking
# quartiles of a questionnaire code would emit a straight-faced "median diabetes
# status of 1.0".
NON_ANALYTES = frozenset({"diagnosed_diabetes", "diagnosed_hypertension"})


# Analyte pairs whose dependence the copula needs. Emitted alongside the marginals so
# the correlation matrix is derived from the same extraction rather than hand-set:
# every one of these was originally an estimate, and every one of them was wrong —
# systolic/diastolic by 0.11, triglycerides/HDL by 0.07, and height/weight in women by
# 0.15 because a pooled-looking figure was used in a model that is stratified by sex.
CORRELATION_PAIRS = (
    ("systolic", "diastolic"),
    ("triglycerides", "hdl"),
    ("height_cm", "weight_kg"),
    ("hba1c", "glucose"),
    ("weight_kg", "bmi"),
    # Haemoglobin, haematocrit and red cell count all measure red cell mass, so they
    # move together tightly. Drawing them independently produces a haemoglobin of 9
    # beside a normal haematocrit, which no laboratory would ever report.
    ("hemoglobin", "hematocrit"),
    ("hemoglobin", "rbc"),
    ("hematocrit", "rbc"),
    # The metabolic cluster: adiposity, glycaemia and lipids move together, and the
    # model drew them independently until this was measured. Emitted per stratum
    # because pooling manufactures dependence that does not exist within one —
    # weight/glucose reads +0.10 across everyone and −0.08 inside the diabetic
    # stratum, since the pooled figure is mostly "heavier people are more often
    # diabetic", a fact the profile split already encodes. Fitting the pooled value
    # would count it twice.
    ("weight_kg", "hdl"),
    ("glucose", "triglycerides"),
    ("glucose", "hdl"),
    # HbA1c needs its own pairs. The first attempt specified only glucose's links and
    # predicted the copula would carry them to HbA1c through the 0.82 glucose/HbA1c
    # correlation, giving about -0.15. Measured: -0.009. A Gaussian copula fills an
    # unspecified entry with zero, which *forces* independence rather than leaving it
    # free to be implied — so an unstated correlation is a stated zero.
    ("hba1c", "hdl"),
    ("hba1c", "triglycerides"),
    # Not fitted, measured only: BMI is computed from height and weight, so its link
    # to HDL is whatever the weight pair induces. Having the target here lets a
    # fidelity check compare an unconfigured quantity against the survey.
    ("bmi", "hdl"),
    # Deliberately absent: weight/glucose and weight/hba1c, whose sign reverses
    # between strata for the reason above, and every pair involving blood pressure —
    # systolic against weight, glucose or lipids is between −0.02 and +0.11 with no
    # consistent sign across sexes, which is noise, not a relationship.
)


def correlations(people: dict[float, dict]) -> dict[str, dict]:
    """Pearson correlation per pair, per sex and stratum.

    Computed **within sex**, which is the only figure a sex-stratified generator can
    use. Pooling the sexes inflates any pair where the sexes differ in level — men are
    both taller and heavier, so pooled height/weight reads 0.41 against a within-sex
    0.30 for women.
    """
    out: dict[str, dict] = {}
    for sex in ("F", "M"):
        for stratum in STRATA:
            records = in_band(people, sex, stratum)
            for first, second in CORRELATION_PAIRS:
                pairs = [
                    (r[first], r[second])
                    for r in records
                    if first in r and second in r
                ]
                if len(pairs) < 30:
                    continue
                xs = np.array([p[0] for p in pairs], dtype=float)
                ys = np.array([p[1] for p in pairs], dtype=float)
                if xs.std() == 0.0 or ys.std() == 0.0:
                    continue
                out[f"{sex}/{stratum}/{first}~{second}"] = {
                    "n": len(pairs),
                    "pearson": round(float(np.corrcoef(xs, ys)[0, 1]), 4),
                }
    return out


# Yes/no questionnaire items whose prevalence a profile models as a comorbidity rule.
PREVALENCE_ITEMS = ("diagnosed_hypertension",)


def prevalences(people: dict[float, dict]) -> dict[str, dict]:
    """Share answering yes to each questionnaire item, per sex and stratum.

    Emitted so a comorbidity probability can cite a measurement rather than an estimate.
    Respondents who did not answer yes or no are excluded rather than counted as no,
    which would bias every rate downward.
    """
    out: dict[str, dict] = {}
    for sex in ("F", "M"):
        for stratum in STRATA:
            records = in_band(people, sex, stratum)
            for item in PREVALENCE_ITEMS:
                answers = [
                    r[item] for r in records if r.get(item) in (DIQ_YES, DIQ_NO)
                ]
                if len(answers) < 30:
                    continue
                yes = sum(1 for a in answers if a == DIQ_YES)
                out[f"{sex}/{stratum}/{item}"] = {
                    "n": len(answers),
                    "rate": round(yes / len(answers), 4),
                }
    return out


def report(people: dict[float, dict]) -> list[Moments]:
    analytes = sorted(
        {a for mapping in VARIABLES.values() for a in mapping.values()} - NON_ANALYTES
    )
    results = []
    for sex in ("F", "M"):
        for label in STRATA:
            records = in_band(people, sex, label)
            for analyte in analytes:
                found = moments(records, analyte, f"{sex}/{label}")
                if found:
                    results.append(found)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--analytes", default="", help="comma-separated filter")
    parser.add_argument("--emit-targets", type=Path,
                        help="write a JSON targets file for the fidelity suite")
    parser.add_argument("--emit-marginals", action="store_true",
                        help="print Marginal(...) literals instead of a table")
    args = parser.parse_args()

    people = load(args.data_dir)
    band = [r for r in people.values() if AGE_LOW <= r["age"] <= AGE_HIGH]
    print(f"NHANES 2017-March 2020: {len(people)} respondents, "
          f"{len(band)} aged {AGE_LOW}-{AGE_HIGH}\n")

    wanted = {a.strip() for a in args.analytes.split(",") if a.strip()}
    rows = [r for r in report(people) if not wanted or r.analyte in wanted]

    if args.emit_targets:
        import json

        payload = {
            "source": "NHANES 2017-March 2020 pre-pandemic public files",
            "age_band": [AGE_LOW, AGE_HIGH],
            "strata": {
                f"{r.stratum}/{r.analyte}": {
                    "n": r.n, "median": round(r.median, 4),
                    "robust_sd": round(r.robust_sd, 4),
                    "q1": round(r.q1, 4), "q3": round(r.q3, 4),
                    "skew_ratio": round(r.skew_ratio, 3),
                    "p2_5": round(r.p2_5, 4), "p97_5": round(r.p97_5, 4),
                }
                for r in rows
            },
            "correlations": correlations(people),
            "prevalences": prevalences(people),
        }
        args.emit_targets.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(
            f"wrote {len(payload['strata'])} strata and "
            f"{len(payload['correlations'])} correlations and "
            f"{len(payload['prevalences'])} prevalences to {args.emit_targets}"
        )
        return 0

    if args.emit_marginals:
        for row in rows:
            print(f"# {row.stratum:16s} n={row.n:5d}  {row.as_marginal()}")
        return 0

    print(f"{'analyte':22s} {'stratum':16s} {'n':>6s} {'median':>9s} "
          f"{'robustSD':>9s} {'rawSD':>8s} {'skew':>6s} {'p2.5':>8s} {'p97.5':>8s}")
    for row in rows:
        print(f"{row.analyte:22s} {row.stratum:16s} {row.n:6d} {row.median:9.3f} "
              f"{row.robust_sd:9.3f} {row.sd:8.3f} {row.skew_ratio:6.2f} "
              f"{row.p2_5:8.2f} {row.p97_5:8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
