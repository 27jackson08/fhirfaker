# carebundle — clinically coherent synthetic FHIR® test data for Python

[![PyPI](https://img.shields.io/pypi/v/carebundle)](https://pypi.org/project/carebundle/)
[![CI](https://github.com/27jackson08/fhirfaker/actions/workflows/ci.yml/badge.svg)](https://github.com/27jackson08/fhirfaker/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://github.com/27jackson08/fhirfaker/actions/workflows/ci.yml)
[![US Core](https://img.shields.io/badge/US%20Core-6.1.0%20validated-brightgreen)](https://github.com/27jackson08/fhirfaker/blob/main/CONFORMANCE.md)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue)](https://github.com/27jackson08/fhirfaker/blob/main/LICENSE)

`pip install`, import, and get a **US Core-conformant FHIR R4 Bundle** back as a Python
object. No JVM, no config file, no output directory to manage.

The badge is the point: the conformance and fidelity claims below are machine-checked
in CI, not asserted in prose. Every Python version listed is actually in the matrix, on
Linux, macOS and Windows — including the byte-identical golden files, so the
determinism contract holds across platforms rather than only on the one that wrote it.

```python
from carebundle import generate_bundle

bundle = generate_bundle(profile="type2_diabetes", seed=42, sex="F")
bundle.entry            # work with it in-process
```

```bash
carebundle generate --profile type2_diabetes --count 20 --seed 42 --out ./fixtures/
```

---

## Why not Synthea?

[Synthea](https://github.com/synthetichealth/synthea) is excellent, mature and
peer-reviewed, and does far more than this: full birth-to-death population simulation,
100+ disease modules, C-CDA and bulk ndjson output, and its own US Core-conformant FHIR
export. **For most people it is still the right answer**, and this is not a replacement
for it.

There is one specific thing it measurably does not do. Synthea's
[published validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/) tested it
against four CMS quality measures: it tracks reality on the *process* measure and scores
**0%** on every *outcome* measure, because a simulator of care pathways has no
representation of what the blood pressure did after treatment started. Modelling
clinical state directly is what makes an outcome measure reachable at all.

That is the gap this fills. It is narrow, and the table below is honest about how
narrow — one of four benchmark measures, with the other three marked *not modelled*
rather than quietly dropped.

| | Synthea | this |
|---|---|---|
| Runtime | Java JDK 17+ | pure Python, `pydantic` + `numpy` |
| Shape | batch — generates a population into a folder | library — returns a `Bundle` object in-process |
| Scope | full patient lifecycle simulation | one visit, clinically coherent |
| Reproducible fixtures | not a contract | **byte-identical for a given seed** |
| CMS *Controlling High Blood Pressure* | **0%** (published) | **71.5%** (real-world 69.7–74.5%) |

**If you want a realistic population to analyse, use Synthea.** Breadth is not close:
231 disease modules against four clinical profiles, and a lifetime per patient against a
single visit. If you want five diabetic patients with coherent lab panels inside a
pytest fixture, this is smaller and the numbers are checked.

The full comparison, including the three measures this does **not** model, is in
[BENCHMARK.md](https://github.com/27jackson08/fhirfaker/blob/main/BENCHMARK.md).

### Why not PySynthea?

[`tietai-synthea`](https://github.com/TIET-AI/tietai-synthea) (published as PySynthea,
[arXiv:2606.28346](https://arxiv.org/abs/2606.28346)) is a Python-native reimplementation
of Synthea: `pip install`, no JVM, 231 disease modules, full lifecycle simulation, FHIR
R4 / CSV / JSON export. It removes the JVM barrier, so "no Java" on its own is no longer
a reason to pick this project. If you want Synthea's depth without the JDK, use it.

Two differences remain, and they are the reasons this exists:

| | tietai-synthea | this |
|---|---|---|
| FHIR version | builds on `fhir.resources>=7.0.0`, which ships R4B 4.3.0, R5 and STU3 — **not R4 4.0.1** | **R4 4.0.1**, the version US Core targets and US production APIs speak |
| US Core | not claimed | **6.1.0, validator-checked every release** |
| Install weight | 12 runtime dependencies (pandas, scipy, matplotlib, jinja2, …) | 2 — `pydantic`, `numpy` |
| Python support | `>=3.9,<3.14` | `>=3.10`, tested through 3.14 |

That R4/R4B distinction is not pedantry: US Core 6.1.0 is written against R4 4.0.1, and
Epic, Cerner and essentially every US production FHIR API are 4.0.1. It is also the
reason this project generates its own models from the R4 StructureDefinitions instead of
taking `fhir.resources` as a dependency.

**What this is explicitly not:** a population health simulator, a replacement for
Synthea's or PySynthea's disease-module depth, or a terminology server.

Where this is heading — and the peer-reviewed evidence behind the direction — is in
[ROADMAP.md](https://github.com/27jackson08/fhirfaker/blob/main/ROADMAP.md).

---

## Three things Synthea cannot do

Not "does better" — cannot, for structural reasons rather than effort. Each is a
consequence of modelling clinical state instead of care pathways, or of being a library
rather than a population simulator.

### Treatment response over time

The single-visit bundle records the pressure a titrated patient *ends up at*. This shows
how they got there — a patient presenting uncontrolled, escalated at each review until
they reach goal, then held:

```python
from carebundle import generate_history
from carebundle.history import visits_of

for visit in visits_of(profile="hypertension", seed=42, visits=5):
    print(visit.on, f"{visit.systolic:.0f}/{visit.diastolic:.0f}", visit.agents)

# 2025-01-06  154/101  0     presents untreated
# 2025-04-06  142/93   1     one agent
# 2025-07-05  137/90   2     at goal
# 2025-10-03  137/90   2     held
# 2026-01-01  137/90   2     held

bundle = generate_history(profile="hypertension", seed=42, visits=5)
```

This is the thing a care-pathway simulator structurally cannot produce: a state machine
decides *whether* a drug was prescribed, not what the pressure did afterwards. The
effect sizes are the same two already cited for the single-visit model (Law 2003 for
each agent, Lancet 2025 for each dose doubling), so it makes no new evidence claims.

It is bounded on purpose — no birth, no death, no disease-progression modules. Breadth
is Synthea's, and competing there loses. `generate_bundle` is untouched, so adding this
changed no existing seeded output.

### Calibrate it to your own population

The shipped marginals are NHANES: US adults aged 45–65. Your patients are not that
population. Supply the summary statistics you *can* share — medians and quartiles
disclose no individual — and get a profile that reproduces them:

```python
from carebundle import calibrate_profile, Quartiles, generate_bundle

calibrate_profile(
    "our_clinic",
    base="type2_diabetes",
    marginals={"hba1c": Quartiles(median=8.4, q1=7.5, q3=9.8, low=6.0, high=13.5)},
)
bundle = generate_bundle(profile="our_clinic", seed=42)
```

Everything you do not override is inherited — the correlation structure, the computed
identities (eGFR, Friedewald LDL, BMI), the conditions and prescribing, and US Core
conformance. Only the numbers change.

It will **warn** if you override an analyte another marginal was derived from. Replacing
HbA1c alone breaks the ADAG glucose relationship, because the glucose marginal is
calibrated against HbA1c's — a warning rather than an error, since it is your population
and your relationship may genuinely differ, but not something to discover silently.
There is a test in the suite that fails if that stops being true.

This is the one capability here that a population simulator structurally cannot offer:
Synthea's distributions come from its modules, and there is nowhere to put yours.

### Deliberately imperfect data

Nothing else in this space generates data that is *wrong on purpose*, and for testing
an application that is the gap that matters: code which has only ever seen well-formed
bundles has untested error paths, and the bug surfaces the first time a real feed
arrives. Real extracts have missing fields, replayed duplicates, site-local code
systems and `"QNS"` where a number should be.

```python
from carebundle import generate_bundle, to_json, Imperfection, inject_defects
import json

clean = json.loads(to_json(generate_bundle(profile="type2_diabetes", seed=42)))
dirty, defects = inject_defects(
    clean, Imperfection(missing_field=0.3, unparseable_value=0.2), seed=5
)

for defect in defects:            # every flaw is enumerable
    print(defect.kind, defect.entry_index, defect.detail)
```

Two rules make it usable rather than merely messy:

- **Off by default.** `Imperfection()` is a no-op. US Core conformance stays provable
  and dirt is something you ask for — CI asserts both halves: clean output validates
  with zero errors, and the dirty output above genuinely fails the HL7 validator.
- **Every defect is machine-readable.** You can assert *"my parser rejected exactly
  these three records"* instead of eyeballing output. Injection is seeded and never
  mutates its input.


## What makes the data defensible

Three layers, weakest to strongest.

### 1. Conformance — proven, not claimed

Output is validated by the **official HL7 FHIR validator** against US Core 6.1.0 on
every release. The full matrix is published in [CONFORMANCE.md](https://github.com/27jackson08/fhirfaker/blob/main/CONFORMANCE.md).

| Profile | Entries | Errors | Warnings |
|---|---:|---:|---:|
| healthy | 42 | **0** | 2 |
| hypertension | 45 | **0** | 4 |
| type2_diabetes | 50 | **0** | 10 |
| ckd_stage3 | 52 | **0** | 12 |

Every remaining warning is examined and documented with a reason; a *new* warning
fails the build. Counts scale with medication count — each RxNorm-coded prescription
raises the same two validator-environment warnings.

### 2. Verified fidelity — the actual differentiator

Most quick synthetic generators randomise each field independently, which is how you
end up with a diabetes diagnosis next to an HbA1c of 5.2%. Here, analytes are drawn
**jointly** from a Gaussian copula, and derived values are **computed** from published
formulas rather than sampled.

The claim is checked statistically on every run and published as a
[fidelity report](https://github.com/27jackson08/fhirfaker/blob/main/FIDELITY.md):

| Check | Observed | Expected | Source |
|---|---:|---:|---|
| ADAG slope | 28.46 | 28.70 | Nathan 2008 |
| **ADAG R²** | **0.845** | **0.840** | Nathan 2008 |
| glucose at HbA1c 8.0% | 183.0 | 182.9 mg/dL | Nathan 2008 |
| eGFR consistent with creatinine | exact | exact | CKD-EPI 2021 |
| LDL consistent with panel | exact | exact | Friedewald 1972 |
| BMI consistent with height/weight | exact | exact | WHO |
| CKD stage-3 eGFR within band | 100% | 100% | KDIGO 2012 |
| HbA1c median (diabetic) | 7.38 | 7.40 | NHANES 2017-2020 |
| triglycerides median (healthy) | 89.3 | 88.0 mg/dL | NHANES 2017-2020 |
| diabetic obesity rate | 0.657 | 0.612 | NHANES 2017-2020 |

All 38 checks pass — but they are **not equally strong evidence**, and the report grades
them rather than reporting a flat total:

| Grade | Checks | What a pass proves |
|---|---:|---|
| **out-of-sample** | **1** | A published relationship the model was *not* fitted to. The only category that evidences fidelity in the sense the word implies. |
| calibration | 32 | A marginal, correlation or prevalence measured from NHANES survived truncation and the copula. Meaningful, but in-sample by construction. |
| round-trip | 1 | The sampler reproduces a value it was configured with. Proves the engine works, not that the value is right. |
| identity | 4 | Computed from its own inputs (eGFR, Friedewald LDL, BMI). Cannot fail unless the code is broken. |

Stating that only one check is genuinely out-of-sample is not a weakness being
confessed; it is the distinction most synthetic-data validation omits, and omitting it
is the specific criticism in
[arXiv:2606.08903](https://arxiv.org/abs/2606.08903) — that evaluation is dominated by
statistical similarity which does not establish clinical validity. The out-of-sample
check is the CMS blood-pressure control measure in [BENCHMARK.md](https://github.com/27jackson08/fhirfaker/blob/main/BENCHMARK.md), and a
test pins the count so it cannot grow by relabelling.

Marginals are calibrated against the **NHANES 2017-March 2020** public files,
restricted to ages 45-65 and stratified by sex and glycaemic status, and the fidelity
report checks the generated medians against those targets. Right-skewed analytes
(triglycerides, diabetic HbA1c) use log-normal marginals — a truncated normal cannot
represent a distribution whose mode sits at its lower bound, and the fit refuses
rather than returning something plausible-looking.

**The R² is the load-bearing number.** The ADAG relationship is
`eAG = 28.7 × HbA1c − 46.7` with R² = 0.84. A generator that derives glucose
deterministically from HbA1c reproduces the line perfectly, scores R² = 1.0, and is
visibly artificial to anyone who plots it. Reproducing the *residual scatter* is the
actual claim, so the check is two-sided — too tight a correlation fails just as a
too-loose one does.

Coherence shows up in the codes too: the CKD profile emits `N18.31` or `N18.32`
depending on which side of 45 mL/min/1.73m² the drawn eGFR falls, so the coded
diagnosis cannot contradict the lab result in the same bundle.

### 3. Determinism — a contract, not a nice-to-have

`seed=42` produces **byte-identical** output. Not "statistically similar" — the same
bytes, enforced by committed [golden files](https://github.com/27jackson08/fhirfaker/tree/main/tests/golden/).

- No `uuid4()`: ids are UUIDv5 derived from `(seed, role, index)`.
- No `datetime.now()`: the reference date is injected.
- No `hash()`: Python salts it per process, which would break reproducibility across
  runs while looking deterministic within one.

**Stability policy:** generated output changes only on a **major** version bump. You
can safely pin test fixtures to a seed.

---

## Install

```bash
pip install carebundle
```

Runtime dependencies: `pydantic>=2`, `numpy>=1.24`. That is the whole list.
Python 3.10+. Type annotations ship inline (PEP 561), so `mypy` and `pyright` read them
without a stubs package.

> The HL7 validator needs a JVM, but it is a **development and CI dependency only**.
> It is never required to install or run this package.

---

## Usage

```python
from carebundle import generate_bundle, generate_patient, generate_draw

# A full transaction bundle: Patient, Practitioner, Encounter, Conditions,
# Observations, MedicationRequests, DiagnosticReport.
bundle = generate_bundle(profile="type2_diabetes", seed=42, sex="F", age_range=(45, 65))

# Just a Patient, no clinical history.
patient = generate_patient(seed=42, sex="M")

# The clinical values without the FHIR wrapping — useful for analysis.
draw = generate_draw(profile="ckd_stage3", seed=42, sex="F", age_years=58)
draw.analytes     # {'egfr': Decimal('51'), 'creatinine': Decimal('1.25'), ...}
draw.conditions   # (N18.31 Chronic kidney disease stage 3a, I10 ...)
```

Serialize with `to_json`:

```python
from carebundle.core.bundle import to_json
open("fixture.json", "w").write(to_json(bundle))
```

### Profiles

| Key | Population |
|---|---|
| `healthy` | No chronic disease. Incidental raised LDL and obesity still occur at typical adult rates — suppressing them would make the data less realistic, not more |
| `hypertension` | Essential hypertension on lisinopril |
| `type2_diabetes` | Diagnosed, moderately controlled; ~70% hypertension comorbidity, diabetic dyslipidaemia, ~60% obesity |
| `ckd_stage3` | CKD stage 3, eGFR sampled in band and creatinine inverted from it |

### Mixed cohorts

`profile="mixed"` draws each patient's profile by prevalence, for population-shaped
fixtures rather than a run of identical cases:

```python
from carebundle import generate_cohort

cohort = generate_cohort(count=100, seed=42)                       # default mix
cohort = generate_cohort(count=100, seed=42,
                         prevalence={"healthy": 3, "ckd_stage3": 1})  # or your own
```

Weights are normalised, so counts and ratios both work. The default mix is
illustrative rather than an epidemiological claim — real prevalences overlap heavily
and these profiles are mutually exclusive.

Each bundle carries a comprehensive metabolic panel, CBC, lipid panel, HbA1c,
albuminuria, seven vital signs and the patient's medications and allergies — grouped
into DiagnosticReports under the panel LOINC codes a laboratory actually reports.
Diagnosis codes follow the values drawn: a diabetic whose eGFR falls below 60 is coded
`E11.22` (diabetes *with* CKD) plus the matching KDIGO stage, not `E11.9`.

### CLI

```bash
carebundle profiles
carebundle generate --profile ckd_stage3 --count 20 --seed 42 --sex mixed --out ./fixtures/
carebundle generate --profile mixed --count 100 --seed 42 --out ./cohort/   # mixed cohort
carebundle generate --profile healthy --seed 1            # JSON to stdout
```

---

## Safety

Synthetic data that looks real is a liability if it reaches a real system. Every
generated resource is self-identifying as test data:

- `meta.security` carries **`HTEST`** (`v3-ActReason`), FHIR's own label for test
  health data.
- The narrative opens with **"SYNTHETIC TEST DATA — not a real person."**
- Identifiers use synthetic `urn:uuid` systems. SSN-style identifiers, where used, are
  restricted to the 900–999 area range the SSA has never issued, and the code refuses
  to mint one outside it.
- Practitioners deliberately do **not** carry checksum-valid NPIs, which could collide
  with a real clinician.

**This data is for testing only. It must never be used for clinical decisions.**

---

## Known limits

Stated here rather than left for you to discover.

- **`Encounter.type` carries no code.** Its US Core value set draws on CPT-4
  (AMA-licensed) and SNOMED CT (affiliate-licensed). Neither can be redistributed here,
  so we assert `text` only and accept one warning. Warning-free US Core Encounter
  conformance is not reachable under this licensing position.
- **No SNOMED CT.** Deliberate — see [CONFORMANCE.md](https://github.com/27jackson08/fhirfaker/blob/main/CONFORMANCE.md). Conditions use
  ICD-10-CM, which US Core's Condition binding accepts with zero errors *and* zero
  warnings.
- **Blood pressure marginals are clinical definitions**, not population fits —
  "normotensive" and "hypertensive" are the populations the profiles mean. Everything
  else is calibrated against NHANES (see below).
- **Diabetic BMI runs slightly high.** Generated diabetics are 64.8% obese against
  NHANES's 61.5% for the same age band and stratum, with a median BMI of 32.5 against
  31.9. Weight is drawn from a symmetric truncated normal while the real distribution is
  right-skewed, and BMI is computed from it, so the derived median lands a little above
  target. Within the fidelity tolerance, checked every run, and stated here rather than
  rounded away.
- **One encounter per bundle.** No longitudinal history — that is Synthea's territory.
- **Terminology is a curated subset** — 102 codes (42 LOINC, 29 RxNorm, 21 ICD-10-CM),
  not full coverage. Every code *and display* is verified against its source vocabulary
  by `python -m carebundle.terminology.verify`, which runs nightly in CI.

---

## Development

```bash
uv venv && . .venv/bin/activate
uv pip install -e ".[dev]"

# Three tiers. Only the first runs on every PR.
pytest -m "not conformance and not fidelity"   # ~5s, no JVM, no network
pytest -m fidelity                             # ~45s, 10k draws per profile
pytest -m conformance                          # ~4min, needs a JVM and network
python -m carebundle.fidelity.report     # regenerate the fidelity report
python -m carebundle.spec.codegen        # regenerate models from the R4 StructureDefinitions
python -m carebundle.terminology.verify  # re-check every code against LOINC/RxNorm/ICD-10-CM
python -m carebundle.calibration.nhanes --data-dir <dir>   # re-derive marginals from NHANES
```

`carebundle/models/r4.py` is generated from the official FHIR R4 4.0.1 StructureDefinitions
and checked in; CI fails if it drifts from the spec.

Coverage is enforced at 80% (currently ~85% on the PR gate, ~91% including the fidelity
suite). Generated models and offline build tooling are excluded — counting 886
statements of generated code would flatter the number rather than measure anything.

To intentionally change generated output:

```bash
pytest tests/test_golden.py --update-golden   # then review the diff
```

Changing seeded output at all is a **major** version bump, not a minor one — users pin
test fixtures to a seed. See [CHANGELOG.md](https://github.com/27jackson08/fhirfaker/blob/main/CHANGELOG.md) for the versioned determinism
contract and [RELEASING.md](https://github.com/27jackson08/fhirfaker/blob/main/RELEASING.md) for the release process.

---

## Naming

The published package is **`carebundle`**, and it carries no HL7 mark deliberately. HL7's
[FHIR trademark policy](https://www.hl7.org/documentcenter/public/legal/FHIR_Trademark_Policy.pdf)
forbids abbreviating the mark or combining it with other words, and bars its use in
product names without written permission — so `fhirforge` and `synthfhir` were not
available. Using "FHIR®" descriptively in prose, as this README does, is fine.

The repository is hosted at `fhirfaker`. That name does combine the mark, and it is a
deliberate choice made with the policy in view — the published distribution, which is
what `pip install` resolves and what appears on PyPI, is `carebundle`.

## Licence

Licensed under the **Apache License 2.0** — see [LICENSE](https://github.com/27jackson08/fhirfaker/blob/main/LICENSE). Apache 2.0 over MIT
for the express patent grant, which matters more than usual for a library that
implements published clinical algorithms.

**Terminology attribution:**

- This material contains content from **LOINC®** (http://loinc.org). LOINC is
  copyright © 1995-2024, Regenstrief Institute, Inc. and the LOINC Committee, and is
  available at no cost under the
  [LOINC licence](https://loinc.org/license/).
- **RxNorm** is produced by the U.S. National Library of Medicine. Only RXCUIs and
  NLM-authored normalized names from RxNorm Current Prescribable Content are included.
- **ICD-10-CM** is published by CMS/NCHS and is in the public domain in the US.

FHIR® is the registered trademark of HL7 and is used with the permission of HL7.
