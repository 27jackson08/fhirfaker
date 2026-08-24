# Fidelity Report

Generated distributions checked against published clinical relationships.
Regenerated per release from n=10,000 draws, seed 20260101.

## How much each check proves

Checks are **graded by evidential strength**, because they are not equivalent and a flat pass count implies more than most of them carry. Reporting statistical similarity as though it established clinical validity is the specific criticism levelled at synthetic-data evaluation in [arXiv:2606.08903](https://arxiv.org/abs/2606.08903), and it is easier to avoid by grading than by adding more checks.

| Grade | Checks | What a pass means |
|---|---:|---|
| **out_of_sample** | 1 | A published relationship the model was NOT fitted to. This is the only category that is evidence of fidelity in the sense the word implies. |
| **calibration** | 50 | Verifies a marginal fitted to a published source survived truncation and the copula. Meaningful — this is where truncation attenuation was caught — but in-sample by construction. |
| **round_trip** | 3 | Verifies the sampler reproduces a value it was configured with. Proves the engine works; proves nothing about whether the configured value is right. |
| **identity** | 4 | Computed from its own inputs. Cannot fail unless the code is broken, so it is a regression test, not evidence of fidelity. |

**Read the top row first.** Only 1 of 58 checks is genuinely out-of-sample. The rest establish self-consistency, which is necessary but is a weaker claim than the phrase 'fidelity report' suggests on its own.

### out_of_sample (1)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| CMS Controlling High Blood Pressure | 0.746 | 0.72 | +0.026 | ±0.09 | Chen 2019 (CMS/HEDIS) | PASS |

### calibration (50)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| ADAG slope | 27.96 | 28.7 | -0.741 | ±1 | Nathan 2008 | PASS |
| ADAG R^2 | 0.8447 | 0.84 | +0.00469 | ±0.02 | Nathan 2008 | PASS |
| glucose at HbA1c 6.5% | 141.1 | 139.8 | +1.3 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 8.0% | 183.1 | 182.9 | +0.184 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 9.5% | 225 | 225.9 | -0.927 | ±5 | Nathan 2008 | PASS |
| T2DM hypertension comorbidity | 0.702 | 0.6997 | +0.0023 | ±0.0259 | NHANES 2017-2020 | PASS |
| systolic/diastolic correlation | 0.743 | 0.743 | +4.68e-05 | ±0.06 | NHANES 2017-2020 | PASS |
| triglyceride/HDL correlation | -0.2933 | -0.2969 | +0.00358 | ±0.06 | NHANES 2017-2020 | PASS |
| diabetic obesity rate | 0.6385 | 0.612 | +0.0265 | ±0.05 | NHANES 2017-2020 | PASS |
| typical-adult median BMI | 29.99 | 28.8 | +1.19 | ±1.5 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/F) | 5.601 | 5.6 | +0.00137 | ±0.168 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/M) | 5.604 | 5.6 | +0.00365 | ±0.168 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/F) | 88.97 | 88 | +0.972 | ±10.6 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/M) | 93.78 | 94 | -0.222 | ±11.3 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/F) | 200.3 | 198 | +2.28 | ±11.9 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/M) | 190 | 188.5 | +1.53 | ±11.3 | NHANES 2017-2020 | PASS |
| hdl median (healthy/F) | 59.7 | 57 | +2.7 | ±4.56 | NHANES 2017-2020 | PASS |
| hdl median (healthy/M) | 48.15 | 47 | +1.15 | ±3.76 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/F) | 0.7508 | 0.73 | +0.0208 | ±0.0584 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/M) | 0.985 | 0.97 | +0.015 | ±0.0776 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/F) | 76.38 | 74.9 | +1.48 | ±4.49 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/M) | 87.09 | 85 | +2.09 | ±5.1 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/F) | 160.3 | 160.1 | +0.186 | ±3.2 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/M) | 173.5 | 173.6 | -0.079 | ±3.47 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/F) | 7.033 | 7.1 | -0.0674 | ±0.355 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/M) | 7.242 | 7.3 | -0.0579 | ±0.365 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/F) | 118.8 | 122 | -3.22 | ±14.6 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/M) | 129.4 | 132 | -2.56 | ±15.8 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/F) | 50.17 | 49 | +1.17 | ±3.92 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/M) | 42.88 | 42 | +0.88 | ±3.36 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/F) | 84.82 | 83.15 | +1.67 | ±6.65 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/M) | 96.47 | 92.6 | +3.87 | ±7.41 | NHANES 2017-2020 | PASS |
| hemoglobin median (anaemia/F) | 11.12 | 11.3 | -0.183 | ±0.565 | NHANES 2017-2020 | PASS |
| hemoglobin median (anaemia/M) | 11.88 | 12.1 | -0.221 | ±0.605 | NHANES 2017-2020 | PASS |
| hematocrit median (anaemia/F) | 34.46 | 34.8 | -0.339 | ±1.74 | NHANES 2017-2020 | PASS |
| hematocrit median (anaemia/M) | 36.49 | 36.8 | -0.306 | ±1.84 | NHANES 2017-2020 | PASS |
| rbc median (anaemia/F) | 4.162 | 4.17 | -0.00838 | ±0.25 | NHANES 2017-2020 | PASS |
| rbc median (anaemia/M) | 4.212 | 4.22 | -0.00832 | ±0.253 | NHANES 2017-2020 | PASS |
| weight_kg/hdl correlation (healthy) | -0.2392 | -0.2584 | +0.0192 | ±0.06 | NHANES 2017-2020 | PASS |
| glucose/triglycerides correlation (healthy) | 0.1567 | 0.1873 | -0.0306 | ±0.06 | NHANES 2017-2020 | PASS |
| glucose/hdl correlation (healthy) | -0.1625 | -0.1785 | +0.016 | ±0.06 | NHANES 2017-2020 | PASS |
| hba1c/hdl correlation (healthy) | -0.2501 | -0.2492 | -0.000928 | ±0.06 | NHANES 2017-2020 | PASS |
| hba1c/triglycerides correlation (healthy) | 0.1118 | 0.131 | -0.0192 | ±0.06 | NHANES 2017-2020 | PASS |
| BMI/HDL correlation, emergent (healthy) | -0.2884 | -0.2998 | +0.0114 | ±0.09 | NHANES 2017-2020 | PASS |
| weight_kg/hdl correlation (type2_diabetes) | -0.2224 | -0.2333 | +0.0109 | ±0.06 | NHANES 2017-2020 | PASS |
| glucose/triglycerides correlation (type2_diabetes) | 0.2937 | 0.3081 | -0.0144 | ±0.06 | NHANES 2017-2020 | PASS |
| glucose/hdl correlation (type2_diabetes) | -0.1099 | -0.108 | -0.00193 | ±0.06 | NHANES 2017-2020 | PASS |
| hba1c/hdl correlation (type2_diabetes) | -0.08776 | -0.0795 | -0.00826 | ±0.06 | NHANES 2017-2020 | PASS |
| hba1c/triglycerides correlation (type2_diabetes) | 0.1467 | 0.159 | -0.0123 | ±0.06 | NHANES 2017-2020 | PASS |
| BMI/HDL correlation, emergent (type2_diabetes) | -0.2285 | -0.2056 | -0.0229 | ±0.09 | NHANES 2017-2020 | PASS |

