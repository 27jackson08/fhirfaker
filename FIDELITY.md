# Fidelity Report

Generated distributions checked against published clinical relationships.
Regenerated per release from n=10,000 draws, seed 20260101.

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| ADAG slope | 28.74 | 28.7 | +0.044 | ±1 | Nathan 2008 | PASS |
| ADAG R^2 | 0.8454 | 0.84 | +0.00536 | ±0.02 | Nathan 2008 | PASS |
| glucose at HbA1c 6.5% | 139.7 | 139.8 | -0.125 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 8.0% | 182.8 | 182.9 | -0.0587 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 9.5% | 226 | 225.9 | +0.00726 | ±5 | Nathan 2008 | PASS |
| CKD stage-3 eGFR within band | 1 | 1 | +0 | ±0 | KDIGO 2012 | PASS |
| eGFR consistent with creatinine | 0 | 0 | +0 | ±1e-09 | CKD-EPI 2021 | PASS |
| ICD-10 stage code matches eGFR | 1 | 1 | +0 | ±0 | ICD-10-CM | PASS |
| T2DM hypertension comorbidity | 0.708 | 0.7 | +0.008 | ±0.0259 | profile config | PASS |
| systolic/diastolic correlation | 0.6019 | 0.6 | +0.00193 | ±0.05 | profile config | PASS |
| LDL consistent with panel (Friedewald) | 0 | 0 | +0 | ±1e-09 | Friedewald 1972 | PASS |
| triglyceride/HDL correlation | -0.3912 | -0.4 | +0.00883 | ±0.05 | profile config | PASS |
| BMI consistent with height and weight | 0 | 0 | +0 | ±1e-09 | WHO | PASS |
| diabetic obesity rate | 0.5785 | 0.6 | -0.0215 | ±0.05 | profile config | PASS |
| typical-adult median BMI | 26.52 | 26.5 | +0.0201 | ±1.5 | profile config | PASS |

**15/15 passed.**

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
