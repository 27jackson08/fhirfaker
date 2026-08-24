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

## Correction, August 2026: the Synthea figure was stale and is withdrawn

**This document used to report Synthea at 0% on blood-pressure control, and that is no
longer true.** The 0% came from Chen et al. 2019 — a citation, not a measurement, about
a build seven years old.

It is now measured. A current Synthea (`master-branch-latest`, August 2026, 1,200
patients, default Massachusetts settings) was generated and scored with
`carebundle.benchmark.cqm` — the same code that scores this package — via
`python -m carebundle.benchmark.synthea`:

| | CBP rate | Denominator | Nearest real-world reference |
|---|---:|---:|---|
| **Synthea, measured Aug 2026** | **74.4%** | ~431 | Massachusetts, 74.5% |
| **carebundle 0.4.0-dev, same code** | **68.8%** | 667 | US national, 69.7% |
| Synthea, *as published* Chen 2019 | 0% | — | — |

Measured against **Synthea `d9d07a6`**, built 2026-08-18, JAR SHA-256
`018ad7f0…fae224ac`. Pinning the commit matters more here than usual: `master-branch-latest`
is a moving target, so a reader re-running this next year and getting a different number
would have no way to tell a Synthea change from an error in this document.

The result is not fragile. Across four defensible readings of the measure — most recent
reading ever or within a 12- or 24-month window, including or excluding decedents —
Synthea lands between **74.2% and 75.0%**; the 74.8% variant excludes decedents. The
74.4% above is the median of three generation runs (74.2 / 74.4 / 74.5), all of which
`python -m carebundle.benchmark.synthea` prints by default, so the document reports what
the tool reports rather than the most flattering of them.

**Why this says 68.8% where `FIDELITY.md` says 74.6%.** They score different
populations. The fidelity check draws the `hypertension` profile at a fixed age 58, so
every patient is hypertensive by construction; the row above scores a mixed cohort aged
18-85, matching the shape of the Synthea population it is being compared against, where
hypertensives arise by prevalence across a much wider age range. Both numbers are
correct. A control rate is a property of a denominator, not of a model, which is the
same trap that makes NHANES report 20.7% and HEDIS ~70% for the same country.

**Read the reference column before reading the rates.** Synthea simulates Massachusetts
by default and lands 0.3 points from the Massachusetts rate. This package calibrates to
NHANES national and lands 0.9 points from the US rate. Both reproduce their own target
population; neither wins, and a comparison that ignored which population each was aiming
at would manufacture a difference that is not there.

**A second published criticism also failed to reproduce.** Kartoun et al. (JAMIA Open
2023) report that "100% of Synthea type-2 diabetics had at least one amputation". In
this population, 3 of 537 diabetes-coded patients carried any amputation code —
**0.56%**, against a real-world US incidence of roughly 5 per 1,000 diabetics per year.
Whatever produced that finding has been fixed too.

**What this cost.** The headline competitive claim of this project was false for as long
as Synthea had been fixed and nobody here had checked. It survived because it was
*cited* rather than *run*, and a citation cannot go stale in CI. Every remaining
comparative claim below is now produced by code in this repository, against software
downloaded at the version stated.

## The claim that survived, also measured

Losing the outcome-measure claim left a narrower architectural one: that a per-condition
module graph represents dependence *within* a condition and not *between* body systems.
Having just been wrong about a competitor on an unchecked claim, that one was checked
before being published. `python -m carebundle.benchmark.dependence` measures it, on
both, from emitted FHIR, against the committed NHANES extraction.

Seven analyte pairs across adiposity, glycaemia and lipids, within sex, ages 45–65, one
contemporaneous panel per patient:

| | mean \|deviation\| | observed spread | worst cell | sign agreement |
|---|---:|---|---:|---:|
| **Synthea** | 0.208 | 0.192 – 0.209, 3 runs | 0.431 | 10 / 14 |
| **carebundle 0.4.0-dev** | **0.047** | 0.040 – 0.055, 4 seeds | **0.149** | **14 / 14** |

