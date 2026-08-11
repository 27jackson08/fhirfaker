# Conformance Matrix

Regenerated per release. Every claim here is produced by the official HL7 FHIR
validator, not by inspection.

**Target:** FHIR R4 4.0.1 · US Core 6.1.0
**Validator:** `org.hl7.fhir.core` validator_cli (latest release)
**Command:** `pytest tests/ -m conformance`

## Status — Phase 1

| Resource | Profile | Errors | Warnings |
|---|---|---:|---:|
| Patient | us-core-patient | 0 | 0 |
| Practitioner | us-core-practitioner | 0 | 0 |
| Encounter | us-core-encounter | 0 | 1 |
| Condition | us-core-condition-problems-health-concerns | 0 | 0 |
| Observation (lab) | us-core-observation-lab | 0 | 0 |
| Observation (BP) | us-core-blood-pressure | 0 | 0 |
| MedicationRequest | us-core-medicationrequest | 0 | 2 |
| DiagnosticReport | us-core-diagnosticreport-lab | 0 | 1 |
| Bundle (transaction, 9 entries) | — | **0** | **4** |

## Accepted warnings

Warnings are not ignored wholesale. Each one below has been examined and has a
reason to remain; `test_bundle_raises_no_unexamined_warnings` fails if a *new*
warning appears, so this list cannot silently grow.

### 1. `Encounter.type` — no code provided

> No code provided, and a code should be provided from the value set
> 'US Core Encounter Type'

**Why it stays.** The US Core Encounter Type value set draws on CPT-4 (AMA-licensed,
not redistributable) and SNOMED CT (affiliate-licensed, excluded by design — build
doc Section 6). We assert `text` only rather than embed a code we have no licence to
ship. The binding is extensible, so this degrades to a warning rather than an error.

**Consequence to state in the README.** Full, warning-free US Core Encounter
conformance is not reachable without a licensed vocabulary. This is a real limit of
the no-SNOMED/no-CPT position, not an oversight.

### 2 & 3. `MedicationRequest.medication` — RxNorm version and value set

> A definition for CodeSystem '…rxnorm' version '06052023' could not be found.
> Valid versions: 03022026
>
> None of the codings provided are in the value set 'Medication Clinical Drug'
> (…|20170601)

**Why it stays.** RXCUI `861007` (metformin hydrochloride 500 MG Oral Tablet) was
resolved against the RxNav `/Prescribe/` endpoint, so it is current prescribable
content. The mismatch is between the validator's bundled RxNorm release and the
value set binding's pinned version — an environment artefact, not a defect in the
generated data.

### 4. `DiagnosticReport.code` — not in US Core Laboratory Test Codes

> None of the codings provided are in the value set 'US Core Laboratory Test Codes'
> (codes = http://loinc.org#11502-2)

**Why it stays.** LOINC `11502-2` is "Laboratory report", a document-class code. That
is semantically correct for `DiagnosticReport.code` on a multi-analyte report. The US
Core value set admits only lab *test* codes, so satisfying it would mean coding a
two-analyte report as if it were a single test. Silencing the warning would make the
data less accurate, so we keep the accurate code and document the warning.

Revisit in Phase 3: profiles that emit a defined panel can use that panel's LOINC
code, which is both in the value set and semantically right.

## Notes

- The JVM is required only to run this matrix. It is never a runtime or install
  dependency of the published package.
- The first validator run downloads ~460 MB of IG packages into `~/.fhir`. Later runs
  hit that cache; CI caches it between runs.
