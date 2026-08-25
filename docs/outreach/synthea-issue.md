# Cross-domain analyte dependence is absent between body systems and over-coupled within modules

**Measured against:** Synthea `d9d07a6` (built 2026-08-18), 1,200 patients, `-s 42 -a 18-85`, default Massachusetts settings
**Reference:** NHANES 2017–March 2020, ages 45–65, within sex
**Reproduction:** `pip install carebundle && python -m carebundle.benchmark.dependence --fhir-dir ./pop/fhir`

First, thank you — Synthea is the reason a benchmark like this is possible at all, and
two of the things I expected to find were wrong in your favour. I'll get those out of the
way, because they matter for how you read the rest.

## Two published criticisms of Synthea that no longer reproduce

I built a comparison on the assumption they held. Both are stale, and I have retracted
them publicly.

| Claim | Source | Measured on `d9d07a6` |
|---|---|---|
| 0% on Controlling High Blood Pressure | Chen et al., *BMC MIDM* 2019 | **74.4%** — 0.1 pts from the Massachusetts rate you simulate |
| 100% of type-2 diabetics have an amputation | Kartoun et al., *JAMIA Open* 2023 | **0.56%** (3 of 537), against a real ~5 per 1,000/yr |

Whatever produced those has been fixed. My project's own README asserted the 0% figure
for months and I withdrew it when I measured it.

## The finding

Seven analyte pairs spanning adiposity, glycaemia and lipids, within sex, ages 45–65, one
contemporaneous panel per patient (the date carrying the most analytes, so values are
compared as measured rather than across a simulated lifetime).

| pair | NHANES | Synthea | reading |
|---|---:|---:|---|
| triglycerides ~ HDL (M) | −0.297 | **+0.134** | wrong sign, 95% CI [0.006, 0.258] excludes zero |
| BMI ~ HDL (F / M) | −0.303 / −0.264 | +0.012 / +0.028 | absent, wrong sign in both sexes |
| glucose ~ triglycerides (F) | 0.234 | **0.473** | roughly double |

Mean absolute deviation from NHANES across 14 cells: **0.208** (median of three
generation runs, range 0.192–0.209). Sign agreement 10/14.

Read together these look like one mechanism rather than three defects. Dependence appears
to follow **module co-membership**: a patient inside the diabetes module gets raised
glucose *and* raised triglycerides together, so that pair is over-coupled at twice the
real value — while weight and HDL, which no single module links, sit at +0.01 against a
real −0.30. The inverse triglyceride/HDL relationship in men, one of the most reproducible
findings in lipidology, comes out positive.

A second measurement supports that reading. Asking for **three of four** metabolic
abnormalities in the same patient (BMI ≥ 30, triglycerides ≥ 150, HDL < 40/50,
glucose ≥ 100):

| | ≥3 of 4 |
|---|---:|
| NHANES | 19.7% |
| Synthea | 4.1% |

But the cause is *not* missing dependence — dividing each population's rate by what its
own marginals imply under independence gives NHANES 1.59×, Synthea **2.10×**. Synthea
clusters *more* than reality. The low rate comes from milder marginals: glucose ≥ 100 in
8.7% of Synthea patients against 47.4% of real ones. I mention this because the obvious
reading of the 4.1% is wrong, and I nearly published it that way.

## Caveats I'd want a reader to have

- Synthea simulates Massachusetts; NHANES is national. Correlations are far less
  population-sensitive than prevalences, but this is not like-for-like.
- Synthea does not reproduce a population from a fixed seed — three runs of `d9d07a6`
  gave 1,462, 1,449 and 1,447 bundles, since `-p` counts living patients and generation
  is concurrent. Figures above are medians across those runs.
- I maintain a small generator in this space, so discount accordingly. Its own numbers
  are in the same table and it is worse than Synthea on breadth by two orders of
  magnitude, which its README says.

## Why this might be worth fixing

Anything reading the *joint* distribution — phenotype queries, cohort selection with
multiple criteria, risk scores combining several labs — inherits this. Single-variable
validation cannot see it: every marginal can be correct while the joint distribution is
wrong, which is exactly the state my own generator was in until I measured it.

Happy to run any variant configuration you'd like tested, or to open a PR adding the
measurement as a check you can run yourselves.
