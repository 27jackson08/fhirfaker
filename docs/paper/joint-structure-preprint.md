# Marginal validation cannot detect joint-structure failure in synthetic health data

**Jackson Bomongcag**

*Preprint draft. Every figure is reproducible from the commands given; the code is at
https://github.com/27jackson08/fhirfaker under Apache 2.0.*

---

## Abstract

Synthetic patient data is usually validated one variable at a time: each distribution is
compared against a reference and the generator is judged by how many match. We show this
is insufficient in a way that is easy to demonstrate and hard to see. We introduce a
reproducible benchmark that measures **cross-domain dependence** — whether analytes from
different body systems co-vary as they do in real patients — and a **multi-criteria
co-occurrence** measure with an accompanying independence control, and apply both to four
generators spanning rule-based simulation, copula sampling, and two learned architectures.

Every generator we tested has correct or near-correct marginals. Their joint structure
differs by a factor of four. A widely used rule-based simulator produces the
triglyceride/HDL relationship with the **wrong sign** in men; a variational autoencoder
holds perfect correlation-sign agreement at every training budget while producing a
multi-criteria phenotype at 2.0% against a real 15.0%; and a GAN's co-occurrence rate
swings from 36.7% to 9.1% to 14.5% across training budgets against a stable truth, driven
by one hyperparameter. None of these is visible from marginal checks, and none is visible
from a co-occurrence rate reported without its independence control.

We also report four negative results, including one that inverted our own initial
explanation of the main finding.

**Conflict of interest.** The author maintains one of the four generators evaluated. Its
figures are in the same tables, it is worse than the leading alternative on breadth by two
orders of magnitude, and a headline comparative claim previously made for it was withdrawn
during this work after measurement contradicted it (§7).

---

## 1. Introduction

Synthetic health data exists so that people can build and test software without touching
real patient records. Its usefulness depends entirely on whether it resembles reality in
the ways the consuming task cares about.

The dominant validation practice is marginal: check that age looks like age, that HbA1c
looks like HbA1c, and report the fraction of distributions that match. This is necessary.
Our claim is that it is badly insufficient, because a great many real tasks read the
*joint* distribution:

- **Phenotype and cohort queries.** "Patients with three of these five abnormalities" is a
  function of how the abnormalities co-occur, not of any one marginal.
- **Risk scores.** FIB-4, ASCVD, and CHA₂DS₂-VASc combine several inputs; their output
  distribution depends on the inputs' dependence.
- **Data-quality rules.** A rule flagging low albumin with normal calcium is testing a
  relationship, not a value.

A generator can pass every marginal check and fail all three. We show that several
widely used generators do.

## 2. Contributions

1. A **reproducible cross-domain dependence benchmark** that reads any FHIR bundle
   directory or tabular record set, so generators of different architectures are scored by
   one implementation (§4.1).
2. A **multi-criteria co-occurrence measure with an independence control** that separates
   "the components are independent" from "the marginals are mild" — two failures that look
   identical in the headline rate and need opposite fixes (§4.2).
3. **Measurements of four generators** plus one assessed and excluded, with the exclusion
   reported rather than left as a gap (§5, §6).
4. **Four negative results**, including a refutation of our own first explanation for the
   main finding (§7).

## 3. Related work

Chen et al. [1] validated Synthea against four CMS quality
measures and found it tracked reality on the process measure and scored 0% on the outcome
measures. Hodges et al. [2] reported that 100% of Synthea's
type-2 diabetics carried an amputation.

**Both results are stale and we retract our own reliance on them.** Measured against
Synthea `d9d07a6` (August 2026), blood-pressure control is **74.4%**, not 0%, and the
diabetic amputation rate is **0.56%** (3 of 537), against a real-world incidence near 5 per
1,000 per year. This matters methodologically: a citation cannot fail in continuous
integration the way a measurement can, and the field's shared picture of a tool's weakness
can outlive the weakness by years.

Evaluation frameworks for synthetic health data conventionally report *fidelity*, *utility*
and *privacy*. Fidelity is generally operationalised marginally. Our contribution sits
inside fidelity and argues that its usual operationalisation misses a class of failure.

## 4. Method