Both figures are medians with their spread, and that is not decoration. Synthea does not
produce an identical population from an identical seed — three runs of build `d9d07a6`
gave 1,462, 1,449 and 1,447 bundles, because `-p` counts living patients and generation
is concurrent. This package is deterministic per seed and varies across seeds instead.
Reporting one seeded draw here against a noisy average there would have flattered this
package, and the first version of this table did exactly that: it quoted 0.192, which
turned out to be the lowest of the three Synthea runs.

### What the dependence gap costs, and two wrong answers on the way

**First attempt: it costs nothing measurable.** The obvious follow-up was the
Train-on-Synthetic-Test-on-Real task this project already had — predict diabetes from
BMI, triglycerides, HDL and systolic, scored on 1,330 real NHANES individuals. Over ten
disjoint folds each:

| trained on | median AUC | range | retention |
|---|---:|---|---:|
| real NHANES (ceiling) | 0.677 | — | 100% |
| Synthea | 0.626 | 0.562–0.666 | 92.5% |
| carebundle | 0.625 | 0.604–0.634 | 92.3% |

Interquartile ranges overlap: **no separable difference.** A logistic model fits one
weight per feature, so it reads each feature's association with the *label* and barely
uses the dependence *between* features. Cross-domain dependence and single-label
predictive utility are dissociable, and TSTR is close to blind to the thing at issue.

*(A first pass compared one Synthea run against five carebundle runs and reported
Synthea ahead at 94.3% against 91.0%. Synthea's single value sat inside carebundle's
range. That is the same point-estimate error as quoting the lowest of three runs above,
and it is why both sides now get folds.)*

**Second attempt: a multi-criteria phenotype, which does consume the joint
distribution.** Four abnormalities — BMI ≥ 30, triglycerides ≥ 150, HDL < 40/50,
glucose ≥ 100 — scored by one rule on all three populations, ages 45–65:

| | ≥1 | ≥2 | **≥3** | ≥4 |
|---|---:|---:|---:|---:|
| NHANES (real) | 71.8% | 44.3% | **19.7%** | 6.2% |
| Synthea | 54.7% | 18.3% | **4.1%** | 0.8% |
| **carebundle** | 74.5% | 39.1% | **14.6%** | 3.6% |

Synthea produces the 3-of-4 phenotype at roughly a quarter of the real rate; this
package at three-quarters. On absolute error against NHANES that is **−15.6 points
against −5.2**. For anyone whose query counts patients meeting several criteria at once
— cohort selection, phenotyping, data-quality rules — that difference is the whole
answer, and TSTR could not see it.

**The mechanism I was about to publish for that was wrong.** The obvious reading is that
Synthea under-produces the phenotype because it draws the components independently.
Dividing each population's observed rate by what its *own* marginals imply under
independence:

| | dependence ratio at ≥3 |
|---|---:|
| NHANES (real) | 1.59× |
| Synthea | **2.10×** |
| carebundle | 1.45× |

**Synthea clusters more than reality, not less.** Its low phenotype rate comes from mild
marginals — glucose ≥ 100 in 8.7% of its patients against 47.4% of real ones — and the
over-clustering is coherent with the correlation table above, where its
glucose/triglyceride pair is over-coupled at double the real value while weight/HDL is
absent. Synthea's dependence is not missing; it is **shaped by module co-membership**,
tight inside a module and absent across them. This package is nearer reality on both the
marginals and the ratio, but the ratio error runs the other way: 1.45 against 1.59 is
slightly *under*-clustered.

Without that control a correct-looking headline number would have shipped with an
inverted explanation behind it. `carebundle.benchmark.cooccurrence` always prints the
control beside the rate, and a test asserts a synthetic population with genuinely
independent components scores 1.0.

### The residual is tail dependence, and a t-copula does not fix it

