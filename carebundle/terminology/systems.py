"""Canonical code system URIs.

Kept separate from the code tables so a system URI is written once and cannot drift
between resource builders.
"""

from __future__ import annotations

LOINC = "http://loinc.org"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
UCUM = "http://unitsofmeasure.org"

SNOMED = "http://snomed.info/sct"  # Deliberately unused in v1 — see build doc Section 6.

# HL7 terminology (freely usable, no licence gate).
CONDITION_CATEGORY = "http://terminology.hl7.org/CodeSystem/condition-category"
CONDITION_CLINICAL = "http://terminology.hl7.org/CodeSystem/condition-clinical"
CONDITION_VER_STATUS = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
OBSERVATION_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
ALLERGY_CLINICAL = "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
ALLERGY_VER_STATUS = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification"
)
ACT_CODE = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
DIAGNOSTIC_SERVICE_SECTION = "http://terminology.hl7.org/CodeSystem/v2-0074"

US_CORE = "http://hl7.org/fhir/us/core/StructureDefinition"