All measurements use NHANES 2017–March 2020, restricted to ages 45–65, stratified by sex,
using the non-diabetic stratum unless stated. Reference figures come from held-out data
where a generator was trained (§5.3).

### 4.1 Cross-domain dependence

For each of seven analyte pairs spanning adiposity, glycaemia and lipids, we compute the
Pearson correlation within sex, and report the mean absolute deviation from the NHANES
value across the resulting cells, together with sign agreement.

One contemporaneous panel is taken per patient — the date carrying the most analytes — so
values are compared as they were measured rather than across a simulated lifetime.
Comparing values recorded years apart would understate dependence for a longitudinal
generator while leaving a single-visit one unaffected, biasing the comparison.

```
python -m carebundle.benchmark.dependence --fhir-dir ./pop/fhir
```

### 4.2 Multi-criteria co-occurrence, and why the control is mandatory

We count patients meeting three or more of four abnormalities: BMI ≥ 30, triglycerides
≥ 150 mg/dL, HDL < 40 (M) / 50 (F), glucose ≥ 100. These are the ATP III metabolic
syndrome criteria with waist circumference replaced by BMI, because no generator tested
emits waist. **The resulting rate is therefore not ATP III prevalence** and is not compared
to a published ATP III figure; all populations are scored by one rule with NHANES as the
reference.

Alongside the rate we report the **independence ratio**: the observed rate divided by what
that population's *own* marginals imply if the four criteria were independent, enumerated
exactly over the sixteen combinations. A ratio of 1.0 means the components behave
independently; real NHANES is 1.76.

This control is not optional, and §7.2 records what happens without it.

### 4.3 Scope

The benchmark reads FHIR bundles or plain tabular records. Records missing an analyte are
skipped rather than imputed: a generator that omits a value has not produced a scorable
patient, and imputing one flatters it invisibly.

## 5. Generators evaluated

| generator | kind | access to NHANES |
|---|---|---|
| Synthea `d9d07a6` | rule-based state machines | none |
| carebundle 0.5.0 | Gaussian copula | fitted to published aggregates |
| CTGAN 0.12.1 | conditional GAN | trained on individual rows |
| TVAE 0.12.1 | variational autoencoder | trained on individual rows |

**Access is deliberately unequal and must be read with the results.** The learned models
have the most direct possible access to the dependence structure; the rule-based simulator
has none. This is a feature of the design: if a model trained on the data itself still
fails, the failure is not an artefact of hand-written rules.

### 5.1 A generator assessed and excluded

PySynthea (`tietai-synthea` 1.0.1) was the intended fifth. Its FHIR export emits
Observations **without values**: systolic, diastolic, height, weight, glucose, HDL,
triglycerides, HbA1c, ALT and AST are all present and all valueless, with `status: "final"`
and no `dataAbsentReason`. Only 15% of its observations carry a `valueQuantity`, and none of
those are analytes any measure here reads. The HL7 validator returns 166 errors and 266
warnings on a single bundle.

We report this rather than omitting the generator silently. It is a young project and its
module coverage and JVM-free install are real.

### 5.2 Reproducibility of the sources

Synthea does not produce an identical population from a fixed seed: three runs of
`d9d07a6` with `-p 1200 -s 42` gave 1,462, 1,449 and 1,447 bundles, because `-p` counts
living patients and generation is concurrent. Figures below are medians across those runs;
observed spread was 0.002 on the CBP rate and 0.017 on the mean dependence deviation.

### 5.3 Training protocol for learned models

606 training rows / 607 held out, split once. All correlation references for the learned
models are computed on the held-out half, so no model is scored against rows it was fitted
on. Epochs swept at 300, 1000 and 3000; CPU only; no further hyperparameter search.

## 6. Results

### 6.1 The headline table

| generator | mean \|dev\| | sign | P(≥3) | ratio |
|---|---:|---:|---:|---:|
| **NHANES (truth)** | **0.000** | **12/12** | **15.0%** | **1.76×** |
| Synthea | 0.208 | 10/14 | 4.1% | 2.10× |
| carebundle | 0.055 | 14/14 | 15.8% | 1.55× |
| CTGAN, 3000 ep | 0.074 | 12/12 | 14.5% | 1.59× |
| TVAE, 3000 ep | 0.059 | 12/12 | 10.6% | 1.80× |