After the correlations were corrected, the healthy profile still produced three-of-four
metabolic abnormalities at a dependence ratio of 1.55 against a real 1.77. The suspected
cause was the copula family: a **Gaussian copula has zero tail dependence**, so joint
extremes are under-produced by construction, and a three-of-four threshold query
measures joint extremes precisely.

Measured, conditional co-occurrence above each variable's 80th centile — independence
would be 0.20:

| pair | NHANES | carebundle |
|---|---:|---:|
| triglycerides ~ HDL | 0.48 | 0.36 |
| glucose ~ HDL | 0.36 | 0.26 |
| glucose ~ triglycerides | 0.32 | 0.28 |
| BMI ~ HDL | 0.31 | 0.30 |

So the diagnosis holds: real data clusters in the tail more than this package does, on
four of six pairs.

**The obvious remedy was tested and rejected.** A Student-t copula has tail dependence
that grows as its degrees of freedom fall, and ν → ∞ recovers the Gaussian. At the same
Pearson correlation:

| pair | Gaussian | t, ν=5 | t, ν=3 | NHANES |
|---|---:|---:|---:|---:|
| triglycerides ~ HDL | 0.396 | 0.418 | 0.431 | 0.48 |
| glucose ~ HDL | 0.274 | 0.301 | 0.318 | 0.36 |

Even at ν=3 — implausibly heavy — it closes roughly a third of the gap. It would also
apply tail dependence to *every* pair including those that genuinely have none, require
a Student-t quantile function implemented without scipy, and move seeded output. Closing
this properly needs pair-specific copulas, which is a vine-copula architecture rather
than a parameter change, and is not scheduled.

One caveat on the target itself: the NHANES tail figures come from roughly 1,200 people
per sex, so 0.48 carries a standard error near 0.05 and the gap is about 1.7 of those.
Suggestive, not decisive — which is a further reason not to re-architect for it.

**What the same instrument says about this package.** Its dependence ratio is 1.45
against a real 1.59, so it is slightly *under*-clustered, and its glucose marginal puts
35.2% of the cohort above 100 mg/dL against a real 47.4%. Both push the 3-of-4 rate
below reality, and the second is the larger term.

The obvious fix was tried and does not work. Six analytes exceed this project's own
"visibly skewed" threshold of 1.3 in the stratum their profile draws from — AST 3.69,
creatinine 3.41, ALT 2.58, glucose 1.51, bilirubin 1.43, alkaline phosphatase 1.34 —
while using a symmetric marginal, and the package already ships a log-normal family it
uses for triglycerides and HbA1c. Switching glucose to it moves P(≥100) from **18.9% to
18.6%**, the wrong way, and the 97.5th percentile from 109.5 to 110.6 against a measured
**123.0**. Both families are fitted from the quartiles, so both reproduce the IQR and
both miss the same tail: the real p97.5 sits 2.6 IQRs above its median where a normal
puts it at 1.45.

**Fixed in 0.5.0, by dropping the family rather than choosing a better one.**
`EmpiricalMarginal` interpolates the measured quantile function at eleven levels from
p1 to p99 and assumes nothing about shape. Mean absolute error against true exceedance
rates, across ten analyte/sex cells:

| fit | mean \|error\| | worst |
|---|---:|---:|
| fitted normal (shipped through 0.4.0) | 4.43 pts | 8.20 |
| 9 knots, p2.5–p97.5 | 1.57 | 2.53 |
| **11 knots, p1–p99** | **0.73** | **1.84** |

The grid is part of the method. Five knots is *worse* than the normal on heavy skew —
linear interpolation across a wide q3-to-p97.5 gap spreads mass uniformly where the real
density is falling, overshooting ALT to 12.1% against a true 5.5%. And a grid stopping at
p2.5 must be rescaled onto its own support, which pulls the tail back in and costs more
than the extra knots buy.

The same change caught a larger problem beside it: the eleven comprehensive metabolic
panel analytes were **hand-set round numbers** — ALT at mean 25.0, SD 11.0 — with no sex
stratification at all, while NHANES carried every one of them. Their mean absolute error
was 2.45 points and is now 0.81, and ALT's true mean is 19.37 rather than 25.0.

