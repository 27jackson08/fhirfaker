"""Is CTGAN's dependence loss under-training, or the model?

Publishing "a GAN loses cross-domain dependence" on 300 epochs and 606 rows would be
unfair in exactly the way this project keeps avoiding. So: sweep the epochs, and also
train on the full sample to separate "not enough data" from "not enough training".
"""
import sys
import numpy as np
import pandas as pd
from ctgan import CTGAN
sys.path.insert(0, ".")
from synthcity_bench import ANALYTES, correlations, real_rows, report

rows = real_rows()
rng = np.random.default_rng(11)
idx = rng.permutation(len(rows))
train = [rows[i] for i in idx[: len(idx) // 2]]
test = [rows[i] for i in idx[len(idx) // 2:]]
reference = correlations(test)
print(f"NHANES nondiabetic 45-65: {len(rows)} complete cases "
      f"({len(train)} train / {len(test)} held out)\n")
report("NHANES (held-out truth)", test, reference)

def run(label, rows_in, epochs):
    frame = pd.DataFrame([{**r, "sex": s} for r, s in rows_in])
    m = CTGAN(epochs=epochs, verbose=False)
    m.fit(frame, discrete_columns=["sex"])
    drawn = m.sample(2400)
    synth = [({a: float(r[a]) for a in ANALYTES}, str(r["sex"]))
             for _, r in drawn.iterrows() if all(np.isfinite(r[a]) for a in ANALYTES)]
    report(label, synth, reference)

for epochs in (300, 1000, 3000):
    run(f"CTGAN {epochs} epochs, n=606", train, epochs)
# Train on everything: an upper bound on what more data buys, at the cost of
# overlapping the evaluation set. Reported as such.
run("CTGAN 3000 epochs, n=1213*", rows, 3000)
print("\n  * trained on all rows including the evaluation half — an optimistic bound,")
print("    not a fair score. Shown to separate 'needs more data' from 'loses structure'.")
