# Fidelity Report

Generated distributions checked against published clinical relationships.
Regenerated per release from n=10,000 draws, seed 20260101.

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| ADAG slope | 28.59 | 28.7 | -0.113 | ±1 | Nathan 2008 | PASS |
| ADAG R^2 | 0.8436 | 0.84 | +0.00358 | ±0.02 | Nathan 2008 | PASS |
| glucose at HbA1c 6.5% | 139.9 | 139.8 | +0.0219 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 8.0% | 182.8 | 182.9 | -0.148 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 9.5% | 225.6 | 225.9 | -0.318 | ±5 | Nathan 2008 | PASS |
| CKD stage-3 eGFR within band | 1 | 1 | +0 | ±0 | KDIGO 2012 | PASS |
| eGFR consistent with creatinine | 0 | 0 | +0 | ±1e-09 | CKD-EPI 2021 | PASS |
| ICD-10 stage code matches eGFR | 1 | 1 | +0 | ±0 | ICD-10-CM | PASS |
| T2DM hypertension comorbidity | 0.6986 | 0.7 | -0.0014 | ±0.0259 | profile config | PASS |
| systolic/diastolic correlation | 0.6019 | 0.6 | +0.00193 | ±0.05 | profile config | PASS |
| LDL consistent with panel (Friedewald) | 0 | 0 | +0 | ±1e-09 | Friedewald 1972 | PASS |
| triglyceride/HDL correlation | -0.3738 | -0.4 | +0.0262 | ±0.05 | profile config | PASS |
| BMI consistent with height and weight | 0 | 0 | +0 | ±1e-09 | WHO | PASS |
| diabetic obesity rate | 0.6565 | 0.612 | +0.0445 | ±0.05 | NHANES 2017-2020 | PASS |
| typical-adult median BMI | 30.2 | 28.8 | +1.4 | ±1.5 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/F) | 5.601 | 5.6 | +0.00137 | ±0.168 | NHANES 2017-2020 | PASS |
| hba1c median (healthy/M) | 5.604 | 5.6 | +0.00365 | ±0.168 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/F) | 89.32 | 88 | +1.32 | ±10.6 | NHANES 2017-2020 | PASS |
| triglycerides median (healthy/M) | 93.5 | 94 | -0.505 | ±11.3 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/F) | 200.3 | 198 | +2.28 | ±11.9 | NHANES 2017-2020 | PASS |
| cholesterol_total median (healthy/M) | 190 | 188.5 | +1.53 | ±11.3 | NHANES 2017-2020 | PASS |
| hdl median (healthy/F) | 59.74 | 57 | +2.74 | ±4.56 | NHANES 2017-2020 | PASS |
| hdl median (healthy/M) | 48.05 | 47 | +1.05 | ±3.76 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/F) | 0.7508 | 0.73 | +0.0208 | ±0.0584 | NHANES 2017-2020 | PASS |
| creatinine median (healthy/M) | 0.985 | 0.97 | +0.015 | ±0.0776 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/F) | 76.89 | 74.9 | +1.99 | ±4.49 | NHANES 2017-2020 | PASS |
| weight_kg median (healthy/M) | 87.33 | 85 | +2.33 | ±5.1 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/F) | 160.3 | 160.1 | +0.186 | ±3.2 | NHANES 2017-2020 | PASS |
| height_cm median (healthy/M) | 173.5 | 173.6 | -0.079 | ±3.47 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/F) | 7.379 | 7.4 | -0.0211 | ±0.37 | NHANES 2017-2020 | PASS |
| hba1c median (type2_diabetes/M) | 7.383 | 7.5 | -0.117 | ±0.375 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/F) | 120.4 | 122 | -1.6 | ±14.6 | NHANES 2017-2020 | PASS |
| triglycerides median (type2_diabetes/M) | 132.7 | 132 | +0.674 | ±15.8 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/F) | 50.61 | 49 | +1.61 | ±3.92 | NHANES 2017-2020 | PASS |
| hdl median (type2_diabetes/M) | 43.14 | 42 | +1.14 | ±3.36 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/F) | 85.67 | 83.15 | +2.52 | ±6.65 | NHANES 2017-2020 | PASS |
| weight_kg median (type2_diabetes/M) | 95.93 | 92.6 | +3.33 | ±7.41 | NHANES 2017-2020 | PASS |

**37/37 passed.**

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
