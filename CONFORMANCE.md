# Conformance Matrix

Regenerated per release. Every claim here is produced by the official HL7 FHIR
validator, not by inspection.

**Target:** FHIR R4 4.0.1 · US Core 6.1.0
**Validator:** `org.hl7.fhir.core` validator_cli (latest release)
**Command:** `pytest tests/ -m conformance`

## Status

Every clinical profile is validated as a whole transaction bundle, so each resource is
checked against its asserted `meta.profile` and every intra-bundle reference is
resolved.

| Profile | Entries | Errors | Warnings |
|---|---:|---:|---:|
| healthy | 42 | **0** | 2 |
| hypertension | 45 | **0** | 4 |
| type2_diabetes | 50 | **0** | 10 |
| ckd_stage3 | 52 | **0** | 12 |

Warning counts scale with the number of medications, because each RxNorm-coded
MedicationRequest raises the same two version/value-set warnings described below.

| Resource | Profile | Errors |
|---|---|---:|
| Patient | us-core-patient | 0 |
| Practitioner | us-core-practitioner | 0 |
| Encounter | us-core-encounter | 0 |
| Condition | us-core-condition-problems-health-concerns | 0 |
| Observation (lab) | us-core-observation-lab | 0 |
| Observation (BP) | us-core-blood-pressure | 0 |
| Observation (vitals) | us-core-body-height / -body-weight / -bmi / -heart-rate / -respiratory-rate / -body-temperature / -pulse-oximetry | 0 |
| AllergyIntolerance | us-core-allergyintolerance | 0 |
| MedicationRequest | us-core-medicationrequest | 0 |
| DiagnosticReport | us-core-diagnosticreport-lab | 0 |

## Accepted warnings

Warnings are not ignored wholesale. Each one below has been examined and has a reason
to remain; `test_bundle_raises_no_unexamined_warnings` fails if a *new* warning
appears, so this list cannot silently grow.

### 1. `Encounter.type` — no code provided

> No code provided, and a code should be provided from the value set
> 'US Core Encounter Type'

**Why it stays.** That value set draws on CPT-4 (AMA-licensed, not redistributable)
and SNOMED CT (affiliate-licensed, excluded by design — build doc Section 6). We
assert `text` only rather than embed a code we have no licence to ship. The binding is
extensible, so this degrades to a warning rather than an error.

**Consequence to state in the README.** Warning-free US Core Encounter conformance is
not reachable without a licensed vocabulary. That is a real limit of the
no-SNOMED/no-CPT position, not an oversight.

### 2. `Observation.valueQuantity` — annotated UCUM code

> UCUM Codes that contain human readable annotations like {1.73_m2} can be misleading

**Why it stays.** `mL/min/{1.73_m2}` is the standard UCUM representation for eGFR, and
the annotation carries the body-surface-area normalisation that defines the quantity.
The warning is generic best-practice advice that fires on *any* annotated code. We do
keep `Quantity.unit` in sync with the annotated code, which clears the second half of
the original warning.

### 3 & 4. `MedicationRequest.medication` — RxNorm version and value set

**Why it stays.** RXCUI `861007` was resolved against the RxNav `/Prescribe/`
endpoint, so it is current prescribable content. The mismatch is between the
validator's bundled RxNorm release and the value set binding's pinned version — an
environment artefact, not a defect in the generated data.

### ~~5. `DiagnosticReport.code` — not in US Core Laboratory Test Codes~~ RESOLVED

This warning is gone. Results are now grouped into the panels a laboratory actually
reports — comprehensive metabolic, CBC, lipid, HbA1c, albuminuria — and each
DiagnosticReport carries that panel's own LOINC code, which *is* in the value set.
The earlier generic "Laboratory report" (11502-2) is a document code.

Resolved exactly as this section predicted: by making the data more accurate rather
than by suppressing the warning.

## Notes

- The JVM is required only to run this matrix. It is never a runtime or install
  dependency of the published package.
- The first validator run downloads ~460 MB of IG packages into `~/.fhir`. Later runs
  hit that cache; CI caches it between runs.
- If the validator subprocess fails to produce a summary line, the harness raises
  rather than reporting a result. A conformance gate that cannot fail is worse than no
  gate, so silence is never treated as success.
