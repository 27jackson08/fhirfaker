# Clinical quality measure benchmark

Regenerate with `pytest -m fidelity tests/test_benchmark.py`. Measures are computed
from the **emitted FHIR**, not from the internal draw — a measure engine reading the
sampler's own state would be marking its own homework.

## Why this benchmark and not another

Synthea's published validation ([Chen et al., *BMC Med Inform Decis Mak* 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/))
measured it against four CMS clinical quality measures. The result splits cleanly:

| Measure | Type | Synthea | Real (MA) | Real (US) |
|---|---|---:|---:|---:|
| Colorectal cancer screening | process | 68.7% | 77.3% | 69.8% |
| COPD 30-day mortality | outcome | 0.7% | 7.0% | 8.0% |
| Complications after hip/knee replacement | outcome | **0%** | 2.9% | 2.8% |
| Controlling high blood pressure | outcome | **0%** | 74.5% | 69.7% |

Synthea tracks reality on the process measure and collapses on every outcome measure.
The authors name the cause: synthetic generators "do not currently model for deviations
in care and the potential outcomes that may result from care deviations."

That is a statement about architecture, not a bug report. A state machine over care
pathways can decide *whether a patient was screened*. It has no representation of what
the blood pressure did after the thiazide started, so a control rate cannot emerge from
it. This project models clinical state directly, which is the machinery an outcome
measure needs.

## Results

| Measure | Synthea | **carebundle** | Real (US) | Real (MA) |
|---|---:|---:|---:|---:|
| Controlling high blood pressure (CBP) | 0% | **71.5%** | 69.7% | 74.5% |
| Colorectal cancer screening | 68.7% | *not modelled* | 69.8% | 77.3% |
| COPD 30-day mortality | 0.7% | *not modelled* | 8.0% | 7.0% |
| Complications after hip/knee replacement | 0% | *not modelled* | 2.8% | 2.9% |

**The three "not modelled" rows are published deliberately.** They need procedures,
mortality and longitudinal follow-up that this library does not generate, and a
benchmark that quietly dropped the measures it loses would be worthless as evidence.
*Not modelled* is a different claim from 0%, and the measure engine keeps them
distinguishable: a zero denominator is reported as a zero denominator, never as a rate.

### Controlling high blood pressure, in detail

Denominator is the HEDIS/NCQA definition — ages 18–85, coded hypertension diagnosis,
an outpatient encounter, and a recorded blood pressure. Numerator is a most-recent
reading below **140/90**, with both components required.

| Population | Denominator | CBP rate |
|---|---:|---:|
| `hypertension` profile | 1500 | 70.3% |
| `type2_diabetes` profile | 1045 | 70.8% |
| `ckd_stage3` profile | 1197 | 71.8% |
| **Mixed cohort (prevalence-drawn)** | **1822 / 4000** | **71.5%** |
| `healthy` profile | 0 | *not in denominator* |

## How the number was produced, and why it is not tuned

This is the part that matters. A benchmark you fit to is worthless, so every input
comes from a cited source and the rate is what those inputs imply.

**Inputs (fitted to sources):**

