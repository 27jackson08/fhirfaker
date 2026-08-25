# FHIR export emits Observations without `value[x]`, and 166 validator errors per bundle

**Version:** `tietai-synthea` 1.0.1 (PyPI) · Python 3.12 · macOS
**Paper:** arXiv:2606.28346

Thanks for building this — a JVM-free Synthea is genuinely useful, and the install was
painless. I was adding PySynthea to an open benchmark that scores synthetic FHIR against
NHANES, and hit a blocker I think is a bug rather than a design choice.

## The blocker: vital signs and labs have no values

```bash
python3.12 -m venv env && env/bin/pip install tietai-synthea
env/bin/synthea -p 10 -s 42 -a 18-85 -o ./psout
```

Across 10 patients / 406 Observations:

| | |
|---|---:|
| Observations emitted | 406 |
| Carrying a `valueQuantity` | 60 (**15%**) |
| Systolic, diastolic, height, weight **with a value** | **0** |
| Glucose, HDL, triglycerides, HbA1c, ALT, AST **with a value** | **0** |

The 60 valued observations are pain scores, temperatures, DXA T-scores, FEV1/FVC, PSA,
NT-proBNP and magnesium. The codes are all emitted — the values are not.

A systolic blood pressure comes out like this:

```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{"coding": [{"system": ".../observation-category",
                            "code": "laboratory", "display": "Laboratory"}]}],
  "code": {"coding": [{"system": "LOINC", "code": "8480-6",
                       "display": "Systolic Blood Pressure"}]},
  "effectiveDateTime": "1949-08-25T16:44:49.966003"
}
```

`status: "final"` with no `value[x]` and no `dataAbsentReason` is a final result that
records nothing. FHIR's `obs-6` invariant requires one or the other, and any consumer
reading these gets a patient with a blood pressure observation and no blood pressure.

I looked for a config flag governing this in `resources/synthea.properties` and did not
find one; `exporter.fhir.export = true` is the default and is what ran. Happy to be told
I missed a switch.

## Also, from the official HL7 validator

`org.hl7.fhir.core` `validator_cli`, FHIR R4 4.0.1, on a single bundle:
**166 errors, 266 warnings.** The recurring ones look like small, mechanical fixes:

| count | issue | fix |
|---:|---|---|
| 40 | `If a date has a time, it must have a timezone` | `1949-08-25T16:44:49.966003` needs an offset or `Z` |
| 16 | `Unknown code 'AMBULATORY' in v3-ActCode` | the code is `AMB` |
| 9 | `Wrong Display Name 'Vital-Signs'` | display is `Vital Signs` |
| 8 | `Array cannot be empty` | omit the property instead of emitting `[]` |
| 4 | `Coding.system must be an absolute reference` | `"LOINC"` → `http://loinc.org` |

The last one matters for interoperability beyond validation: a consumer matching on
system URI will not recognise any of these codes.

Blood-pressure observations are also categorised `laboratory` rather than
`vital-signs`, which US Core's vital-signs profile requires.

## Why I'm reporting rather than just moving on

I maintain a small generator in the same space, so treat this as interested-party
feedback and discount accordingly. But I benchmark against Synthea too, and I published a
retraction when my own headline comparison against it turned out to be false — I would
rather send this than write around it.

The reproduction above is complete, and I'm glad to test a fix or open a PR for the
mechanical validator items if that's useful.
