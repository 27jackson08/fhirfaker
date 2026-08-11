"""Curated terminology subset.

Phase 1 starter set; Phase 2 expands it to the sizes in build doc Section 6
(~30-50 LOINC, 20-30 RxNorm, 15-20 ICD-10-CM).

Licensing constraints that shape this file (build doc Section 6):
  * LOINC     — redistributable with attribution; codes must keep their meanings.
  * RxNorm    — only RXCUIs and NLM-authored normalized names, drawn from RxNorm
                Current Prescribable Content. No proprietary source vocabularies.
  * ICD-10-CM — US public domain (CMS/NCHS). Note this is the US Clinical
                Modification, not WHO ICD-10, which is copyrighted.
  * SNOMED CT — absent by design.

Every RxNorm entry here was resolved against the RxNav `/Prescribe/` endpoints, which
serve exactly the Current Prescribable Content subset, so membership is verified
rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

from pkg.models.r4 import CodeableConcept, Coding
from pkg.terminology import systems


@dataclass(frozen=True)
class Code:
    """One coded concept plus the provenance needed to defend shipping it."""

    system: str
    code: str
    display: str

    def coding(self) -> Coding:
        return Coding(system=self.system, code=self.code, display=self.display)

    def concept(self, text: str | None = None) -> CodeableConcept:
        return CodeableConcept(coding=[self.coding()], text=text or self.display)


# --- LOINC: labs -----------------------------------------------------------------
HBA1C = Code(systems.LOINC, "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood")
GLUCOSE_FASTING = Code(
    systems.LOINC, "1558-6", "Fasting glucose [Mass/volume] in Serum or Plasma"
)
CREATININE = Code(
    systems.LOINC, "2160-0", "Creatinine [Mass/volume] in Serum or Plasma"
)

# --- LOINC: vitals ---------------------------------------------------------------
BP_PANEL = Code(systems.LOINC, "85354-9", "Blood pressure panel with all children optional")
BP_SYSTOLIC = Code(systems.LOINC, "8480-6", "Systolic blood pressure")
BP_DIASTOLIC = Code(systems.LOINC, "8462-4", "Diastolic blood pressure")
BODY_HEIGHT = Code(systems.LOINC, "8302-2", "Body height")
BODY_WEIGHT = Code(systems.LOINC, "29463-7", "Body weight")
HEART_RATE = Code(systems.LOINC, "8867-4", "Heart rate")

# --- LOINC: report codes ---------------------------------------------------------
LAB_REPORT = Code(systems.LOINC, "11502-2", "Laboratory report")

# --- RxNorm (verified against RxNav /Prescribe/) ---------------------------------
# 861007 is IMMEDIATE-release metformin. 860975 is the 24 HR extended-release form —
# a different clinical product. Do not swap them.
METFORMIN_500 = Code(
    systems.RXNORM, "861007", "metformin hydrochloride 500 MG Oral Tablet"
)
LISINOPRIL_10 = Code(systems.RXNORM, "314076", "lisinopril 10 MG Oral Tablet")
ATORVASTATIN_20 = Code(systems.RXNORM, "617310", "atorvastatin 20 MG Oral Tablet")

# --- ICD-10-CM -------------------------------------------------------------------
T2DM_NO_COMPLICATIONS = Code(
    systems.ICD10CM, "E11.9", "Type 2 diabetes mellitus without complications"
)
ESSENTIAL_HYPERTENSION = Code(
    systems.ICD10CM, "I10", "Essential (primary) hypertension"
)

# --- HL7 workflow/category codes -------------------------------------------------
CATEGORY_LABORATORY = Code(systems.OBSERVATION_CATEGORY, "laboratory", "Laboratory")
CATEGORY_VITAL_SIGNS = Code(systems.OBSERVATION_CATEGORY, "vital-signs", "Vital Signs")
CATEGORY_PROBLEM_LIST = Code(
    systems.CONDITION_CATEGORY, "problem-list-item", "Problem List Item"
)
CATEGORY_ENCOUNTER_DIAGNOSIS = Code(
    systems.CONDITION_CATEGORY, "encounter-diagnosis", "Encounter Diagnosis"
)
CLINICAL_ACTIVE = Code(systems.CONDITION_CLINICAL, "active", "Active")
VERIFICATION_CONFIRMED = Code(systems.CONDITION_VER_STATUS, "confirmed", "Confirmed")
ALLERGY_ACTIVE = Code(systems.ALLERGY_CLINICAL, "active", "Active")
ALLERGY_CONFIRMED = Code(systems.ALLERGY_VER_STATUS, "confirmed", "Confirmed")
ENCOUNTER_AMBULATORY = Code(systems.ACT_CODE, "AMB", "ambulatory")
SERVICE_SECTION_LAB = Code(systems.DIAGNOSTIC_SERVICE_SECTION, "LAB", "Laboratory")

# --- UCUM units ------------------------------------------------------------------
UNIT_PERCENT = ("%", "%")
UNIT_MG_DL = ("mg/dL", "mg/dL")
UNIT_MMHG = ("mmHg", "mm[Hg]")
UNIT_BPM = ("beats/minute", "/min")
UNIT_CM = ("cm", "cm")
UNIT_KG = ("kg", "kg")
