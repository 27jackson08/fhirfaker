"""Curated terminology subset.

Every code and display in this file was fetched from its source vocabulary, never
typed from memory. Re-check them at any time with:

    python -m pkg.terminology.verify

Licensing constraints that shape this file (build doc Section 6):
  * LOINC     — redistributable with attribution; codes keep their meanings and
                displays are the LONG_COMMON_NAME the HL7 validator checks against.
  * RxNorm    — only RXCUIs and NLM-authored normalized names, resolved through the
                RxNav `/Prescribe/` endpoints, which serve exactly the Current
                Prescribable Content subset. A code outside that subset returns
                nothing there, so the licence boundary is enforced by the lookup
                rather than by remembering to check.
  * ICD-10-CM — US public domain (CMS/NCHS). This is the US Clinical Modification,
                not WHO ICD-10, which is copyrighted.
  * SNOMED CT — absent by design.

Two traps this file exists to avoid, both found the hard way:
  * Ambiguous drug names. "metformin 500 MG Oral Tablet" resolves to two RXCUIs —
    immediate-release and 24-hour extended-release. "aspirin 81 MG Oral Tablet"
    likewise splits plain from delayed-release. Picking the first hit ships the wrong
    product silently.
  * Wrong displays. A display taken from a third-party code aggregator was rejected
    outright by the validator even though the code was correct.
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


# =================================================================================
# LOINC — laboratory
# =================================================================================

# Glycaemic
HBA1C = Code(systems.LOINC, "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood")
# 2345-7 rather than the fasting-specific 1558-6: the ADAG relationship this project
# anchors glucose to describes *average* glucose, so a fasting-specific code would
# misdescribe the quantity being generated. See correlation/relations.py.
GLUCOSE = Code(systems.LOINC, "2345-7", "Glucose [Mass/volume] in Serum or Plasma")
GLUCOSE_FASTING = Code(
    systems.LOINC, "1558-6", "Fasting glucose [Mass/volume] in Serum or Plasma"
)

# Renal
CREATININE = Code(systems.LOINC, "2160-0", "Creatinine [Mass/volume] in Serum or Plasma")
EGFR = Code(
    systems.LOINC,
    "98979-8",
    "Glomerular filtration rate [Volume Rate/Area] in Serum, Plasma or Blood by "
    "Creatinine-based formula (CKD-EPI 2021)/1.73 sq M",
)
BUN = Code(systems.LOINC, "3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma")
UACR = Code(systems.LOINC, "9318-7", "Albumin/Creatinine [Mass Ratio] in Urine")
MICROALBUMIN_URINE = Code(
    systems.LOINC, "14957-5", "Microalbumin [Mass/volume] in Urine"
)

# Electrolytes and general chemistry
SODIUM = Code(systems.LOINC, "2951-2", "Sodium [Moles/volume] in Serum or Plasma")
POTASSIUM = Code(systems.LOINC, "2823-3", "Potassium [Moles/volume] in Serum or Plasma")
CHLORIDE = Code(systems.LOINC, "2075-0", "Chloride [Moles/volume] in Serum or Plasma")
CO2 = Code(
    systems.LOINC, "2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma"
)
CALCIUM = Code(systems.LOINC, "17861-6", "Calcium [Mass/volume] in Serum or Plasma")
ALBUMIN = Code(systems.LOINC, "1751-7", "Albumin [Mass/volume] in Serum or Plasma")

# Lipids
CHOLESTEROL_TOTAL = Code(
    systems.LOINC, "2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"
)
HDL = Code(
    systems.LOINC, "2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"
)
LDL_CALCULATED = Code(
    systems.LOINC,
    "13457-7",
    "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation",
)
TRIGLYCERIDES = Code(
    systems.LOINC, "2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"
)

# Liver
ALT = Code(
    systems.LOINC,
    "1742-6",
    "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma",
)
AST = Code(
    systems.LOINC,
    "1920-8",
    "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma",
)
ALKALINE_PHOSPHATASE = Code(
    systems.LOINC,
    "6768-6",
    "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma",
)
BILIRUBIN_TOTAL = Code(
    systems.LOINC, "1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"
)

# Haematology
HEMOGLOBIN = Code(systems.LOINC, "718-7", "Hemoglobin [Mass/volume] in Blood")
HEMATOCRIT = Code(
    systems.LOINC, "4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"
)
WBC = Code(
    systems.LOINC, "6690-2", "Leukocytes [#/volume] in Blood by Automated count"
)
PLATELETS = Code(
    systems.LOINC, "777-3", "Platelets [#/volume] in Blood by Automated count"
)
RBC = Code(
    systems.LOINC, "789-8", "Erythrocytes [#/volume] in Blood by Automated count"
)

# =================================================================================
# LOINC — vitals
# =================================================================================
BP_PANEL = Code(
    systems.LOINC, "85354-9", "Blood pressure panel with all children optional"
)
BP_SYSTOLIC = Code(systems.LOINC, "8480-6", "Systolic blood pressure")
BP_DIASTOLIC = Code(systems.LOINC, "8462-4", "Diastolic blood pressure")
BODY_HEIGHT = Code(systems.LOINC, "8302-2", "Body height")
BODY_WEIGHT = Code(systems.LOINC, "29463-7", "Body weight")
BMI = Code(systems.LOINC, "39156-5", "Body mass index (BMI) [Ratio]")
HEART_RATE = Code(systems.LOINC, "8867-4", "Heart rate")
RESPIRATORY_RATE = Code(systems.LOINC, "9279-1", "Respiratory rate")
BODY_TEMPERATURE = Code(systems.LOINC, "8310-5", "Body temperature")
OXYGEN_SATURATION = Code(
    systems.LOINC, "59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry"
)

# =================================================================================
# LOINC — panels and reports
# =================================================================================
LAB_REPORT = Code(systems.LOINC, "11502-2", "Laboratory report")
PANEL_METABOLIC_COMPREHENSIVE = Code(
    systems.LOINC, "24323-8", "Comprehensive metabolic 2000 panel - Serum or Plasma"
)
PANEL_LIPID = Code(
    systems.LOINC, "57698-3", "Lipid panel with direct LDL - Serum or Plasma"
)
PANEL_CBC = Code(systems.LOINC, "58410-2", "CBC panel - Blood by Automated count")

# =================================================================================
# RxNorm — all resolved through RxNav /Prescribe/ (Current Prescribable Content)
# =================================================================================

# Diabetes. 861007 is IMMEDIATE-release metformin; 860975 is the 24 HR
# extended-release form — a different clinical product. Do not swap them.
METFORMIN_500 = Code(
    systems.RXNORM, "861007", "metformin hydrochloride 500 MG Oral Tablet"
)
METFORMIN_1000 = Code(
    systems.RXNORM, "861004", "metformin hydrochloride 1000 MG Oral Tablet"
)
GLIPIZIDE_5 = Code(systems.RXNORM, "310490", "glipizide 5 MG Oral Tablet")
GLIMEPIRIDE_2 = Code(systems.RXNORM, "199246", "glimepiride 2 MG Oral Tablet")
SITAGLIPTIN_100 = Code(systems.RXNORM, "665033", "sitagliptin 100 MG Oral Tablet")
EMPAGLIFLOZIN_10 = Code(systems.RXNORM, "1545658", "empagliflozin 10 MG Oral Tablet")

# Antihypertensives and cardiac
LISINOPRIL_10 = Code(systems.RXNORM, "314076", "lisinopril 10 MG Oral Tablet")
LISINOPRIL_20 = Code(systems.RXNORM, "314077", "lisinopril 20 MG Oral Tablet")
AMLODIPINE_5 = Code(systems.RXNORM, "197361", "amlodipine 5 MG Oral Tablet")
AMLODIPINE_10 = Code(systems.RXNORM, "308135", "amlodipine 10 MG Oral Tablet")
HYDROCHLOROTHIAZIDE_25 = Code(
    systems.RXNORM, "310798", "hydrochlorothiazide 25 MG Oral Tablet"
)
LOSARTAN_50 = Code(systems.RXNORM, "979492", "losartan potassium 50 MG Oral Tablet")
CARVEDILOL_12_5 = Code(systems.RXNORM, "200032", "carvedilol 12.5 MG Oral Tablet")
FUROSEMIDE_40 = Code(systems.RXNORM, "313988", "furosemide 40 MG Oral Tablet")

# Lipid lowering. Rosuvastatin exists only under its salt name in RxNorm —
# "rosuvastatin 10 MG Oral Tablet" resolves to nothing.
ATORVASTATIN_20 = Code(systems.RXNORM, "617310", "atorvastatin 20 MG Oral Tablet")
ATORVASTATIN_40 = Code(systems.RXNORM, "617311", "atorvastatin 40 MG Oral Tablet")
ROSUVASTATIN_10 = Code(
    systems.RXNORM, "859747", "rosuvastatin calcium 10 MG Oral Tablet"
)
SIMVASTATIN_20 = Code(systems.RXNORM, "312961", "simvastatin 20 MG Oral Tablet")

# Other common chronic-care medications. 243670 is the plain tablet; 308416 is the
# delayed-release product.
ASPIRIN_81 = Code(systems.RXNORM, "243670", "aspirin 81 MG Oral Tablet")
LEVOTHYROXINE_50 = Code(
    systems.RXNORM, "966221", "levothyroxine sodium 0.05 MG Oral Tablet"
)
OMEPRAZOLE_20 = Code(
    systems.RXNORM, "198051", "omeprazole 20 MG Delayed Release Oral Capsule"
)
SERTRALINE_50 = Code(systems.RXNORM, "312941", "sertraline 50 MG Oral Tablet")
GABAPENTIN_300 = Code(systems.RXNORM, "310431", "gabapentin 300 MG Oral Capsule")

# --- RxNorm ingredients, used as allergy substances -------------------------------
# US Core's allergy substance value set draws on RxNorm ingredients and SNOMED CT.
# SNOMED is excluded by design, so drug allergies use RxNorm ingredient (TTY=IN)
# codes, all of which are NLM-authored and present in Current Prescribable Content.
#
# These MUST be looked up by exact name. RxNav's approximate search (`search=1`)
# returned 10178 "sulfamethazine" — a veterinary sulfonamide — for a query of
# "sulfamethoxazole", and a multi-ingredient compound for "codeine". Fuzzy matching
# silently substitutes a different molecule.
ALLERGEN_PENICILLIN_G = Code(systems.RXNORM, "7980", "penicillin G")
ALLERGEN_AMOXICILLIN = Code(systems.RXNORM, "723", "amoxicillin")
ALLERGEN_SULFAMETHOXAZOLE = Code(systems.RXNORM, "10180", "sulfamethoxazole")
ALLERGEN_CODEINE = Code(systems.RXNORM, "2670", "codeine")
ALLERGEN_IBUPROFEN = Code(systems.RXNORM, "5640", "ibuprofen")
ALLERGEN_ASPIRIN = Code(systems.RXNORM, "1191", "aspirin")

# =================================================================================
# ICD-10-CM
# =================================================================================

# Diabetes
T2DM_NO_COMPLICATIONS = Code(
    systems.ICD10CM, "E11.9", "Type 2 diabetes mellitus without complications"
)
T2DM_WITH_CKD = Code(
    systems.ICD10CM,
    "E11.22",
    "Type 2 diabetes mellitus with diabetic chronic kidney disease",
)
T2DM_WITH_NEPHROPATHY = Code(
    systems.ICD10CM, "E11.21", "Type 2 diabetes mellitus with diabetic nephropathy"
)
T2DM_WITH_HYPERGLYCEMIA = Code(
    systems.ICD10CM, "E11.65", "Type 2 diabetes mellitus with hyperglycemia"
)
T2DM_WITH_NEUROPATHY = Code(
    systems.ICD10CM,
    "E11.40",
    "Type 2 diabetes mellitus with diabetic neuropathy, unspecified",
)
LONG_TERM_INSULIN_USE = Code(
    systems.ICD10CM, "Z79.4", "Long term (current) use of insulin"
)

# Cardiovascular and metabolic
ESSENTIAL_HYPERTENSION = Code(
    systems.ICD10CM, "I10", "Essential (primary) hypertension"
)
ATHEROSCLEROTIC_HEART_DISEASE = Code(
    systems.ICD10CM,
    "I25.10",
    "Atherosclerotic heart disease of native coronary artery without angina pectoris",
)
HEART_FAILURE = Code(systems.ICD10CM, "I50.9", "Heart failure, unspecified")
HYPERLIPIDEMIA = Code(systems.ICD10CM, "E78.5", "Hyperlipidemia, unspecified")
PURE_HYPERCHOLESTEROLEMIA = Code(
    systems.ICD10CM, "E78.00", "Pure hypercholesterolemia, unspecified"
)
OBESITY = Code(systems.ICD10CM, "E66.9", "Obesity, unspecified")
HYPOTHYROIDISM = Code(systems.ICD10CM, "E03.9", "Hypothyroidism, unspecified")

# Chronic kidney disease. ICD-10-CM splits stage 3 by eGFR band, and the CKD profile
# picks the code matching the eGFR it actually drew — the coded diagnosis and the lab
# value have to agree for the data to be coherent.
CKD_STAGE_1 = Code(systems.ICD10CM, "N18.1", "Chronic kidney disease, stage 1")
CKD_STAGE_2 = Code(systems.ICD10CM, "N18.2", "Chronic kidney disease, stage 2 (mild)")
CKD_STAGE_3_UNSPECIFIED = Code(
    systems.ICD10CM, "N18.30", "Chronic kidney disease, stage 3 unspecified"
)
CKD_STAGE_3A = Code(systems.ICD10CM, "N18.31", "Chronic kidney disease, stage 3a")
CKD_STAGE_3B = Code(systems.ICD10CM, "N18.32", "Chronic kidney disease, stage 3b")
CKD_STAGE_4 = Code(systems.ICD10CM, "N18.4", "Chronic kidney disease, stage 4 (severe)")
CKD_STAGE_5 = Code(systems.ICD10CM, "N18.5", "Chronic kidney disease, stage 5")
CKD_UNSPECIFIED = Code(systems.ICD10CM, "N18.9", "Chronic kidney disease, unspecified")

# =================================================================================
# HL7 workflow and category codes
# =================================================================================
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

# =================================================================================
# UCUM units — (human-readable display, UCUM code)
# =================================================================================
UNIT_PERCENT = ("%", "%")
UNIT_MG_DL = ("mg/dL", "mg/dL")
UNIT_G_DL = ("g/dL", "g/dL")
UNIT_MMOL_L = ("mmol/L", "mmol/L")
UNIT_MMHG = ("mmHg", "mm[Hg]")
UNIT_BPM = ("beats/minute", "/min")
UNIT_BREATHS_MIN = ("breaths/minute", "/min")
UNIT_CM = ("cm", "cm")
UNIT_KG = ("kg", "kg")
UNIT_KG_M2 = ("kg/m2", "kg/m2")
UNIT_CELSIUS = ("Cel", "Cel")
UNIT_IU_L = ("U/L", "U/L")
UNIT_MG_G = ("mg/g", "mg/g")
UNIT_K_PER_UL = ("10*3/uL", "10*3/uL")
UNIT_M_PER_UL = ("10*6/uL", "10*6/uL")
# UCUM curly-brace annotation: the 1.73 m2 normalisation is an annotation, not a unit.
# The human-readable unit must carry the annotation too — the validator warns when the
# UCUM code has one and Quantity.unit does not, because annotations are ignored during
# unit comparison and the two strings then disagree about what was measured.
UNIT_EGFR = ("mL/min/{1.73_m2}", "mL/min/{1.73_m2}")
