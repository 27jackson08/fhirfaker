"""Score a learned tabular generator on the same dependence benchmark.

Why this generator, specifically
-------------------------------
Synthea and carebundle are both rule-based, so a shared blind spot between them would be
uninformative — the finding could be about that architecture rather than about Synthea.
A model *trained on the data itself* is the strongest test available: it has the most
direct possible access to the dependence structure.

The comparison therefore is not symmetric, and saying so matters:

    Synthea      never sees NHANES at all
    carebundle   marginals and correlations fitted to NHANES aggregates
    synthcity    trained on individual NHANES rows

synthcity has the greatest advantage of the three. If it still under-reproduces the
dependence, that is a strong result about generative models. If it reproduces it well,
that is expected, and it demonstrates the benchmark is sensitive rather than lenient.

Train and test are split so the generator is never scored against rows it was fitted on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np



from carebundle.benchmark.cooccurrence import measure as cooccur  # noqa: E402
from carebundle.calibration import nhanes  # noqa: E402

DATA = Path("/private/tmp/claude-501/-Users-jacksonbomongcag-FIHR-github/"
            "a9f4c9a5-ef91-444f-9726-a58a87010f16/scratchpad/nhanes")
ANALYTES = ("bmi", "triglycerides", "hdl", "glucose")
PAIRS = (("bmi", "triglycerides"), ("bmi", "hdl"), ("bmi", "glucose"),
         ("triglycerides", "hdl"), ("glucose", "triglycerides"), ("glucose", "hdl"))


def real_rows():
    people = nhanes.load(DATA)
    rows = []
    for sex in ("F", "M"):
        for r in nhanes.in_band(people, sex, "nondiabetic"):
            if all(r.get(a) is not None for a in ANALYTES):
                rows.append(({a: r[a] for a in ANALYTES}, sex))
    return rows


def correlations(rows):
    out = {}
    for a, b in PAIRS:
        for sex in ("F", "M"):
            xy = [(r[a], r[b]) for r, s in rows if s == sex]
            if len(xy) > 30:
                out[(a, b, sex)] = float(
                    np.corrcoef([p[0] for p in xy], [p[1] for p in xy])[0, 1])
    return out


def report(name, rows, reference):
    got = correlations(rows)
    devs = [abs(got[k] - reference[k]) for k in reference if k in got]
    signs = sum(np.sign(got[k]) == np.sign(reference[k]) for k in reference if k in got)
    c = cooccur(rows)
    print(f"  {name:26} n={c.n:5}  mean |dev| {np.mean(devs):.3f}  "
          f"sign {signs}/{len(devs)}  P(>=3) {c.rate(3):5.1%}  "
          f"ratio {c.dependence_ratio(3):.2f}x")
    return np.mean(devs)


def main():
    rows = real_rows()
    rng = np.random.default_rng(11)
    idx = rng.permutation(len(rows))
    train = [rows[i] for i in idx[: len(idx) // 2]]
    test = [rows[i] for i in idx[len(idx) // 2:]]
    reference = correlations(test)
    print(f"NHANES nondiabetic 45-65: {len(rows)} complete cases "
          f"({len(train)} train / {len(test)} held out)\n")
    report("NHANES (held-out truth)", test, reference)

    import pandas as pd
    from ctgan import CTGAN

    frame = pd.DataFrame([{**r, "sex": s} for r, s in train])
    model = CTGAN(epochs=300, verbose=False)
    model.fit(frame, discrete_columns=["sex"])
    drawn = model.sample(len(test) * 4)
    synth = [
        ({a: float(row[a]) for a in ANALYTES}, str(row["sex"]))
        for _, row in drawn.iterrows()
        if all(np.isfinite(row[a]) for a in ANALYTES)
    ]
    report("CTGAN (trained on NHANES)", synth, reference)


if __name__ == "__main__":
    main()
