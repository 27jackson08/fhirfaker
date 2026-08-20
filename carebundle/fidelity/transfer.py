"""Clinical utility: does a model trained on generated data work on real patients?

The third dimension of the evaluation framework in arXiv:2606.08903, and the one this
project could not previously evidence. Descriptive fidelity asks whether the
distributions match. Structural validity asks whether the relationships hold. Clinical
utility asks the question a user actually has — **if I train on this, does it transfer?**

The measurement is Train-on-Synthetic-Test-on-Real (TSTR), the standard for synthetic
data: fit a classifier entirely on generated patients, score it on real held-out
individuals, and compare against the same classifier trained on real data. The ratio is
what matters; the absolute AUC is a property of the task.

Offline, like `carebundle/calibration/nhanes.py`. It needs the NHANES files, which are
not vendored, so it cannot run in CI and is not part of the fidelity suite. Run it when
the calibration changes:

    python -m carebundle.fidelity.transfer --data-dir <dir>

**Why the task deliberately excludes HbA1c.** Predicting diabetes from HbA1c is not a
prediction, it is the diagnostic criterion restated, and any generator would score near
1.0. The features here — BMI, triglycerides, HDL, systolic pressure — are the metabolic
signal *around* the diagnosis, which is a genuinely hard task: a model trained on real
data only reaches about 0.68. That low ceiling is the point. It leaves room to fail.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from carebundle.calibration.nhanes import AGE_HIGH, AGE_LOW, DIQ_NO, DIQ_YES
from carebundle.calibration.xpt import read_xpt
from carebundle.profiles.base import draw
from carebundle.profiles.library import get_profile

FEATURES = ("bmi", "triglycerides", "hdl", "systolic")
FILES = ("P_DEMO", "P_DIQ", "P_BMX", "P_TRIGLY", "P_HDL", "P_BPXO")
_SEX = {1.0: "M", 2.0: "F"}


def load_real(data_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Real NHANES individuals in the target age band, with complete features."""
    rows = {name: read_xpt(data_dir / f"{name}.xpt")[1] for name in FILES}
    people: dict[float, dict] = {}
    for record in rows["P_DEMO"]:
        seqn = record.get("SEQN")
        if seqn is None:
            continue
        people[seqn] = {
            "age": record.get("RIDAGEYR"),
            "sex": _SEX.get(record.get("RIAGENDR")),
        }
    mapping = {
        "P_DIQ": {"DIQ010": "diq"},
        "P_BMX": {"BMXBMI": "bmi"},
        "P_TRIGLY": {"LBXTR": "triglycerides"},
        "P_HDL": {"LBDHDD": "hdl"},
        "P_BPXO": {"BPXOSY1": "systolic"},
    }
    for name, columns in mapping.items():
        for record in rows[name]:
            person = people.get(record.get("SEQN"))
            if person is None:
                continue
            for source, target in columns.items():
                value = record.get(source)
                if isinstance(value, float):
                    person[target] = value

    selected = [
        p for p in people.values()
        if p["age"] is not None
        and AGE_LOW <= p["age"] <= AGE_HIGH
        and p.get("diq") in (DIQ_YES, DIQ_NO)
        and all(f in p for f in FEATURES)
    ]
    features = np.array([[p[f] for f in FEATURES] for p in selected], dtype=float)
    labels = np.array([1.0 if p["diq"] == DIQ_YES else 0.0 for p in selected])
    return features, labels


def synthesise(profile: str, count: int, rng: np.random.Generator) -> np.ndarray:
    rows = []
    for index in range(count):
        sex = "F" if index % 2 else "M"
        drawn = draw(get_profile(profile, sex), rng=rng, age_years=55.0, sex=sex)
        rows.append([drawn.raw[f] for f in FEATURES])
    return np.array(rows, dtype=float)


def fit_logistic(
    features: np.ndarray, labels: np.ndarray, *, epochs: int = 4000, rate: float = 0.25
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Plain logistic regression by gradient descent.

    Hand-rolled rather than pulled from scikit-learn: this module is offline tooling and
    the runtime dependency list — two packages — is part of what the project claims.
    Standardisation uses the *training* moments, which are then applied to the test set
    unchanged, so no information about the real data leaks into a synthetic-trained model.
    """
    mean, deviation = features.mean(0), features.std(0)
    design = np.hstack([(features - mean) / deviation, np.ones((len(features), 1))])
    weights = np.zeros(design.shape[1])
    for _ in range(epochs):
        predicted = 1.0 / (1.0 + np.exp(-design @ weights))
        weights -= rate * (design.T @ (predicted - labels)) / len(labels)
    return weights, mean, deviation


def apply_model(model: tuple, features: np.ndarray) -> np.ndarray:
    weights, mean, deviation = model
    design = np.hstack([(features - mean) / deviation, np.ones((len(features), 1))])
    return design @ weights


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based AUC, equivalent to the Mann-Whitney U statistic."""
    order = np.argsort(scores)
    ranks = np.empty(len(labels), dtype=float)
    ranks[order] = np.arange(1, len(labels) + 1)
    positives, negatives = labels.sum(), (1.0 - labels).sum()
    if positives == 0 or negatives == 0:
        raise ValueError("AUC needs both classes present")
    return float(
        (ranks[labels == 1].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def evaluate(data_dir: Path, *, seed: int = 20260820, size: int = 1200) -> dict:
    """TSTR against a train-on-real ceiling, both scored on real held-out individuals."""
    real_features, real_labels = load_real(data_dir)
    rng = np.random.default_rng(seed)

    synthetic = np.vstack([
        synthesise("type2_diabetes", size, rng),
        synthesise("healthy", size, rng),
    ])
    synthetic_labels = np.concatenate([np.ones(size), np.zeros(size)])

    tstr = roc_auc(
        apply_model(fit_logistic(synthetic, synthetic_labels), real_features),
        real_labels,
    )

    # Cross-validated so the ceiling is never scored on rows it was fitted to.
    indices = np.arange(len(real_labels))
    rng.shuffle(indices)
    folds = np.array_split(indices, 5)
    scores = []
    for held_out in range(5):
        test = folds[held_out]
        train = np.concatenate([folds[i] for i in range(5) if i != held_out])
        model = fit_logistic(real_features[train], real_labels[train])
        scores.append(roc_auc(apply_model(model, real_features[test]), real_labels[test]))
    trtr = float(np.mean(scores))

    return {
        "n_real": len(real_labels),
        "prevalence": float(real_labels.mean()),
        "tstr_auc": tstr,
        "real_auc": trtr,
        "retention": tstr / trtr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()

    result = evaluate(args.data_dir, seed=args.seed)
    print(f"real individuals      {result['n_real']:>8}")
    print(f"prevalence            {result['prevalence']:>8.1%}")
    print(f"TSTR  (synthetic->real) AUC {result['tstr_auc']:.3f}")
    print(f"TRTR  (real->real)      AUC {result['real_auc']:.3f}   <- ceiling")
    print(f"retention             {result['retention']:>8.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
