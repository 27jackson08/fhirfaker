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

[Unreleased]: https://github.com/27jackson08/fhirfaker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.2.0
[0.1.2]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.2
[0.1.1]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.1
[0.1.0]: https://github.com/27jackson08/fhirfaker/releases/tag/v0.1.0