**Deviation, not CI coverage, is the metric.** Synthea's sample here is 492 panels
against 2,998, so its confidence intervals are roughly twice as wide and cover the
target more often by luck. Scoring "cells whose CI covers NHANES" would reward having
less data; it gives Synthea 4/14 and this package 7/14, and that comparison is an
artefact of sample size rather than a finding.

Three cells carry most of the difference, and they point at the mechanism:

| pair | NHANES | Synthea | reading |
|---|---:|---:|---|
| triglycerides ~ HDL (M) | −0.297 | **+0.134** | wrong sign, CI [0.006, 0.258] excludes zero |
| BMI ~ HDL (F / M) | −0.303 / −0.264 | +0.012 / +0.028 | absent, wrong sign in both sexes |
| glucose ~ triglycerides (F) | 0.234 | **0.473** | roughly double |

Read together they are one story rather than three defects. Synthea's dependence comes
from **module co-membership**: a patient inside the diabetes module gets a raised
glucose and raised triglycerides together, so that pair is over-coupled at twice the
real value — while weight and HDL, which no single module links, are uncorrelated at
+0.01 against a real −0.30. The inverse triglyceride/HDL relationship in men, one of the
most reproducible findings in lipidology, comes out positive.

**This package was in the same position four days ago.** Its own weight/HDL correlation
was +0.01 against the same −0.26 until it was measured in 0.4.0-dev, and every marginal
passed the whole time. The difference is not that a copula is inherently better than a
module graph — it is that dependence you do not measure is dependence you do not have,
in either architecture, and only one of the two currently checks.

Caveats that belong next to the numbers: Synthea simulates Massachusetts against a
national NHANES reference, which correlations are far less sensitive to than
prevalences but not immune. And this package fits correlations *within* stratum and then
mixes profiles, so a mixture carries between-group covariance on top — which is why its
own glucose/triglyceride cell is its worst at 0.149, sitting above the pooled target
rather than below it.

## Results

| Measure | Synthea (measured) | **carebundle** | Real (US) | Real (MA) |
|---|---:|---:|---:|---:|
| Controlling high blood pressure (CBP) | 74.8% | **68.8%** | 69.7% | 74.5% |
| Colorectal cancer screening | 68.7% | *not modelled* | 69.8% | 77.3% |
| COPD 30-day mortality | 0.7% | *not modelled* | 8.0% | 7.0% |
| Complications after hip/knee replacement | 0% | *not modelled* | 2.8% | 2.9% |

**The three "not modelled" rows are published deliberately.** A benchmark that quietly
dropped the measures it loses would be worthless as evidence. *Not modelled* is a
different claim from 0%, and the measure engine keeps them distinguishable: a zero
denominator is reported as a zero denominator, never as a rate.

**They are also not going to be modelled**, and the reason is licensing rather than
effort. All three need `Procedure` resources, and the procedures in question have no
realistic public-domain coding:

- Screening colonoscopy is **CPT 45378** in the ambulatory setting where screening
  happens; CPT is AMA-licensed. Hip and knee replacement likewise.
- SNOMED CT needs an affiliate licence and bars redistribution.
- ICD-10-PCS *is* public domain and US Core accepts it, so `0DJD8ZZ` would validate —
  but PCS is inpatient facility coding, and no real US ambulatory system emits it for a
  screening colonoscopy. Conformant and wrong. Checked and rejected rather than used,
  because winning a benchmark row with a code no real system emits would forfeit the
  realism claim the row is meant to evidence.

The measures this project can reach are those defined over labs, vitals and diagnoses —
which it codes with LOINC and ICD-10-CM. That is a real and narrow boundary, and it is
better stated than discovered.

### Controlling high blood pressure, in detail

