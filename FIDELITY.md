# Fidelity Report

Generated distributions checked against published clinical relationships.
Regenerated per release from n=10,000 draws, seed 20260101.

| Check | Observed | Expected | Delta | Tolerance | Source | |
|---|---:|---:|---:|---:|---|:--:|
| ADAG slope | 28.51 | 28.7 | -0.191 | ±1 | Nathan 2008 | PASS |
| ADAG R^2 | 0.8411 | 0.84 | +0.00108 | ±0.02 | Nathan 2008 | PASS |
| glucose at HbA1c 6.5% | 140.2 | 139.8 | +0.369 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 8.0% | 183 | 182.9 | +0.0822 | ±5 | Nathan 2008 | PASS |
| glucose at HbA1c 9.5% | 225.7 | 225.9 | -0.205 | ±5 | Nathan 2008 | PASS |
| CKD stage-3 eGFR within band | 1 | 1 | +0 | ±0 | KDIGO 2012 | PASS |
| eGFR consistent with creatinine | 0 | 0 | +0 | ±1e-09 | CKD-EPI 2021 | PASS |
| ICD-10 stage code matches eGFR | 1 | 1 | +0 | ±0 | ICD-10-CM | PASS |
| T2DM hypertension comorbidity | 0.7034 | 0.7 | +0.0034 | ±0.0259 | profile config | PASS |
| systolic/diastolic correlation | 0.5966 | 0.6 | -0.0034 | ±0.05 | profile config | PASS |

**10/10 passed.**

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