### round_trip (3)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| CKD stage-3 eGFR within band | 1 | 1 | +0 | ±0 | KDIGO 2012 | PASS |
| anaemia profile is anaemic (F) | 1 | 1 | +0 | ±0 | WHO haemoglobin criteria | PASS |
| anaemia profile is anaemic (M) | 1 | 1 | +0 | ±0 | WHO haemoglobin criteria | PASS |

### identity (4)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| eGFR consistent with creatinine | 0 | 0 | +0 | ±1e-09 | CKD-EPI 2021 | PASS |
| ICD-10 stage code matches eGFR | 1 | 1 | +0 | ±0 | ICD-10-CM | PASS |
| LDL consistent with panel (Friedewald) | 0 | 0 | +0 | ±1e-09 | Friedewald 1972 | PASS |
| BMI consistent with height and weight | 0 | 0 | +0 | ±1e-09 | WHO | PASS |

**58/58 passed.**

## Clinical utility: does a model trained on this transfer?

Regenerate with `python -m carebundle.fidelity.transfer --data-dir <dir>`. Offline — it needs the NHANES individual records, which are not vendored, so it is not part of the CI suite and these figures are refreshed by hand when the calibration changes.

Train-on-Synthetic-Test-on-Real. A logistic model is fitted **entirely on generated patients**, then scored on 1,330 real NHANES individuals aged 45-65, and compared against the same model trained on real data with five-fold cross-validation.

| Model | AUC |
|---|---:|
| Train on **synthetic**, test on **real** | **0.621** |
| Train on real, test on real (5-fold) | 0.677 |
| **Retention** | **91.7%** |

Task: predict diagnosed diabetes from BMI, triglycerides, HDL and systolic pressure. Prevalence 21.0%; chance is 0.500.

**HbA1c is deliberately excluded.** Predicting diabetes from HbA1c is not a prediction, it is the diagnostic criterion restated, and any generator would score near 1.0. These features are the metabolic signal *around* the diagnosis — a genuinely hard task, which is why the real-data ceiling is only 0.677. A low ceiling leaves room to fail.

**This is graded `calibration`, not `out_of_sample`.** The individuals in the test set were never seen by the generator and no fitting targeted an AUC, which makes it a far stronger check than comparing a fitted median to its target. But the marginals and correlations came from the same survey, so it is not evidence from an independent source. Calling it out-of-sample would inflate the one category this report exists to keep honest.

## Why R^2 is the load-bearing number

The ADAG relationship is `eAG = 28.7 x HbA1c - 46.7` with **R^2 = 0.84**. A
generator that derives glucose deterministically from HbA1c reproduces the
line perfectly and scores R^2 = 1.0 — visibly artificial to anyone who plots
it. Reproducing the residual scatter is the actual claim, so that check is
two-sided: too tight a correlation fails just as a too-loose one does.

## Marginals and dependence both come from the survey

Marginals are fitted to NHANES 2017-March 2020, aged 45-65, within sex and
within stratum; `python -m carebundle.calibration.nhanes` regenerates them
and reproduces the committed file byte for byte. Some relationships are
instead computed rather than sampled — eGFR from creatinine by CKD-EPI 2021,
LDL by Friedewald, BMI from height and weight — and those are graded
`identity` above, because they cannot fail unless the code is broken.

**Marginals being right does not make the joint distribution right.** Every
analyte here matched its target while adiposity, glycaemia and lipids were
drawn independently of one another: the weight/HDL correlation was -0.26 in
the survey and +0.01 in generated output, and no marginal check could see it.
The metabolic-cluster rows above exist because that was measured. A Gaussian
copula fills any pair you do not specify with zero, so an unstated
correlation is a stated zero, and the model asserts independence it was never
asked to assert.
