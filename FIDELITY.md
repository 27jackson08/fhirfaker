# Fidelity Report

Generated distributions checked against published clinical relationships.
Regenerated per release from n=10,000 draws, seed 20260101.

## How much each check proves

Checks are **graded by evidential strength**, because they are not equivalent and a flat pass count implies more than most of them carry. Reporting statistical similarity as though it established clinical validity is the specific criticism levelled at synthetic-data evaluation in [arXiv:2606.08903](https://arxiv.org/abs/2606.08903), and it is easier to avoid by grading than by adding more checks.

| Grade | Checks | What a pass means |
|---|---:|---|
| **out_of_sample** | 1 | A published relationship the model was NOT fitted to. This is the only category that is evidence of fidelity in the sense the word implies. |
| **calibration** | 31 | Verifies a marginal fitted to a published source survived truncation and the copula. Meaningful — this is where truncation attenuation was caught — but in-sample by construction. |
| **round_trip** | 2 | Verifies the sampler reproduces a value it was configured with. Proves the engine works; proves nothing about whether the configured value is right. |
| **identity** | 4 | Computed from its own inputs. Cannot fail unless the code is broken, so it is a regression test, not evidence of fidelity. |

**Read the top row first.** Only 1 of 38 checks is genuinely out-of-sample. The rest establish self-consistency, which is necessary but is a weaker claim than the phrase 'fidelity report' suggests on its own.

### out_of_sample (1)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| CMS Controlling High Blood Pressure | 0.75 | 0.72 | +0.03 | ±0.09 | Chen 2019 (CMS/HEDIS) | PASS |

### calibration (31)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| ADAG slope | 27.96 | 28.7 | -0.741 | ±1 | Nathan 2008 | PASS |
| ADAG R^2 | 0.8447 | 0.84 | +0.00469 | ±0.02 | Nathan 2008 | PASS |
| glucose at HbA1c 6.5% | 141.1 | 139.8 | +1.3 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 8.0% | 183.1 | 182.9 | +0.184 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 9.5% | 225 | 225.9 | -0.927 | ±5 | Nathan 2008 | PASS |
| systolic/diastolic correlation | 0.743 | 0.743 | +4.68e-05 | ±0.06 | NHANES 2017-2020 | PASS |
| triglyceride/HDL correlation | -0.2751 | -0.2969 | +0.0218 | ±0.06 | NHANES 2017-2020 | PASS |
| diabetic obesity rate | 0.638 | 0.612 | +0.026 | ±0.05 | NHANES 2017-2020 | PASS |
| typical-adult median BMI | 29.98 | 28.8 | +1.18 | ±1.5 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/F) | 5.601 | 5.6 | +0.00137 | ±0.168 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/M) | 5.604 | 5.6 | +0.00365 | ±0.168 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/F) | 89.32 | 88 | +1.32 | ±10.6 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/M) | 93.5 | 94 | -0.505 | ±11.3 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/F) | 200.3 | 198 | +2.28 | ±11.9 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/M) | 190 | 188.5 | +1.53 | ±11.3 | NHANES 2017-2020 | PASS |
| hdl median (healthy/F) | 59.78 | 57 | +2.78 | ±4.56 | NHANES 2017-2020 | PASS |
| hdl median (healthy/M) | 48.48 | 47 | +1.48 | ±3.76 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/F) | 0.7508 | 0.73 | +0.0208 | ±0.0584 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/M) | 0.985 | 0.97 | +0.015 | ±0.0776 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/F) | 76.45 | 74.9 | +1.55 | ±4.49 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/M) | 87.34 | 85 | +2.34 | ±5.1 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/F) | 160.3 | 160.1 | +0.186 | ±3.2 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/M) | 173.5 | 173.6 | -0.079 | ±3.47 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/F) | 7.046 | 7.1 | -0.0543 | ±0.355 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/M) | 7.386 | 7.3 | +0.0856 | ±0.365 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/F) | 118.5 | 122 | -3.52 | ±14.6 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/M) | 132.4 | 132 | +0.403 | ±15.8 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/F) | 50.25 | 49 | +1.25 | ±3.92 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/M) | 43.56 | 42 | +1.56 | ±3.36 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/F) | 85.18 | 83.15 | +2.03 | ±6.65 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/M) | 95.78 | 92.6 | +3.18 | ±7.41 | NHANES 2017-2020 | PASS |

### round_trip (2)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| CKD stage-3 eGFR within band | 1 | 1 | +0 | ±0 | KDIGO 2012 | PASS |
| T2DM hypertension comorbidity | 0.6952 | 0.7 | -0.0048 | ±0.0259 | profile config | PASS |

### identity (4)

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| eGFR consistent with creatinine | 0 | 0 | +0 | ±1e-09 | CKD-EPI 2021 | PASS |
| ICD-10 stage code matches eGFR | 1 | 1 | +0 | ±0 | ICD-10-CM | PASS |
| LDL consistent with panel (Friedewald) | 0 | 0 | +0 | ±1e-09 | Friedewald 1972 | PASS |
| BMI consistent with height and weight | 0 | 0 | +0 | ±1e-09 | WHO | PASS |

**38/38 passed.**

## Why R^2 is the load-bearing number

The ADAG relationship is `eAG = 28.7 x HbA1c - 46.7` with **R^2 = 0.84**. A
generator that derives glucose deterministically from HbA1c reproduces the
line perfectly and scores R^2 = 1.0 — visibly artificial to anyone who plots
it. Reproducing the residual scatter is the actual claim, so that check is
two-sided: too tight a correlation fails just as a too-loose one does.

## Marginals are estimates, dependence is cited

The marginal distributions are clinically-informed estimates for a 45-65
adult population, not fits to a named cohort. What comes from the literature
is the *dependence* structure: the HbA1c/glucose correlation is derived from
the published R^2, and eGFR is computed from creatinine by CKD-EPI 2021
rather than sampled. Calibrating marginals against NHANES is Phase 4.