Denominator is the HEDIS/NCQA definition — ages 18–85, coded hypertension diagnosis,
an outpatient encounter, and a recorded blood pressure. Numerator is a most-recent
reading below **140/90**, with both components required.

| Population | Denominator | CBP rate |
|---|---:|---:|
| `hypertension` profile | 1500 | 69.9% |
| `type2_diabetes` profile | 1044 | 71.6% |
| `ckd_stage3` profile | 1180 | 72.8% |
| **Mixed cohort, ages 45–65 (default)** | **1803 / 4000** | **69.3%** |
| **Mixed cohort, ages 18–85 (matched to Synthea)** | **667 / 1500** | **68.8%** |
| `healthy` profile | 0 | *not in denominator* |

Every row moved by up to two points in 0.4.0-dev, when the metabolic cluster changed the
joint sampling and with it every profile's RNG stream. The mixed-cohort figure was 71.5%
before that change and is 69.3% after; the titration narrative below quotes the earlier
number because that is what the experiment measured at the time. The 18–85 row exists
only so the Synthea comparison at the top of this document scores a population of the
same shape.

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
71.5%. Change either cited input and the number moves — which is exactly what happened
when titration was added, and is documented below rather than smoothed over.

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

## Non-adherence: a prediction that failed, and was not shipped

The previous section predicted that adding non-adherence "should push the rate down".
It does — by far too much to be right.

