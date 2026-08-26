# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [semantic versioning](https://semver.org/) from 0.1.0 onward.

**The determinism contract is versioned here.** Any change to the bytes generated for a
given seed is a **breaking change**. If you pin fixtures to a seed, that guarantee is
what you are relying on, and this file is where it is recorded.

While the project is on **0.x**, a breaking change takes the *minor* position — 0.1.x to
0.2.0 — because [semver](https://semver.org/) reserves major version zero for initial
development, where the public API is explicitly not yet stable. Publishing 1.0.0 would
claim a stability commitment this project is not ready to make; it still ships
`Development Status :: 3 - Alpha`. Once it reaches 1.0.0 the rule becomes the plain one:
seeded output is byte-identical within a major version.

Practically, for anyone pinning: **pin the patch version.** `carebundle==0.1.2` is safe;
`carebundle~=0.1` is not, while the project is pre-1.0.

## [Unreleased]

### Added

- **`rows_from_records`: the benchmark accepts tabular generators.** Not every synthetic
  data tool speaks FHIR — CTGAN, TVAE and the rest of that family produce a row per
  patient carrying exactly the analytes the co-occurrence measure reads. Requiring FHIR
  would have meant writing an adapter whose only purpose was to be parsed straight back
  out.

  Records missing an analyte, carrying a NaN, or lacking a usable sex are **skipped
  rather than imputed**. A generator that omits a value has not produced a patient this
  measure can score, and filling one in would flatter it invisibly — the exact failure
  mode the benchmark exists to catch.

### Assessed and excluded

- **PySynthea (`tietai-synthea` 1.0.1) cannot be benchmarked.** It was the intended third
  generator: pip-installable, no JVM, 231 modules, FHIR R4 export. Its export emits
  Observations *without values* — systolic, diastolic, height, weight, glucose, HDL,
  triglycerides, HbA1c, ALT and AST are all present and all valueless, with
  `status: "final"` and no `dataAbsentReason`. Only 15% of its observations carry a
  `valueQuantity`, and none of those are analytes any benchmark here reads. The HL7
  validator returns **166 errors and 266 warnings** on a single bundle.

  Recorded with its reproduction in `pysynthea_assessment.json` rather than left as an
  unexplained absence from a results table. This repository's README claimed "no Java is
  no longer a reason to pick this project", which assumed the alternative produced usable
  output; that is corrected.

## [0.5.0] — 2026-08-25

**Seeded output changes.** Fixtures pinned to a seed under 0.4.0 will not reproduce; the
golden files were regenerated and the diff is values only, no structural change.

This release is about the numbers themselves. 0.4.0 established that the *joint*
structure was missing; this one found that a large share of the *marginals* and the
panel's dependence had never been measured at all — eleven analytes and three
correlations carried hand-set values while NHANES held every one of them. Four
"obvious fixes" were tested and rejected before writing along the way.

### Changed — correlations now mean what they say

- **Configured correlations are target Pearson values, solved for their latent
  parameter.** They used to be latent copula parameters, so the numbers in the source
  were not the numbers in the output: a Gaussian copula attenuates dependence through
  the marginal transform, always toward zero. Across the 32 configured pairs, realized
  values sat a mean **0.0086** below target and **0.0298** at worst, every one short.
  Now: mean **0.0019**, worst **0.0043**, and the residual is sampling noise in the
  measurement rather than model error.

- **`latent_for_pearson`, by quadrature rather than sampling.** The existing
  `calibrate_latent_correlation` solved this for a positive R² by searching upward from
  √R², which cannot serve a signed target — half the dependence here is negative. The
  replacement bisects on a signed target and evaluates the realized correlation by
  two-dimensional Gauss–Hermite quadrature. A 30,000-draw Monte Carlo estimate carries a
  standard error near 0.006, the same size as the attenuation being corrected, so the
  estimator would have been the dominant error term; quadrature agrees with a 400,000
  draw check to 0.0004 and returns the same number every run. The old function is
  **removed**, not deprecated.

- **A double correction, caught by the fidelity suite.** The HbA1c/glucose pair was
  already solved to a latent inside `_adag_calibrated_glucose`, so once the engine
  solved every pair it was corrected twice and the realized ADAG R² went to **0.875**
  against a target of 0.84. It now returns the target and lets the engine solve it once.
  This is the double-counting error recorded for pooled correlations and for blood
  pressure, in a third place — and the reason the superseded solver was deleted rather
  than left available.

- **The README's opening argument still asserted Synthea scores 0%**, in the present
  tense, fifteen lines above the correction saying it does not. Every guard passed,
  because the phrase list did not anticipate that wording. Fixed, and the list extended
  with what it missed.

- **Three correlations were excluded on a mistaken argument, and it cost clustering.**
  Weight against glucose, triglycerides and HbA1c were left out because their sign
  reverses between strata. That was the wrong conclusion from the right observation:
  reversal is a reason to key by stratum, which the table already does, so each profile
  uses its own measured value and the pooled figure is never touched. Excluding them set
  them to **zero**, and a Gaussian copula treats an unstated pair as a stated zero — the
  same trap already recorded for HbA1c's lipid pairs.

  Measured within matched strata, which is how it surfaced: the healthy profile produced
  three-of-four metabolic abnormalities in **8.6%** of patients against **13.9%** of real
  non-diabetic adults, a dependence ratio of 1.44 against 1.77, while the diabetes
  profile matched at 44.3% against 41.4%. With the pairs restored: **9.3%** and a ratio
  of **1.55**. The diabetes profile is unchanged, because those correlations are near
  zero inside its stratum — which is exactly why the pooled figure was misleading.

  A residual gap remains (1.55 against 1.77) and is expected: a **Gaussian copula has
  zero tail dependence**, so joint extremes are under-produced by construction, and a
  three-of-four threshold query measures precisely joint extremes. That is a property of
  the family, not a calibration error.

  This also corrected my earlier diagnosis, recorded in 0.4.0, that the co-occurrence
  shortfall was cohort composition. It was not — matched-stratum comparison put it in the
  healthy profile's joint structure.

- **The phrase-list guard is replaced by a structural one, and it found a fourth
  document immediately.** The withdrawn claim survived three separate guards by moving
  syntactic position — body prose, a section heading, then the write-up's own title,
  which read "Synthetic patient generators score 0% on outcome quality measures" while
  carrying the correction inside it. Each fix extended a list of banned phrasings by
  exactly the wording that had slipped past, which only catches the next instance if
  somebody guesses its shape first.

  The replacement ignores phrasing entirely: **any markdown document that mentions
  Synthea and states a zero rate must also carry the measured figure**, with the
  documents discovered by glob rather than listed and the figure read from the recorded
  comparison. A second, stricter rule covers prominence, because the title case had the
  correction present and the headline still said the opposite.

  On its first run it failed on `synthetic-fhir-generator-build-doc.md`, a fourth
  document that no hand-written list had ever covered.

- **The routine panel's dependence was three hand-set numbers for fifteen analytes.**
  Swept against NHANES the way the metabolic cluster was, mean absolute error across 210
  panel pairs came to **0.083**, with twelve pairs above 0.20. The worst was **calcium
  against albumin: 0.48 in reality and 0.004 here** — textbook physiology, since roughly
  40% of serum calcium is albumin-bound and corrected-calcium formulas exist because of
  it. Platelets against white cells was 0.35 against 0.008, chloride against CO2 −0.27
  against −0.007.

  Two of the three hand-set values were also wrong. Sodium/chloride at 0.65 was lucky
  (measured 0.646/0.644). ALT/AST at 0.72 was not: measured 0.779 in women and 0.891 in
  men, and one sex-blind figure cannot be either.

  Sixteen measured pairs now replace them, per sex and per stratum. Mean error falls to
  **0.061** and pairs above 0.20 from twelve to five.

  **Three qualifying pairs are excluded, and the reason is worth knowing.**
  Albumin/haemoglobin, albumin/haematocrit and ALT/haemoglobin each break positive
  definiteness. All three tie a chemistry analyte to a red-cell one, and the red-cell
  block is already nearly singular — haemoglobin against haematocrit is 0.96 — so it has
  no room to absorb another constraint. Pairwise correlations estimated on differing
  missingness subsets are not guaranteed to form a consistent matrix, and solving each to
  a latent parameter amplifies all of them. They are dropped rather than shrunk: quietly
  scaling a measured value until the matrix factorises would put a number in the source
  that is not the number in the data.

  They are also four of the five largest remaining gaps, so the residual is explained
  rather than merely reported.

### Documentation

- **Four shipped modules were undiscoverable.** `benchmark.synthea`,
  `benchmark.dependence`, `benchmark.cooccurrence` and `benchmark.drift` all landed in
  one session and appeared in neither `README.md` nor `CONTRIBUTING.md`. Nothing failed,
  because nothing was checking. That is the "README denies a capability the package has"
  defect pointed the other way: capability the package has and nobody can find.

  All four are now documented with the point that matters — they read *any* directory of
  FHIR bundles, so they score a competitor's output with the same code that scores this
  package's.

  A test now fails when a module that guards `__main__` and defines `main` is named in
  neither document. It accepts a console-script name as documentation too: `carebundle.cli`
  is documented everywhere as `carebundle generate …` and nowhere as `python -m
  carebundle.cli`, which is correct, and which the first version of the guard reported as
  missing. It covers eleven runnable modules.

### Investigated and not built

- **The residual clustering gap is tail dependence, and a t-copula does not close it.**
  With the correlations corrected, the healthy profile still clustered at a ratio of 1.55
  against a real 1.77. Measured conditional co-occurrence above the 80th centile — where
  independence is 0.20 — confirms the diagnosis: triglycerides/HDL is 0.48 in NHANES
  against 0.36 here, glucose/HDL 0.36 against 0.26, and real data clusters harder on four
  of six pairs.

  A Student-t copula is the standard answer, since its tail dependence grows as degrees
  of freedom fall. Simulated at matched Pearson correlations, **even ν=3 closes only
  about a third of the gap** (0.396 → 0.431 against a needed 0.48). It would also impose
  tail dependence on every pair including those that have none, need a Student-t quantile
  function written without scipy, and move seeded output. Closing this properly means
  pair-specific copulas — a vine architecture, not a parameter change.

  Recorded rather than attempted, and with the target's own uncertainty stated: the
  NHANES tail figures rest on ~1,200 people per sex, so 0.48 carries a standard error
  near 0.05 and the gap is about 1.7 of those.

### Fixed

- **Every text read and write is explicitly UTF-8.** The structural guard added above
  failed on Windows in CI: `Path.read_text()` uses the *platform* default encoding, which
  is cp1252 there, and the markdown documents it globs contain em dashes. The Python
  matrix caught it within minutes of a push I had not been able to verify locally.

  Fixed at the class level rather than at the one call site — 15 modules and tests on the
  read side, plus the CLI's own `--out` and ndjson writers, which emit FHIR JSON and are
  therefore UTF-8 by specification. They were safe only because `json.dumps` escapes
  non-ASCII by default, which is a property of the serialiser and not of the code around
  it.

### Performance

- **`get_profile` is cached, and generation is ~40% faster.** It rebuilt the profile on
  every call, and building the diabetes profile runs a 50,000-sample bisection to solve
  its HbA1c/glucose latent correlation — **9.87 ms against 0.37 ms for `healthy`** — paid
  once per generated patient for an answer identical every time.
  `generate_cohort(200)` drops from **2.49 s to 1.50 s**.

  Output is unchanged: the profile is a pure function of (key, sex), the RNG is passed
  separately, and the golden files are byte-identical across the change. The one hazard
  is the registry being mutated underneath the cache, so `calibrate_profile` and
  `forget_profile` clear it and two tests assert a re-registered profile is not served
  stale and a forgotten one stops resolving.

### Changed — **seeded output changes; this is a breaking change (0.5.0)**

- **The comprehensive metabolic panel was never calibrated, and now is.** Eleven
  analytes — sodium, potassium, chloride, CO2, calcium, albumin, BUN, ALT, AST, alkaline
  phosphatase, bilirubin — were **hand-set round numbers** with *no sex stratification at
  all*, while NHANES carried every one of them. ALT sat at mean 25.0, SD 11.0 against a
  true mean of 19.37, and one figure served both sexes where the true exceedance rates
  are 5.5% and 12.8%. Mean absolute error against true exceedance rates falls from
  **2.45 points to 0.81**.

  This is the failure the contribution rules exist to prevent — "numbers come from
  sources, not from judgement" — sitting in the routine panel of every profile since v1,
  found only because the co-occurrence work made the tails worth auditing.

- **`EmpiricalMarginal`: marginals from measured quantiles, with no family.** 0.4.0
  documented that both `Marginal` and `LogNormalMarginal` are fitted from the median and
  IQR, so both reproduce the middle and miss the same tail, and recorded that closing it
  needed a third parameter fitted to a tail percentile. The fix turned out to be dropping
  the family instead: interpolate the measured quantile function directly.

  Mean absolute error against true exceedance rates over ten analyte/sex cells —
  **fitted normal 4.43 points, 9 knots (p2.5–p97.5) 1.57, 11 knots (p1–p99) 0.73.** The
  grid is part of the method, not an implementation detail: five knots is *worse* than
  the normal on heavy skew, because linear interpolation across a wide q3-to-p97.5 gap
  spreads mass uniformly where the real density is falling, overshooting ALT to 12.1%
  against a true 5.5%. A grid stopping at p2.5 also has to be rescaled onto its own
  support, which pulls the tail back in and costs more than the extra knots buy.

  Non-diabetic glucose moves with it: 18.9% above 100 mg/dL against a true 22.7% under
  the fitted normal, 21.7% now. HbA1c stays a fitted normal, because its non-diabetic
  skew ratio is 1.09 and a family still fits it.

  The extraction emits the grid; `skew_ratio` is now a diagnostic rather than a family
  selector. Seven tests, including one asserting the knots come back exactly and one
  that the endpoints carry no point mass — the artefact a naive clamping interpolation
  would create, invisible in a mean and obvious in a histogram.

  **One small cost, recorded rather than absorbed.** Glucose's realized correlations
  drift slightly further from their configured targets — glucose/triglycerides from
  0.1648 to 0.1567 against 0.1873, glucose/HDL from −0.1686 to −0.1625 against −0.1785 —
  because a Gaussian copula's latent correlation maps to a *smaller* Pearson correlation
  as the marginal gets more skewed, and these pairs were configured as latent values
  rather than solved for a target.

  **Resolved in the same unreleased delta, above.** Every configured correlation is now a
  target Pearson value solved by the engine, which is what made the attenuation worth
  fixing generally rather than patching for glucose alone.

## [0.4.0] — 2026-08-24

**Seeded output changes.** Fixtures pinned to a seed under 0.3.0 will not reproduce; the
golden files were regenerated and the diff is values only, no structural change. Under
the 0.x policy at the top of this file a breaking change takes the minor position.

The release is dominated by corrections rather than features, and that is the point of
it: the project's headline competitive claim was false, and finding out cost four
hypotheses of which three were refuted.

### Corrected — **the headline competitive claim was false and is withdrawn**

- **Synthea does not score 0% on Controlling High Blood Pressure.** This project said it
  did, in `README.md`, `BENCHMARK.md`, `ROADMAP.md`, the write-up and two docstrings, on
  the authority of Chen et al. 2019. Measured in August 2026 against a current build,
  with this package's own measure code, Synthea scores **74.4%** (median of three runs)
  — 0.3 points from the Massachusetts rate it simulates, while this package scores 68.8%
  on a matched cohort,
  0.9 points from the US national rate it calibrates to. Both reproduce their own target
  population. **There is no outcome-measure wedge**, and the strategy built on one is
  annotated as wrong rather than deleted.

  A second published criticism also failed to reproduce: Hodges et al. (JAMIA Open 2023)
  report 100% of Synthea type-2 diabetics carrying an amputation; measured here it is
  **0.56%** (3 of 537), against a real-world incidence near 5 per 1,000 per year.

  The claim survived for as long as it did because it was *cited* rather than *run*, and
  a citation cannot go stale in CI. Two tests now fail if any document asserts the 0%
  figure in the present tense without the correction beside it, or reports a competitor's
  score without the date and harness that produced it.

### Added

- **`carebundle.benchmark.synthea`** — runs this package's quality measures against a
  Synthea FHIR export, so the comparison is reproducible instead of quoted. Synthea is
  not vendored, for the same reason the NHANES files are not; the module docstring gives
  the four commands.
- **`carebundle.benchmark.drift`, a recorded comparison, and a monthly workflow.**
  Replacing a stale citation with a measurement fixes half the problem: a measurement
  taken once and never repeated goes stale the same way, with better provenance
  attached. So the comparison is now recorded with the **exact Synthea build that
  produced it** — commit `d9d07a6`, built 2026-08-18, JAR SHA-256 `018ad7f0…` — and
  `.github/workflows/synthea-drift.yml` regenerates the population monthly and fails if
  the figures move or if Synthea has shipped a new build. Those two are reported
  separately: a new upstream build is a shelf-life notice, not a defect here.

  It runs in **51 seconds** over 1,462 lifetime bundles. The first implementation parsed
  the population once per measure; the second materialised it into a list to share, and
  did not finish inside ten minutes because ~1,500 bundles of ~1,000 resources do not
  belong in memory at once. A single streaming pass feeds both measures.

  Five tests pin it, including one that fails if `BENCHMARK.md` quotes a figure the
  record does not contain, and one asserting an empty denominator is still reported as a
  terminology fault rather than as a rate of 0% — the specific way the withdrawn claim
  could come back looking confirmed.

  **Rehearsing the workflow refuted an assumption inside it.** The job was written
  claiming a fixed seed made Synthea reproducible, so any movement would be a real
  change rather than noise. The first run produced **1,449 bundles from the same build
  and seed that produced 1,462 locally** — `-p` counts living patients and generation is
  concurrent, so the number of deceased records varies with thread interleaving. The
  mean dependence deviation moved 0.192 → 0.208, within 0.004 of tripping a tolerance
  chosen on the assumption that it could not move at all. `DEVIATION_TOLERANCE` is now
  0.05, sized against that measured spread and still far below the 0.14 gap it exists to
  detect. Noted here rather than adjusted quietly, which is what the module's own failure
  message demands.
- **`carebundle.benchmark.cooccurrence`** — how often several abnormalities land in the
  same patient, which is what a phenotyping or cohort-selection query actually asks.
  Four criteria, one rule, three populations. On the 3-of-4 phenotype: real 19.7%,
  **carebundle 14.6%, Synthea 4.1%** — absolute error against NHANES of −5.2 points
  against −15.6.

  **It reports an independence control beside every rate, because the mechanism was
  wrong twice on the way here.** TSTR was tried first and found nothing: median AUC
  retention 92.3% here against 92.5% for Synthea over ten disjoint folds, with
  overlapping IQRs. A logistic model fits one weight per feature, so it reads
  feature-to-label association and barely uses feature-to-feature dependence —
  dissociable properties, and TSTR is close to blind to this one. Then the phenotype gap
  looked like the predicted "Synthea draws components independently", and the control
  refuted that too: dividing each population's rate by what its own marginals imply
  under independence gives **NHANES 1.59×, Synthea 2.10×, carebundle 1.45×**. Synthea
  clusters *more* than reality. Its low rate comes from mild marginals — glucose ≥ 100
  in 8.7% of its patients against 47.4% of real ones — and its dependence is shaped by
  module co-membership, tight inside a module and absent across them, exactly as the
  correlation table shows. This package errs the other way, slightly under-clustered.

  Ten tests, including one asserting a genuinely independent synthetic population scores
  a ratio of 1.0, and one checking the control against a hand-computed four-coin case.
- **`carebundle.benchmark.dependence`** — measures cross-domain analyte dependence in
  any FHIR source against the committed NHANES extraction, and it exists because the
  claim that replaced the withdrawn one should not also go unchecked. Seven pairs across
  adiposity, glycaemia and lipids, within sex, ages 45–65, one contemporaneous panel per
  patient.

  Measured: median absolute deviation from NHANES of **0.047** here (0.040–0.055 across
  four seeds) against **0.208** for Synthea (0.192–0.209 across three runs), with sign
  agreement 14/14 against 10/14. Both sides are reported as medians with their spread
  because Synthea does not reproduce a population from a fixed seed and this package
  does; quoting one seeded draw here against a noisy average there would have flattered
  this package, and the first version of the table did exactly that — it used 0.192,
  the lowest of the three Synthea runs. Synthea's dependence follows module
  co-membership — glucose against triglycerides is over-coupled at roughly double the
  real value, while weight against HDL is +0.01 against a real −0.26, and the inverse
  triglyceride/HDL relationship comes out *positive* in men.

  Deviation rather than CI coverage is reported, because Synthea's smaller sample gives
  wider intervals that cover the target more often by luck; the coverage metric would
  have read 4/14 against 7/14 and rewarded having less data.

  **This package was in the same position four days ago** — its own weight/HDL
  correlation was +0.01 until 0.4.0-dev measured it, with every marginal passing
  throughout. Four tests now guard the result, including one that fails on any
  correlation with the wrong sign.

### Fixed

- **`cqm` scored any SNOMED-coded source at zero.** It recognised hypertension only in
  ICD-10-CM, which this package emits and Synthea does not. An empty denominator is not
  a rate of zero, and this one would have "reproduced" the 2019 finding for a pure
  terminology reason. SNOMED hypertension codes are now recognised — read off a
  generated population rather than recalled — and an empty denominator is reported as
  such, never as 0%.
- **`cqm` mis-scored longitudinal bundles.** "Most recent blood pressure" took the last
  array element rather than the latest by date, and age came from `encounters[0]`, which
  on a lifetime is usually infancy. Both are corrections rather than Synthea adapters:
  on a one-visit bundle they are invisible, and this package's own rates are unchanged.
- **A test fixture claimed to match real output while omitting `effectiveDateTime`.**
  Every benchmark test failed the moment the measure started reading dates, and the
  emitter was fine throughout.

### Changed — **seeded output changes; this is a breaking change (0.4.0)**

- **The metabolic cluster is now modelled.** Adiposity, glycaemia and lipids were drawn
  independently of one another: weight against HDL is −0.26 in NHANES and was **+0.01**
  in generated output. Every marginal matched its target the whole time, so no marginal
  check could see it — a heavy patient was no likelier than anyone else to have a low
  HDL, and the metabolic phenotype that makes a diabetic patient look diabetic was
  absent from the joint distribution.

  Five pairs are now fitted per sex, from the stratum each profile draws from:
  weight/HDL, glucose/triglycerides, glucose/HDL, HbA1c/HDL and HbA1c/triglycerides.
  All ten reproduce within 0.02 of the survey. BMI/HDL moves from +0.015 to −0.27
  against a measured −0.30 without being configured at all, since BMI is computed from
  height and weight rather than sampled.

  **Pooled correlations were deliberately not used.** Weight against glucose reads
  +0.10 across everyone and −0.08 inside the diabetic stratum: the pooled figure is
  mostly "heavier people are more often diabetic", which the profile split already
  encodes, so fitting it would count the same fact twice. Pairs whose sign flips
  between strata, and every pair involving blood pressure (between −0.02 and +0.11 with
  no consistent sign across sexes), are excluded and the reasons are in the source.

  **A prediction made here was wrong and is recorded rather than quietly fixed.** The
  first attempt specified only glucose's lipid links, reasoning that HbA1c correlates
  with glucose at 0.82 so the copula would carry the dependence across at about −0.15.
  Measured: −0.009. A Gaussian copula fills every unspecified entry with zero, so an
  unstated correlation is a *stated* zero — the model asserts independence it was never
  asked to assert. HbA1c now carries its own pairs.

### Added

- **Twelve fidelity checks** covering the pairs above, including BMI/HDL, which is the
  only check in the report that could fail while every configured value stayed correct.
  All are graded `calibration`, not `out_of_sample`: they are fitted to the same survey
  that supplies the marginals. **The out-of-sample count stays at 1** — the denominator
  moved from 46 to 58 and the evidence did not.
- **`anaemia` now has a golden file.** It shipped in 0.2.0 without one: the golden test
  iterated a hardcoded tuple of four profile names instead of the profile registry, so
  the determinism contract covered every profile but only pinned the four somebody had
  typed. The list is now derived, and a new profile fails until its golden exists.

### Fixed

- **Five of the ten rows in the README's evidence table had drifted** — the ADAG slope,
  the glucose value at HbA1c 8.0%, both medians and the obesity rate, the last of which
  contradicted the README's own prose about the same figure two sections away. It is
  the most persuasive table in the project and was the least checked. Rows now use the
  report's exact labels and a test asserts every one of them.
- **The fidelity report told readers its marginals were not fitted to a named cohort**
  and that "calibrating marginals against NHANES is Phase 4". Phase 4 shipped in 0.2.0.
  Stale prose inside a generated artefact is worse than stale prose in a document,
  because it arrives stamped with the authority of the thing it is wrong about.

## [0.3.0] — 2026-08-22

Additive throughout: no seeded output changed, so fixtures pinned to a seed under 0.2.0
still reproduce byte for byte.

### Added

- **`carebundle.bulk` / `to_ndjson`, and `carebundle generate --format ndjson`** —
  FHIR Bulk Data output, one ndjson file per resource type, for testing an `$export`
  importer. Ids are minted from each entry's `fullUrl` and every `urn:uuid:` reference
  is rewritten to `ResourceType/id`, because a transaction Bundle and a bulk export
  differ in exactly the two ways that break importers. `identifier.system` keeps its
  urn form, which is deliberate and separately tested.
- **`carebundle.calibration.fetch`** — downloads the eleven NHANES files the offline
  tooling needs, so the claims in this repository can actually be checked. Knowing which
  files, under which of several CDC URL layouts, was the undocumented step between "not
  vendored" and "verify it yourself". Regenerating the calibration targets from a fresh
  download reproduces the committed file byte for byte.
- **`carebundle.fidelity.transfer`** — clinical-utility evidence by
  Train-on-Synthetic-Test-on-Real. A logistic model fitted entirely on generated
  patients scores AUC 0.621 on 1,330 real NHANES individuals against 0.677 for the same
  model trained on real data: **92% retention**. Offline tooling like the calibration,
  since it needs the NHANES individual records.

  Graded `calibration` rather than `out_of_sample` — the test individuals were never
  seen and no fitting targeted an AUC, but the marginals came from the same survey, so
  it is not independent evidence. The pinned out-of-sample count stays at 1.

### Fixed

- **The README denied a capability the package has.** It listed "no longitudinal
  history" as a limitation three hundred lines below the section documenting
  `generate_history`. Understating is the same class of defect as overstating, and a
  test now fails if a stated limitation contradicts an exported name.
- **A fifth documentation figure had drifted.** The diabetic obesity rate was typed as
  64.8% against a measured 63.8%; it is now read out of the fidelity report rather than
  retyped. Every figure appearing in both prose and an artefact is asserted against the
  artefact — five for five is no longer coincidence.
- **Scope claims in the design record that time had falsified** — longitudinal history,
  the profile count, and a format exclusion that had been read as ruling out ndjson when
  it does not. Annotated rather than rewritten, so both the original decision and the
  reason it moved stay legible.

## [0.2.0] — 2026-08-20

### Changed — **breaking, seeded output**

- **The red cell correlations are measured rather than estimated.** Haemoglobin,
  haematocrit and red cell count were hand-set at 0.93 / 0.86 / 0.87. Measured against
  NHANES 45-65 they are 0.964 / 0.538 / 0.648 in women and 0.960 / 0.649 / 0.752 in men.
  Haemoglobin against red cell count was badly wrong — 0.86 against a measured 0.54 —
  and all three differ by sex, so a single constant could not have been right for both.

  This is the same failure as the three correlations corrected before publication: a
  plausible number nobody had compared to data. It was found while calibrating the
  anaemia profile, which needed the same trio measured within its own stratum.

  **This changes seeded output for every profile.** Fixtures pinned to a seed on 0.1.x
  will differ here; pin the patch version if that matters to you.

### Added

- **`anaemia` profile** — anaemia by WHO haemoglobin criteria (<13 g/dL in men, <12 in
  women), calibrated to a new NHANES `anaemic` stratum. The diagnosis code is derived
  from the values rather than fixed: `D63.1` (anaemia in chronic kidney disease) when
  eGFR is below 60, `D50.9` (iron deficiency) when the red cell count is low too,
  `D64.9` otherwise — so the coded diagnosis cannot contradict the labs beside it.

  Its red cell correlations are measured *within* the anaemic stratum, which differs
  strikingly from the general population: haemoglobin and red cell count correlate at
  0.54–0.65 across everyone but only 0.04 (F) / 0.35 (M) among anaemics, because iron
  deficiency lowers the haemoglobin per cell while leaving the count comparatively
  intact. Reusing the general-population figure would erase the thing that makes an
  anaemic panel look anaemic.

  Ships with eight fidelity assertions and zero US Core errors. Adds four terminology
  codes, all verified against their source vocabularies.

Generated output for existing profiles is unchanged; this is additive.

## [0.1.2] — 2026-08-16

### Fixed

- **`carebundle.__version__` reported the wrong version.** 0.1.1 shipped with
  distribution metadata saying `0.1.1` and the runtime attribute still saying `0.1.0`,
  because the version was written in two places and only one was bumped. The existing
  test asserted the string contained two dots, so it could never have caught it.

  The version is now single-sourced: `carebundle/__init__.py` defines it and
  `pyproject.toml` declares it dynamic and reads it from there, which makes the two
  impossible to disagree. Tests assert both that configuration and, when installed,
  that the distribution metadata matches the module attribute.

Generated output is unchanged.

## [0.1.1] — 2026-08-16

### Fixed

- **Every documentation link on the PyPI page was dead.** The README is published as
  the long description, where relative links resolve against `pypi.org` rather than the
  repository — so `BENCHMARK.md`, `CONFORMANCE.md`, `FIDELITY.md`, `ROADMAP.md` and
  `LICENSE` all 404'd on the page where "check the evidence yourself" is the whole
  pitch. Now absolute GitHub URLs, which work in both places. `twine check` does not
  catch this: the markup is valid, only the destinations are wrong. A test now asserts
  the README contains no relative links.

Generated output is unchanged, so seeded fixtures pinned to 0.1.0 are unaffected.

## [0.1.0] — 2026-08-16

First release. Everything here is new, so this entry describes the surface rather than a
diff. Output changed several times during development; none of it is recorded as a
breaking change, because nothing was published and so nothing depended on it. The
determinism contract described above starts now.

### Added

- **Generation API** — `generate_bundle`, `generate_patient`, `generate_draw`,
  `generate_cohort`, `to_json`, and the `PROFILES` registry. Returns FHIR R4 4.0.1
  `transaction` Bundles as in-process objects; JSON export is optional.
- **Four clinical profiles** — `healthy`, `hypertension`, `type2_diabetes`,
  `ckd_stage3`, plus `mixed` cohorts drawn by prevalence.
- **Nine resource types** — Patient, Practitioner, Encounter, Condition, Observation,
  MedicationRequest, DiagnosticReport, AllergyIntolerance, and the Bundle itself.
- **US Core 6.1.0 conformance**, checked by the official HL7 Java validator on every
  release. Zero errors across all four profiles; every remaining warning is documented
  with a reason in `CONFORMANCE.md`, and a new warning fails the build.
- **Correlation engine** — Gaussian copula for jointly sampled analytes, with derived
  values computed rather than sampled (CKD-EPI 2021 eGFR, Friedewald LDL, BMI) so a
  bundle cannot contradict itself. Blood pressure is computed from the regimen actually
  prescribed, using the effect sizes in Law MR et al., *BMJ* 2003;326:1427 and a further
  1.5 mmHg per dose doubling ([*Lancet* 2025](https://pubmed.ncbi.nlm.nih.gov/40885583/)),
  so a bundle cannot prescribe three antihypertensives beside an untreated-looking
  168/102.
- **NHANES-calibrated marginals and dependence structure.** Marginals, correlations and
  comorbidity prevalence are all derived from the NHANES 2017–March 2020 files rather
  than estimated, with log-normal marginals where a truncated normal cannot represent a
  distribution whose mode sits at its lower bound. The type 2 diabetes profile is
  calibrated to *diagnosed* diabetics (DIQ010), not to everyone above an HbA1c
  threshold — a quarter of diagnosed diabetics sit below 6.5 because their treatment
  works, and a lab-defined stratum excludes all of them.
- **`carebundle.benchmark`** — CMS/HEDIS clinical quality measures computed from emitted
  FHIR. `Controlling High Blood Pressure` scores **71.5%** against Synthea's published
  **0%**, between the US (69.7%) and Massachusetts (74.5%) comparators, from
  independently cited inputs. See [BENCHMARK.md](BENCHMARK.md), which also publishes the
  three measures this does *not* model and why.
- **`carebundle.history` / `generate_history`** — one patient across several visits,
  with blood pressure falling as therapy is escalated toward goal.
- **`calibrate_profile` / `Quartiles`** — calibrate a profile to your own population from
  medians and quartiles, inheriting the correlation structure, computed identities,
  prescribing rules and conformance.
- **`carebundle.imperfection`** — deliberately imperfect FHIR for testing the code paths
  clean data never reaches. Five defect kinds, seeded, non-mutating, every injected flaw
  returned. Off by default; CI asserts clean output validates and dirtied output does
  not.
- **Verified fidelity, graded by evidential strength.** 46 checks across
  `out_of_sample`, `calibration`, `round_trip` and `identity`; [FIDELITY.md](FIDELITY.md)
  is grouped by grade rather than reported as a flat pass count, and a test pins the
  out-of-sample count so it cannot grow by relabelling.
- **Determinism contract** — `seed=42` produces byte-identical output, enforced by
  golden-file tests. Verified byte-identical across CPython 3.10 through 3.14, across
  numpy versions, and on Linux, macOS and Windows.
- **85 terminology codes** (LOINC, RxNorm, ICD-10-CM) with per-code provenance and
  licence metadata, re-verified nightly against the source vocabularies.
- **Safety by construction** — every resource carries the `HTEST` security label, a
  synthetic narrative, identifiers from never-issued ranges, and fictional names.
- **CLI** — `carebundle generate` and `carebundle profiles`. Behaves as a Unix filter:
  exits 141 on a closed pipe with no traceback, 130 on Ctrl-C.
- **Inline type annotations** (PEP 561) via `py.typed`.

### Notes

- Runtime dependencies are `pydantic>=2` and `numpy>=1.24`. The HL7 validator needs a
  JVM but is a development and CI dependency only — never required to install or run.
- `Encounter.type` asserts `text` only and takes one validator warning. Its value set
  draws on CPT-4 (AMA-licensed) and SNOMED CT, so warning-free US Core Encounter
  conformance is not reachable without licensed terminology. See `CONFORMANCE.md`.

[Unreleased]: https://github.com/27jackson08/fhirfaker/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.5.0
[0.4.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.4.0
[0.3.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.3.0
[0.2.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.2.0
[0.1.2]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.2
[0.1.1]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.1
[0.1.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.0
