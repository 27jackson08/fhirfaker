# Synthetic patient generators score 0% on outcome quality measures

*A write-up of the finding behind this library. Every figure here is asserted against the
repository's own evidence documents by `tests/test_writeup.py`, so it cannot go stale
quietly.*

If you generate synthetic health data, you probably validate it by checking that the
distributions look right. That is the standard approach and it is not enough, in a way
that is easy to demonstrate and hard to fix.

## The finding

A 2019 study tested Synthea — the standard open-source synthetic patient generator, from
MITRE — against four CMS clinical quality measures. Synthea is good software with a
decade of work behind it, and the result splits cleanly [1]:

| Measure | Type | Synthea | Real (US) |
|---|---|---:|---:|
| Colorectal cancer screening | process | 68.7% | 69.8% |
| COPD 30-day mortality | outcome | 0.7% | 8.0% |
| Complications after hip/knee replacement | outcome | **0%** | 2.8% |
| Controlling high blood pressure | outcome | **0%** | 69.7% |

One percentage point off on the process measure. Zero on the outcome measures.

> **Correction, August 2026.** That table is Chen et al.'s 2019 result and it no longer
> describes Synthea. Measured in August 2026 with this project's own measure code,
> current Synthea scores **74.4%** on blood-pressure control, not 0%, and 0.56% of its
> diabetic patients carry an amputation code rather than the 100% a 2023 paper reported.
> The argument below — that a pathway simulator has no representation of what the blood
> pressure did afterwards — was a reasonable reading of the 2019 evidence and is not a
> safe claim about the software today. What survives is the design argument, not the
> scoreboard. See [BENCHMARK.md](../BENCHMARK.md) for the measured comparison and the
> harness that produced it.

The authors name the cause: synthetic generators "do not currently model for deviations
in care and the potential outcomes that may result from care deviations."

## Why this is architectural, not a bug

Synthea models care as state machines over *pathways*. A module encodes: patient has
hypertension, therefore a visit occurs, therefore a drug is prescribed. That structure
answers "was this patient screened?" — a process question — extremely well.

It has no representation of what the blood pressure *did* after the thiazide started.
And "Controlling High Blood Pressure" is not a question about the pathway. It asks
whether the most recent reading is below 140/90. Control is a property of the value.

A pathway simulator cannot produce a control rate, because the quantity being measured
does not exist in its model. No amount of additional modules fixes that; it is the wrong
axis.

## What happens if you model the value instead

I tested this while building a generator that works the other way round: analytes drawn
jointly from a Gaussian copula, calibrated against NHANES, with derived quantities
computed from published formulas rather than sampled.

Starting point: **21.4%**. Better than zero, but for an uninteresting reason — the
marginal represented untreated hypertension and its lower bound happened to put some
patients under 140/90 by accident.

The real fix was to make the recorded pressure depend on the treatment in the same
bundle. Two cited inputs:

- **Who is treated.** NHANES 2021–2023: 59.2% of hypertensive adults are aware, 51.2%
  are on medication, so 51.2/59.2 = **86.5%** of *diagnosed* hypertensives are treated.
- **How much treatment lowers pressure.** Law, Wald and Morris, BMJ 2003 — 354
  randomised trials: **9.1 systolic / 5.5 diastolic** per standard-dose agent, and larger
  from a higher starting pressure.

The copula draws a pre-treatment pressure; the prescribing rules escalate on it; the
recorded pressure is computed from the regimen the patient actually received.

Result: **64.1%**, against a real-world 69.7%.

## The part that makes it a test rather than a fit

A benchmark you tune to is worthless. So the discipline was: calibrate inputs to sources,
never to the benchmark, and publish whatever the output does.

That left a 5.6-point shortfall, published with a falsifiable guess: HEDIS scores the
*most recent* reading of a year in which clinicians repeatedly re-measure and escalate
until the patient reaches goal, whereas I was modelling a single visit at standard doses.

Then I tested it. A 2025 Lancet meta-analysis of 484 trials gives a further **1.5 mmHg**
systolic per dose doubling — a *different* study from the one supplying the base effect,
so the correction was not calibrated against the residual it was predicting. Escalation
only fires above goal, so it cannot inflate the rate by pushing already-controlled
patients further down.

Result: **71.5%**, between the US (69.7%) and Massachusetts (74.5%) comparators.

The prediction held. That is worth more than the number.

## The prediction that did not hold

Non-adherence is real, well documented, and acts in the direction of the original
shortfall. Adding it looked obviously correct.

| Model | Control rate |
|---|---:|
| No adherence term | 74.7% |
| 45% take nothing (per meta-analysis) | 50.4% |
| Effect scaled by proportion-of-days-covered | 49.3% |
| Real-world | 69.7–74.5% |

