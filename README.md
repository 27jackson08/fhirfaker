# pkg — clinically coherent synthetic FHIR® test data for Python

> **Working title.** The package name is not settled — see [Naming](#naming). Every
> command below uses the placeholder `pkg`.

`pip install`, import, and get a **US Core-conformant FHIR R4 Bundle** back as a Python
object. No JVM, no config file, no output directory to manage.

```python
from pkg import generate_bundle

bundle = generate_bundle(profile="type2_diabetes", seed=42, sex="F")
bundle.entry            # work with it in-process
```

```bash
pkg generate --profile type2_diabetes --count 20 --seed 42 --out ./fixtures/
```

---

## Why not Synthea?

You probably should use [Synthea](https://github.com/synthetichealth/synthea). It is
excellent, mature, peer-reviewed, and does far more than this: full birth-to-death
population simulation, 100+ disease modules, C-CDA and bulk ndjson output, and its own
US Core-conformant FHIR export.

This project is not "better than Synthea". It is what you reach for when Synthea is
overkill:

| | Synthea | this |
|---|---|---|
| Runtime | Java JDK 17+ | pure Python, `pydantic` + `numpy` |
| Shape | batch — generates a population into a folder | library — returns a `Bundle` object in-process |
| Scope | full patient lifecycle simulation | one visit, clinically coherent |
| Reproducible fixtures | not a contract | **byte-identical for a given seed** |

If you want a realistic population to analyse, use Synthea. If you want five diabetic
patients with coherent lab panels inside a pytest fixture, this is smaller.

**What this is explicitly not:** a population health simulator, a replacement for
Synthea's disease-module depth, or a terminology server.

---

## What makes the data defensible

Three layers, weakest to strongest.

### 1. Conformance — proven, not claimed

Output is validated by the **official HL7 FHIR validator** against US Core 6.1.0 on
every release. The full matrix is published in [CONFORMANCE.md](CONFORMANCE.md).

| Profile | Entries | Errors | Warnings |
|---|---:|---:|---:|
| healthy | 9 | **0** | 3 |
| hypertension | 11 | **0** | 5 |
| type2_diabetes | 12 | **0** | 5 |
| ckd_stage3 | 12 | **0** | 5 |

All five remaining warnings are examined and documented with reasons; a *new* warning
fails the build.

### 2. Verified fidelity — the actual differentiator

Most quick synthetic generators randomise each field independently, which is how you
end up with a diabetes diagnosis next to an HbA1c of 5.2%. Here, analytes are drawn
**jointly** from a Gaussian copula, and derived values are **computed** from published
formulas rather than sampled.

The claim is checked statistically on every run and published as a
[fidelity report](FIDELITY.md):

| Check | Observed | Expected | Source |
|---|---:|---:|---|
| ADAG slope | 28.51 | 28.70 | Nathan 2008 |
| **ADAG R²** | **0.841** | **0.840** | Nathan 2008 |
| glucose at HbA1c 8.0% | 183.0 | 182.9 mg/dL | Nathan 2008 |
| eGFR consistent with creatinine | exact | exact | CKD-EPI 2021 |
| CKD stage-3 eGFR within band | 100% | 100% | KDIGO 2012 |
| T2DM hypertension comorbidity | 0.703 | 0.700 | profile config |

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
bytes, enforced by committed [golden files](tests/golden/).

- No `uuid4()`: ids are UUIDv5 derived from `(seed, role, index)`.
- No `datetime.now()`: the reference date is injected.
- No `hash()`: Python salts it per process, which would break reproducibility across
  runs while looking deterministic within one.

**Stability policy:** generated output changes only on a **major** version bump. You
can safely pin test fixtures to a seed.

---

## Install

```bash
pip install pkg
```

Runtime dependencies: `pydantic>=2`, `numpy>=1.24`. That is the whole list.

> The HL7 validator needs a JVM, but it is a **development and CI dependency only**.
> It is never required to install or run this package.

---

## Usage

```python
from pkg import generate_bundle, generate_patient, generate_draw

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
from pkg.core.bundle import to_json
open("fixture.json", "w").write(to_json(bundle))
```

### Profiles

| Key | Population |
|---|---|
| `healthy` | Healthy baseline, no conditions or prescriptions |
| `hypertension` | Essential hypertension on lisinopril |
| `type2_diabetes` | Diagnosed, moderately controlled; ~70% hypertension comorbidity |
| `ckd_stage3` | CKD stage 3, eGFR sampled in band and creatinine inverted from it |

### CLI

```bash
pkg profiles
pkg generate --profile ckd_stage3 --count 20 --seed 42 --sex mixed --out ./fixtures/
pkg generate --profile healthy --seed 1            # JSON to stdout
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
- **No SNOMED CT.** Deliberate — see [CONFORMANCE.md](CONFORMANCE.md). Conditions use
  ICD-10-CM, which US Core's Condition binding accepts with zero errors *and* zero
  warnings.
- **Marginals are clinically-informed estimates**, not fits to a named cohort. What
  comes from the literature is the *dependence* structure. Calibrating marginals
  against NHANES is future work, and the fidelity report says so.
- **One encounter per bundle.** No longitudinal history — that is Synthea's territory.
- **Terminology is a curated subset**, sized to the profiles that exist rather than to
  full coverage.

---

## Development

```bash
uv venv && . .venv/bin/activate
uv pip install -e ".[dev]"

pytest -m "not conformance"       # fast: unit, property, golden, fidelity
pytest -m conformance             # needs a JVM; downloads ~460MB of IGs on first run
python -m pkg.fidelity.report     # regenerate the fidelity report
python -m pkg.spec.codegen        # regenerate models from the R4 StructureDefinitions
```

`pkg/models/r4.py` is generated from the official FHIR R4 4.0.1 StructureDefinitions
and checked in; CI fails if it drifts from the spec.

To intentionally change generated output:

```bash
pytest tests/test_golden.py --update-golden   # then review the diff
```

---

## Naming

The package name is unsettled. HL7's
[FHIR trademark policy](https://www.hl7.org/documentcenter/public/legal/FHIR_Trademark_Policy.pdf)
forbids abbreviating the mark or combining it with other words, and bars its use in
product names without written permission — so `fhirforge` and `synthfhir` are not
available. Using "FHIR®" descriptively in prose, as this README does, is fine.

## Licence

Project licence: **TBD** (MIT or Apache 2.0).

**Terminology attribution:**

- This material contains content from **LOINC®** (http://loinc.org). LOINC is
  copyright © 1995-2024, Regenstrief Institute, Inc. and the LOINC Committee, and is
  available at no cost under the
  [LOINC licence](https://loinc.org/license/).
- **RxNorm** is produced by the U.S. National Library of Medicine. Only RXCUIs and
  NLM-authored normalized names from RxNorm Current Prescribable Content are included.
- **ICD-10-CM** is published by CMS/NCHS and is in the public domain in the US.

FHIR® is the registered trademark of HL7 and is used with the permission of HL7.