Cell counts differ (8 for tabular sources carrying four analytes, 14 for FHIR sources also
emitting weight and HbA1c), so deviations are not over identical pair sets.

### 6.2 Marginals are not the problem

Every generator here has broadly correct marginals; the joint structure differs
four-fold. Three specific failures:

- **Synthea reverses a relationship.** Triglycerides against HDL in men comes out at
  **+0.134** (95% CI 0.006–0.258, excluding zero) against a real **−0.297** — one of the
  most reproducible findings in lipidology, backwards. BMI against HDL is +0.01/+0.03
  against a real −0.30/−0.26: absent in both sexes.
- **Synthea's dependence is shaped by module co-membership.** Glucose against
  triglycerides is over-coupled at 0.473 against a real 0.234, because a patient inside the
  diabetes module receives both together, while weight and HDL — which no single module
  links — are uncorrelated.
- **carebundle was in the same state until it was measured.** Its weight/HDL correlation
  was +0.01 against the same −0.26 while every marginal passed. The defect is not
  characteristic of one architecture; it is characteristic of not looking.

### 6.3 Training budget dominates joint structure in learned models

| model | epochs | P(≥3) | ratio | sign |
|---|---:|---:|---:|---:|
| CTGAN | 300 | 36.7% | 0.99× | 8/12 |
| CTGAN | 1000 | 9.1% | 1.05× | 7/12 |
| CTGAN | 3000 | 14.5% | 1.59× | 12/12 |
| TVAE | 300 | 2.0% | 2.36× | 12/12 |
| TVAE | 1000 | 7.5% | 2.29× | 12/12 |
| TVAE | 3000 | 10.6% | 1.80× | 12/12 |

Both converge by 3000 epochs. Both are badly wrong before it, **in opposite directions**:
CTGAN drifts toward independence, TVAE over-couples. A practitioner who tuned one would
learn nothing transferable about the other.

**The most important row is TVAE at 300 epochs.** Sign agreement is perfect — 12 of 12 —
while the co-occurrence rate is 2.0% against a real 15.0%. The obvious sanity check on a
correlation table is entirely uninformative here. Mean deviation is no better: it is
*lower* at 300 epochs (0.100) than at 1000 (0.114) while the joint structure is wrong
throughout.

A run trained on all 1,213 rows, including the evaluation half, is barely better than the
fair 3,000-epoch run, so the binding constraint is training budget rather than sample size.

### 6.4 The independence control is what separates the failure modes

Synthea's 4.1% co-occurrence looks like missing dependence. It is not: its ratio is
**2.10×**, meaning it clusters *more* than reality. The low rate comes from mild marginals
— glucose ≥ 100 in 8.7% of its patients against 47.4% of real ones.

CTGAN at 300 epochs has the opposite pathology: ratio 0.99 (genuinely independent) with a
co-occurrence rate more than twice reality, from marginals that are too abnormal.

Both look like "the rate is wrong". The fixes are opposite. Only the pair of numbers
distinguishes them.

## 7. What did not work

### 7.1 Downstream utility did not detect the difference

We first tested whether the dependence gap costs anything using Train-on-Synthetic-Test-on-Real,
predicting diabetes from BMI, triglycerides, HDL and systolic pressure, scored on 1,330
real individuals. Over ten disjoint folds each, median AUC retention was **92.5% for
Synthea and 92.3% for carebundle, with overlapping interquartile ranges** — no separable
difference.

A logistic model fits one weight per feature: it reads each feature's association with the
*label* and barely uses dependence *between* features. Cross-domain dependence and
single-label predictive utility are dissociable, and TSTR is close to blind to the former.
This is a caution against treating downstream AUC as a sufficient fidelity check.

### 7.2 Our own explanation of the main finding was inverted

Having measured Synthea's 4.1% co-occurrence, we were about to publish the natural
mechanism: that it under-produces multi-criteria patients because it draws the components
independently. The independence control refuted this — Synthea clusters more than reality,
not less, and the cause is marginal.

Without the control, a correct headline number would have shipped with an inverted
explanation.

### 7.3 A heavier-tailed copula does not close the residual gap

