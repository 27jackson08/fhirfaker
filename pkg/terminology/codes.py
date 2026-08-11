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
# 2345-7 rather than the fasting-specific 1558-6: the ADAG relationship this project
# anchors glucose to describes *average* glucose, so a fasting-specific code would
# misdescribe the quantity being generated. See correlation/relations.py.
GLUCOSE = Code(systems.LOINC, "2345-7", "Glucose [Mass/volume] in Serum or Plasma")
GLUCOSE_FASTING = Code(
    systems.LOINC, "1558-6", "Fasting glucose [Mass/volume] in Serum or Plasma"
)
CREATININE = Code(
    systems.LOINC, "2160-0", "Creatinine [Mass/volume] in Serum or Plasma"
)
# Display strings are checked by the HL7 validator, not just the codes. This one was
# first taken from a third-party code listing that used the older "/1.73 sq M.predicted"
# phrasing and was rejected: "Wrong Display Name ... Valid display is one of 3 choices".
# Take displays from LOINC itself, never from a secondary aggregator.
EGFR = Code(
    systems.LOINC,
    "98979-8",
    "Glomerular filtration rate [Volume Rate/Area] in Serum, Plasma or Blood by "
    "Creatinine-based formula (CKD-EPI 2021)/1.73 sq M",
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
# ICD-10-CM splits stage 3 by eGFR band. The CKD profile picks the code that matches
# the eGFR it actually drew, rather than always emitting the unspecified code — the
# coded diagnosis and the lab value have to agree for the data to be coherent.
CKD_STAGE_3_UNSPECIFIED = Code(
    systems.ICD10CM, "N18.30", "Chronic kidney disease, stage 3 unspecified"
)
CKD_STAGE_3A = Code(systems.ICD10CM, "N18.31", "Chronic kidney disease, stage 3a")
CKD_STAGE_3B = Code(systems.ICD10CM, "N18.32", "Chronic kidney disease, stage 3b")

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
# UCUM curly-brace annotation: the 1.73 m2 normalisation is an annotation, not a unit.
# The human-readable unit must carry the annotation too — the validator warns when the
# UCUM code has one and Quantity.unit does not, because annotations are ignored during
# unit comparison and the two strings then disagree about what was measured.
UNIT_EGFR = ("mL/min/{1.73_m2}", "mL/min/{1.73_m2}")
