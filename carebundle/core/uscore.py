"""US Core 6.1.0 profile canonical URLs.

Asserting `meta.profile` is what makes the validator check against the profile rather
than only base R4. Without it, conformance claims mean much less.
"""

from __future__ import annotations

_BASE = "http://hl7.org/fhir/us/core/StructureDefinition"

PATIENT = f"{_BASE}/us-core-patient"
PRACTITIONER = f"{_BASE}/us-core-practitioner"
ENCOUNTER = f"{_BASE}/us-core-encounter"
CONDITION_PROBLEMS = f"{_BASE}/us-core-condition-problems-health-concerns"
CONDITION_ENCOUNTER_DIAGNOSIS = f"{_BASE}/us-core-condition-encounter-diagnosis"
OBSERVATION_LAB = f"{_BASE}/us-core-observation-lab"
BLOOD_PRESSURE = f"{_BASE}/us-core-blood-pressure"
BODY_HEIGHT = f"{_BASE}/us-core-body-height"
BODY_WEIGHT = f"{_BASE}/us-core-body-weight"
BMI = f"{_BASE}/us-core-bmi"
HEART_RATE = f"{_BASE}/us-core-heart-rate"
RESPIRATORY_RATE = f"{_BASE}/us-core-respiratory-rate"
BODY_TEMPERATURE = f"{_BASE}/us-core-body-temperature"
PULSE_OXIMETRY = f"{_BASE}/us-core-pulse-oximetry"
MEDICATION_REQUEST = f"{_BASE}/us-core-medicationrequest"
DIAGNOSTIC_REPORT_LAB = f"{_BASE}/us-core-diagnosticreport-lab"
ALLERGY_INTOLERANCE = f"{_BASE}/us-core-allergyintolerance"