Real data clusters in the tail more than a Gaussian copula can represent — conditional
co-occurrence above the 80th centile is 0.48 in NHANES against 0.36 for our copula on
triglycerides/HDL, where independence is 0.20. A Student-t copula is the standard remedy.
At matched Pearson correlations, **even ν = 3 closes about a third of the gap**, while
imposing tail dependence on every pair including those that have none. Closing it properly
requires pair-specific copulas.

### 7.4 A different marginal family does not fix tail exceedance

Where a fitted normal put 18.9% of non-diabetic women above a glucose of 100 mg/dL against
a true 22.7%, switching to a log-normal fitted from the same quartiles gave **18.6%** — the
wrong direction. Both families are parameterised from the median and IQR, so both reproduce
the middle and miss the same tail. Interpolating the measured quantile function directly
took mean absolute error on exceedance rates from 4.43 points to 0.73.

## 8. Limitations

- **One reference population.** NHANES, US, ages 45–65. Generalisation to other
  populations is untested.
- **Synthea simulates Massachusetts** against a national reference. Correlations are far
  less population-sensitive than prevalences, but this is not like-for-like.
- **Four analytes in the co-occurrence measure**, with BMI substituting for waist.
- **Two learned architectures**, both from one package, CPU-trained, with only an epoch
  sweep. No diffusion or copula-based learned model was tested.
- **Tail figures are uncertain.** The NHANES tail estimates rest on ~1,200 people per sex;
  the 0.48 above carries a standard error near 0.05.
- **Author conflict**, declared in the abstract.

## 9. Conclusion

Marginal validation is necessary and not sufficient. Across four generators of three
architectures, marginals were broadly right and joint structure varied four-fold, in ways
invisible to the checks the field customarily reports — including correlation sign
agreement, mean correlation deviation, and downstream AUC.

We recommend that synthetic health data be reported with (i) a cross-domain dependence
measure against a named reference, and (ii) a multi-criteria co-occurrence rate **with its
independence control**, since the rate alone cannot distinguish two failure modes that
require opposite remedies.

The strongest single caution we can offer is empirical rather than theoretical: at 300
epochs a variational autoencoder reproduced every correlation sign correctly while
producing the target phenotype at one seventh of its real rate. Every check most
practitioners run would have passed.

## References

1. Chen J, Chun D, Patel M, Chiang E, James J. The validity of synthetic clinical data:
   a validation study of a leading synthetic data generator (Synthea) using clinical
   quality measures. *BMC Med Inform Decis Mak.* 2019;19:44.
   doi:10.1186/s12911-019-0793-0
2. Hodges R, Tokunaga K, LeGrand J. A novel method to create realistic synthetic
   medication data. *JAMIA Open.* 2023;6(3):ooad052. doi:10.1093/jamiaopen/ooad052
3. Centers for Disease Control and Prevention, National Center for Health Statistics.
   National Health and Nutrition Examination Survey, 2017–March 2020 pre-pandemic data
   files. Hyattsville, MD.
4. Xu L, Skoularidou M, Cuesta-Infante A, Veeramachaneni K. Modeling tabular data using
   conditional GAN. *NeurIPS.* 2019. (CTGAN and TVAE, as implemented in `ctgan` 0.12.1.)
5. Walonoski J, Kramer M, Nichols J, et al. Synthea: an approach, method, and software
   mechanism for generating synthetic patients and the synthetic electronic health care
   record. *J Am Med Inform Assoc.* 2018;25(3):230–238. doi:10.1093/jamia/ocx079
6. Cruz R, Rey-Blanco D. PySynthea: a Python-native framework for scalable synthetic
   healthcare data generation. *arXiv:2606.28346.* 2026.
7. Expert Panel on Detection, Evaluation, and Treatment of High Blood Cholesterol in
   Adults. Executive summary of the third report (ATP III). *JAMA.*
   2001;285(19):2486–2497. (Criteria adapted; see §4.2.)

## Reproduction

```bash
pip install carebundle
python -m carebundle.benchmark.suite --fhir Synthea=./pop/fhir --records CTGAN=./gen.csv
```

Recorded figures, the Synthea build identity, and the excluded generator's assessment are
committed under `carebundle/benchmark/data/`. A scheduled job re-runs the competitor
comparison monthly and fails if it moves, because a measurement taken once goes stale
exactly as a citation does.