| Model | CBP rate |
|---|---:|
| Current (no explicit adherence term) | 74.7% |
| 45% of patients take nothing ([Abegaz 2017 meta-analysis](https://pubmed.ncbi.nlm.nih.gov/28121920/)) | 50.4% |
| Effect scaled by proportion-of-days-covered (62.2%) | 49.3% |
| **Real-world comparators** | **69.7% – 74.5%** |

Both formulations land roughly 20 points **below** reality. The prediction was right
about direction and badly wrong about magnitude, and the honest conclusion is that the
naive adherence term is a worse model, not a missing one. It is therefore **not
shipped**. Two reasons it fails:

- **The population-wide adherence figures do not transfer to this denominator.** HEDIS
  CBP counts patients who are diagnosed *and* have an outpatient encounter — people
  engaged enough with care to show up. Adherence meta-analyses are drawn from a much
  broader population. Applying the broader figure to the narrower denominator imports
  a selection effect that the denominator has already excluded.
- **"Non-adherent" is not "untreated".** A patient with 62% days covered takes most of
  their doses and gets most of the benefit. Modelling them as receiving nothing is a
  category error, and the PDC-scaled variant fails for the related reason that response
  is not linear in coverage.

Recording this matters more than the result. The rate is close to reality *without*
this term, so a naive version would have made the benchmark worse while sounding more
sophisticated — and the reason it is excluded is that it contradicts the data by 20
points, which is model falsification rather than parameter fitting. If adherence is
modelled later it needs a dose-response formulation and a denominator-matched source.

## Why there is no second measure: CMS122, and what it taught

The obvious candidate for a second measure was **CMS122, Diabetes: HbA1c Poor Control
(>9%)**. It needs only a diagnosis and a lab result, both of which this project codes
with ICD-10-CM and LOINC, so unlike the colonoscopy measures it is not blocked by
licensing. It is blocked by something more interesting.

**The measure has no single national rate.** CMS's own
[2024 quality benchmarks](https://www.cms.gov/files/document/2024-quality-benchmarks.csv)
publish three, for the same measure in the same year:

| Collection type | Average performance rate |
|---|---:|
| Medicare Part B Claims | 11.70% |
| MIPS CQM | 27.30% |
| eCQM (CMS122v12) | 43.53% |

A four-fold spread is not measurement noise, and the numerator definition explains it:

> "Patients whose most recent HbA1c level (performed during the measurement period) is
> >9.0% **or is missing, or was not performed** during the measurement period"

CMS122 does not measure glycaemic control. It measures glycaemic control **plus
testing completeness**, summed into one number. The more a collection method depends on
complete EHR capture, the more untested patients inflate the rate — which is exactly the
ordering above.

**A generator with perfect data capture cannot reproduce that.** Every diabetic here has
an HbA1c, so this project would always score at the "everyone was tested" floor. Our
generated rate above 9.0% is 12.9%, which sits near the claims figure and near NHANES's
measured 12.9% — and that agreement would be *misleading* to publish as reproducing
CMS122, because the measure it would claim to reproduce is counting something else.

Two things follow, and both are worth more than the row would have been.

**The blocker generalises.** Any quality measure whose numerator includes "or is
missing" is partly a data-completeness measure, and synthetic data with complete capture
can only ever reproduce the clinical half. That is a structural limit on benchmarking
synthetic generators against real quality measures, and it applies to Synthea equally.

**It is also a use for the imperfection module.** `carebundle.imperfection` exists to
omit fields on purpose. A future version could model the missing-result component
explicitly and reproduce the full measure — the only route to CMS122 that would not be
quietly comparing two different quantities.

**A caveat this exposed in the CBP measure above.** HEDIS CBP has the same shape: a
member with no blood-pressure reading counts as not controlled. This implementation
instead requires a reading to enter the denominator. It makes no difference to the
number, because every generated patient has one — but it means the 71.5% figure is a
*clinical* control rate compared against real-world rates that blend control with
capture. The real-world comparators are therefore, if anything, slightly pessimistic
relative to what is being measured here.

## Remaining caveats

- The comparators are from 2019 and reflect the plans and years measured then. The
  national HEDIS figure has sat in the low-to-mid 60s in other years.
- Titration is modelled here as an equilibrium: the recorded pressure is where a
  titrated patient ends up, which is the right value for a most-recent-reading measure.
  The trajectory behind it is now available separately via `generate_history`, which
  emits the same patient across several reviews as therapy is escalated.

## What this does and does not establish

It establishes that a distributional model reproduces a published outcome measure from
independently cited inputs, checked in CI, landing 0.9 points from the US national rate.

**It does not establish any advantage over Synthea on this measure.** Measured on the
same day with the same code, Synthea scores 74.8% against its own Massachusetts
reference and this package 68.8% against its national one. Both are right. The earlier
version of this document claimed a 71.5-point gap that no longer exists, and the
rewrite above explains why.

It does not establish that this is a better synthetic data generator than Synthea.
Synthea covers 231 conditions, a lifetime per patient, and three of the four measures
in this very table. On breadth it is not close, and [ROADMAP.md](ROADMAP.md) does not
propose competing there.

**Where the difference actually is**, now that the outcome-measure claim has gone: this
package grades every one of its 58 fidelity checks by what a pass proves and says out
loud that 1 is out-of-sample; it derives its marginals, correlations and treatment
effects from named sources that regenerate byte-identically; and it models joint
structure within a visit — adiposity against HDL, glycaemia against triglycerides — that
a per-condition module graph does not represent. Those are checkable claims about
evidence discipline. "Synthea scores zero" was a checkable claim too, which is how it
came to be withdrawn.

## Sources

- [Chen J et al., "The validity of synthetic clinical data … (Synthea) using clinical quality measures", *BMC Med Inform Decis Mak* 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/)
- [NCHS Data Brief: Hypertension Prevalence, Awareness, Treatment, and Control, US, Aug 2021–Aug 2023](https://www.ncbi.nlm.nih.gov/books/NBK612761/)
- [Law MR, Wald NJ, Morris JK, "Value of low dose combination treatment with blood pressure lowering drugs", *BMJ* 2003;326:1427](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC162261/)
- [Blood pressure-lowering efficacy of antihypertensive drugs and their combinations, *Lancet* 2025](https://pubmed.ncbi.nlm.nih.gov/40885583/)
- [NCQA HEDIS: Controlling High Blood Pressure (CBP)](https://www.ncqa.org/report-cards/health-plans/state-of-health-care-quality-report/controlling-high-blood-pressure-cbp/)