1. **Who is treated.** NHANES, August 2021–August 2023 ([NCHS Data Brief](https://www.ncbi.nlm.nih.gov/books/NBK612761/)):
   59.2% of US adults with hypertension are aware of it, 51.2% take medication. So
   51.2 / 59.2 = **86.5% of diagnosed hypertensives are on treatment**, and
   diagnosed-and-in-care is exactly the population these profiles represent. The
   per-drug prescribing probabilities are *solved* for that fraction rather than
   hand-written, so the cited target and the emitted probabilities cannot drift apart.
2. **How much treatment lowers pressure.** Law MR, Wald NJ, Morris JK, *BMJ*
   2003;326:1427 — a meta-analysis of 354 randomised placebo-controlled trials. One
   standard-dose agent lowers blood pressure by **9.1 systolic / 5.5 diastolic**, and
   the reduction is larger from a higher starting pressure (1.0 mmHg more systolic per
   10 mmHg higher pre-treatment). A [2025 *Lancet* meta-analysis](https://pubmed.ncbi.nlm.nih.gov/40885583/)
   of 484 trials puts monotherapy at 8.7 (95% CI 8.2–9.2), bracketing the same figure.

**Output (not fitted):** the control rate. Nothing in the model was adjusted to reach
64.1%. Change either cited input and the number moves.

The mechanism is the same computed-identity discipline used for eGFR and Friedewald
LDL: the copula draws a *pre-treatment* pressure, the prescribing rules escalate on it
(you add an agent because the patient is uncontrolled), and the *recorded* pressure is
then computed from the regimen the patient actually received. Effects are applied per
distinct drug class sequentially, so Law's baseline-dependence produces diminishing
returns by construction rather than by a fudge factor. A bundle therefore cannot
prescribe three antihypertensives beside an untreated-looking 168/102.

## The titration hypothesis, tested and confirmed

The first version of this benchmark measured **64.1%** against a US comparator of
69.7% and published the 5.6-point shortfall rather than closing it, along with a
specific, falsifiable explanation:

> The most likely mechanism is dose titration: HEDIS scores the *most recent* reading
> of a year in which clinicians repeatedly re-measure and escalate until the patient
> reaches goal, whereas this models a single visit with a fixed regimen at standard
> doses.

**That prediction was then tested and it held.** Modelling titration moved the rate
from 64.1% to **71.5%**, between the US (69.7%) and Massachusetts (74.5%) comparators.

What makes this a real test rather than a fit:

- The titration effect size comes from a **different study** than the base effect —
  the [2025 *Lancet* meta-analysis](https://pubmed.ncbi.nlm.nih.gov/40885583/) of 484
  trials, at 1.5 mmHg systolic per dose doubling — so the correction was not
  calibrated against the residual it was predicting.
- Escalation is **conditional on being above goal**, which is what titration is. A
  patient already at target is never escalated, so the mechanism cannot inflate the
  control rate from the wrong end by pushing controlled patients further down.
- The ceiling of two doublings is clinically motivated (beyond roughly four times
  standard dose, another agent is preferred to another doubling), not fitted. Raising
  it would push the rate higher; it was fixed before the rate was measured.

The direction of the original error also ruled out the obvious alternative. Law's
figures are **trial efficacy**, and real-world effectiveness is normally *lower*
because of adherence — so an adherence gap would have made the modelled rate too
**high**, not too low. Undershooting pointed at a missing treatment intensity, which
is what titration supplies.

Remaining caveats:

- Non-adherence is still not modelled. It is a real effect in the opposite direction,
  and the fact that the rate lands mid-band without it suggests the two are partially
  cancelling rather than that adherence is absent from reality.
- The comparators are from 2019 and reflect the plans and years measured then. The
  national HEDIS figure has sat in the low-to-mid 60s in other years.

## What this does and does not establish

It establishes that a distributional model reproduces an outcome measure that a
pathway simulator scores **0%** on, from independently cited inputs, checked in CI.

It does not establish that this is a better synthetic data generator than Synthea.
Synthea covers 231 conditions, a lifetime per patient, and three of the four measures
in this very table. On breadth it is not close, and [ROADMAP.md](ROADMAP.md) does not
propose competing there.

## Sources

- [Chen J et al., "The validity of synthetic clinical data … (Synthea) using clinical quality measures", *BMC Med Inform Decis Mak* 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/)
- [NCHS Data Brief: Hypertension Prevalence, Awareness, Treatment, and Control, US, Aug 2021–Aug 2023](https://www.ncbi.nlm.nih.gov/books/NBK612761/)
- [Law MR, Wald NJ, Morris JK, "Value of low dose combination treatment with blood pressure lowering drugs", *BMJ* 2003;326:1427](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC162261/)
- [Blood pressure-lowering efficacy of antihypertensive drugs and their combinations, *Lancet* 2025](https://pubmed.ncbi.nlm.nih.gov/40885583/)
- [NCQA HEDIS: Controlling High Blood Pressure (CBP)](https://www.ncqa.org/report-cards/health-plans/state-of-health-care-quality-report/controlling-high-blood-pressure-cbp/)