Both formulations land roughly 20 points *below* reality. Right about direction, badly
wrong about magnitude — so the naive term is a worse model, not a missing one, and it was
not shipped.

Two reasons it fails, and both generalise. Population-wide adherence figures do not
transfer to a HEDIS denominator that already selects for people who attend appointments.
And "non-adherent" is not "untreated": a patient at 62% days-covered takes most of their
doses and gets most of the benefit.

## Does any of this transfer?

Reproducing a quality measure shows the distributions are right where that measure looks.
It does not show the data is *useful*. The standard test for that is
Train-on-Synthetic-Test-on-Real: fit a model entirely on generated patients, score it on
real ones.

| Model | AUC |
|---|---:|
| Train on **synthetic**, test on **real** | **0.621** |
| Train on real, test on real (5-fold) | 0.677 |
| **Retention** | **91.7%** |

Predicting diagnosed diabetes from BMI, triglycerides, HDL and systolic pressure, scored
on 1,330 real NHANES individuals aged 45–65.

HbA1c is deliberately excluded. Predicting diabetes from HbA1c is not a prediction, it is
the diagnostic criterion restated, and any generator would score near 1.0. These features
are the metabolic signal *around* the diagnosis — a genuinely hard task, which is why the
real-data ceiling is only 0.677. A low ceiling leaves room to fail.

This is not independent evidence: the marginals came from the same survey the test
individuals do. But no fitting targeted an AUC, and the individuals were never seen, so
it tests something the calibration never aimed at.

## The trap in benchmarking synthetic data at all

The obvious second measure was CMS122, diabetes HbA1c poor control. It needs only a
diagnosis and a lab result. It is not usable, for a reason worth knowing.

CMS publishes three national rates for it, same measure, same year: **11.70%** (Medicare
Part B claims), **27.30%** (MIPS CQM), **43.53%** (eCQM). A four-fold spread in an
official benchmark, and the numerator explains it:

> "Patients whose most recent HbA1c level is >9.0% **or is missing, or was not
> performed** during the measurement period"

CMS122 measures glycaemic control *plus testing completeness*, summed. The three rates
order exactly by how much each collection method depends on complete EHR capture.

A generator where every diabetic has an HbA1c can only reproduce the clinical half. Mine
sits at 12.9% above 9%, close to the claims figure — and publishing that as reproducing
CMS122 would be matching two different quantities.

**The general rule: before benchmarking against a quality measure, read its numerator for
the word "missing."** If it is there, the measure is partly about data quality and partly
about care, and synthetic data with perfect capture cannot reproduce it. This constrains
Synthea equally.

## What this does not show

Not that my generator is better than Synthea. Synthea covers 231 conditions, a lifetime
per patient, and three of the four measures in that table. On breadth it is not close.

Nor that the fidelity is broadly validated. The report grades every check by what a pass
proves, and says out loud that **1 of 58 is genuinely out-of-sample** — the rest establish
self-consistency, which is necessary and is a weaker claim than the phrase "fidelity
report" suggests. A test pins that count so it cannot grow by relabelling.

What it does show is narrower and, I think, more useful: **distributional similarity and
clinical validity are different properties, and the standard way of validating synthetic
health data measures the first while implying the second.** A generator can match every
marginal and still score zero on the question a clinician would actually ask.

That is not my observation. A 2026 evaluation of four generative paradigms on a
50,000-person cardiovascular cohort found that "models with strong distributional
fidelity can exhibit poor calibration and distorted relationships," and that none of the
four simultaneously preserved subgroup structure, effect estimates and dependency
relationships [2].

The quality measures have been sitting there the whole time, published, with real-world
comparators attached. They are a harder test than a Kolmogorov–Smirnov statistic and a
more meaningful one.

---

## Reproducing this

Everything above is checkable. The blood-pressure figures come out of the test suite:

```bash
pip install -e ".[dev]"
pytest -m fidelity tests/test_benchmark.py     # the control rates
```

The transfer result needs the NHANES individual records, which are not vendored:

```bash
python -m carebundle.calibration.fetch    --data-dir nhanes/
python -m carebundle.fidelity.transfer    --data-dir nhanes/
```

The calibration itself is deterministic — regenerating the targets from a fresh download
reproduces the committed file byte for byte.

The library is [carebundle](https://pypi.org/project/carebundle/) (`pip install
carebundle`). The benchmark, including the three measures it does not model and why, is
in [BENCHMARK.md](../BENCHMARK.md).

[1] Chen J et al., *BMC Med Inform Decis Mak* 2019. https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/
[2] "Synthetic but Not Realistic", arXiv:2606.08903. https://arxiv.org/abs/2606.08903
