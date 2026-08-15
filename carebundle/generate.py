"""Bundle generation — the public API.

A bundle is produced from a single profile draw, so the Conditions, Observations and
MedicationRequests inside it all come from one coherent sample rather than being
decided independently. That is the whole point of the correlation engine
(build doc Section 8).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

import numpy as np

from carebundle.builders.clinical import (
    build_allergy_intolerance,
    build_blood_pressure,
    build_condition,
    build_lab_observation,
    build_vital_observation,
)
from carebundle.builders.orders import (
    build_diagnostic_report,
    build_encounter,
    build_medication_request,
)
from carebundle.builders.people import build_patient, build_practitioner
from carebundle.core import uscore
from carebundle.core.bundle import Entry, build_transaction_bundle, to_json  # noqa: F401
from carebundle.core.ids import deterministic_uuid, stable_digest, urn_uuid
from carebundle.models.r4 import Bundle, CodeableConcept
from carebundle.profiles.base import ProfileDraw, draw
from carebundle.profiles.library import PROFILES, get_profile
from carebundle.terminology import codes

# Injected rather than read from the clock: any datetime.now() call would destroy the
# determinism contract (build doc Section 9).
DEFAULT_REFERENCE_DATE = date(2026, 1, 1)

# US Core's Encounter.type value set draws on CPT-4 (AMA-licensed) and SNOMED CT
# (affiliate-licensed). Neither can ship here, so we assert text only and let the
# extensible binding degrade to a warning rather than embed an unlicensed code.
AMBULATORY_VISIT_TYPE = CodeableConcept(text="Ambulatory visit")

SEX_TO_FHIR_GENDER = {"F": "female", "M": "male"}

# Laboratory results are grouped into the panels a laboratory actually reports, and
# each panel's DiagnosticReport carries that panel's own LOINC code. A single report
# coded "Laboratory report" (11502-2) is a *document* code, which US Core's lab test
# value set rightly excludes — using real panel codes is both more accurate and
# removes the warning that came with the generic one.
LAB_PANELS = (
    (
        "cmp",
        codes.PANEL_METABOLIC_COMPREHENSIVE,
        (
            ("sodium", codes.SODIUM, codes.UNIT_MMOL_L),
            ("potassium", codes.POTASSIUM, codes.UNIT_MMOL_L),
            ("chloride", codes.CHLORIDE, codes.UNIT_MMOL_L),
            ("co2", codes.CO2, codes.UNIT_MMOL_L),
            ("calcium", codes.CALCIUM, codes.UNIT_MG_DL),
            ("albumin", codes.ALBUMIN, codes.UNIT_G_DL),
            ("bun", codes.BUN, codes.UNIT_MG_DL),
            ("creatinine", codes.CREATININE, codes.UNIT_MG_DL),
            # Laboratories report eGFR alongside creatinine on the same panel.
            ("egfr", codes.EGFR, codes.UNIT_EGFR),
            ("glucose", codes.GLUCOSE, codes.UNIT_MG_DL),
            ("alt", codes.ALT, codes.UNIT_IU_L),
            ("ast", codes.AST, codes.UNIT_IU_L),
            ("alkaline_phosphatase", codes.ALKALINE_PHOSPHATASE, codes.UNIT_IU_L),
            ("bilirubin_total", codes.BILIRUBIN_TOTAL, codes.UNIT_MG_DL),
        ),
    ),
    (
        "cbc",
        codes.PANEL_CBC,
        (
            ("hemoglobin", codes.HEMOGLOBIN, codes.UNIT_G_DL),
            ("hematocrit", codes.HEMATOCRIT, codes.UNIT_PERCENT),
            ("rbc", codes.RBC, codes.UNIT_M_PER_UL),
            ("wbc", codes.WBC, codes.UNIT_K_PER_UL),
            ("platelets", codes.PLATELETS, codes.UNIT_K_PER_UL),
        ),
    ),
    (
        "lipid",
        codes.PANEL_LIPID,
        (
            ("cholesterol_total", codes.CHOLESTEROL_TOTAL, codes.UNIT_MG_DL),
            ("hdl", codes.HDL, codes.UNIT_MG_DL),
            ("ldl", codes.LDL_CALCULATED, codes.UNIT_MG_DL),
            ("triglycerides", codes.TRIGLYCERIDES, codes.UNIT_MG_DL),
        ),
    ),
    (
        "hba1c",
        codes.HBA1C,
        (("hba1c", codes.HBA1C, codes.UNIT_PERCENT),),
    ),
    (
        "albuminuria",
        codes.UACR,
        (
            ("uacr", codes.UACR, codes.UNIT_MG_G),
            ("microalbumin_urine", codes.MICROALBUMIN_URINE, codes.UNIT_MG_DL),
        ),
    ),
)

# Panel keys, in emission order.
ALL_PANELS = ("cmp", "cbc", "lipid", "hba1c", "albuminuria")

# The panels a lean fixture wants: whatever the presenting problem needs, nothing
# else. A 50-entry bundle is realistic for a real visit but heavy for someone who
# just wants five diabetic patients in a pytest fixture, and "lightweight" is the
# whole positioning.
LEAN_PANELS = ("hba1c", "lipid")

# Analyte -> (LOINC code, US Core vitals profile, unit).
VITAL_ANALYTES = (
    ("height_cm", codes.BODY_HEIGHT, uscore.BODY_HEIGHT, codes.UNIT_CM),
    ("weight_kg", codes.BODY_WEIGHT, uscore.BODY_WEIGHT, codes.UNIT_KG),
    ("bmi", codes.BMI, uscore.BMI, codes.UNIT_KG_M2),
    ("heart_rate", codes.HEART_RATE, uscore.HEART_RATE, codes.UNIT_BPM),
    ("respiratory_rate", codes.RESPIRATORY_RATE, uscore.RESPIRATORY_RATE,
     codes.UNIT_BREATHS_MIN),
    ("body_temperature", codes.BODY_TEMPERATURE, uscore.BODY_TEMPERATURE,
     codes.UNIT_CELSIUS),
    ("oxygen_saturation", codes.OXYGEN_SATURATION, uscore.PULSE_OXIMETRY,
     codes.UNIT_PERCENT),
)

# Vitals whose US Core profile requires extra codings on Observation.code.
VITAL_EXTRA_CODES = {
    "oxygen_saturation": (codes.OXYGEN_SATURATION_ARTERIAL,),
}


def _birth_date(rng, age_range: tuple[int, int], reference: date) -> tuple[date, float]:
    low, high = age_range
    age = int(rng.integers(low, high + 1))
    day_offset = int(rng.integers(0, 365))
    born = reference - timedelta(days=age * 365 + day_offset)
    return born, (reference - born).days / 365.25


def _require_sex(sex: str) -> None:
    if sex not in SEX_TO_FHIR_GENDER:
        raise ValueError(f"sex must be one of {sorted(SEX_TO_FHIR_GENDER)}, got {sex!r}")


def _require_age_range(age_range: tuple[int, int]) -> None:
    """Validate at the library boundary, not just in the CLI.

    A reversed range was previously caught only incidentally, by numpy raising
    "low >= high" from inside the sampler — an error that says nothing about which
    argument was wrong.
    """
    low, high = age_range
    if low > high:
        raise ValueError(f"age_range low {low} exceeds high {high}")
    if low < 0:
        raise ValueError(f"age_range cannot be negative, got {age_range}")


def generate_patient(
    *,
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
):
    """Generate a single US Core Patient with no clinical history."""
    _require_sex(sex)
    _require_age_range(age_range)
    rng = np.random.default_rng([seed, index])
    born, _ = _birth_date(rng, age_range, reference_date)
    return build_patient(
        resource_id=deterministic_uuid(seed, "patient", index),
        sex=sex,
        birth_date=born,
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )


def generate_draw(
    *,
    profile: str = "type2_diabetes",
    seed: int,
    sex: str = "F",
    age_years: float = 55.0,
    index: int = 0,
) -> ProfileDraw:
    """Draw clinical values without building FHIR — useful for analysis and testing."""
    _require_sex(sex)
    # The profile key enters the seed so two profiles sharing a marginal do not draw
    # identical values at the same seed. stable_digest, not hash(): the built-in is
    # salted per process and would break byte-identical output across runs.
    rng = np.random.default_rng([seed, index, stable_digest(profile)])
    return draw(get_profile(profile, sex), rng=rng, age_years=age_years, sex=sex)


# Illustrative prevalence for a 45-65 adult cohort. Real US prevalences overlap
# heavily (a patient can have all three), and these profiles are mutually exclusive,
# so this is a plausible mix rather than an epidemiological claim. Override it.
DEFAULT_COHORT_PREVALENCE = {
    "healthy": 0.50,
    "hypertension": 0.30,
    "type2_diabetes": 0.15,
    "ckd_stage3": 0.05,
}


def generate_cohort(
    *,
    count: int,
    seed: int,
    prevalence: dict[str, float] | None = None,
    sex: str = "mixed",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    panels: Sequence[str] | None = None,
    include_vitals: bool = True,
) -> list[Bundle]:
    """Generate a mixed cohort, drawing each patient's profile by prevalence.

    Deterministic in the same way single bundles are: the same seed yields the same
    cohort, including which profile each patient was drawn from.
    """
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    weights = dict(prevalence or DEFAULT_COHORT_PREVALENCE)
    unknown = set(weights) - set(PROFILES)
    if unknown:
        raise ValueError(f"unknown profile(s) in prevalence: {sorted(unknown)}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("prevalence weights must sum to a positive number")

    keys = sorted(weights)
    probabilities = [weights[k] / total for k in keys]
    # A separate stream from the per-patient draws, so changing the cohort mix does
    # not shift the clinical values of patients whose profile did not change.
    chooser = np.random.default_rng([seed, stable_digest("cohort")])
    chosen = chooser.choice(len(keys), size=count, p=probabilities)

    return [
        generate_bundle(
            profile=keys[int(pick)],
            seed=seed,
            sex=("F", "M")[index % 2] if sex == "mixed" else sex,
            age_range=age_range,
            reference_date=reference_date,
            index=index,
            panels=panels,
            include_vitals=include_vitals,
        )
        for index, pick in enumerate(chosen)
    ]


def generate_bundle(
    *,
    profile: str = "type2_diabetes",
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
    panels: Sequence[str] | None = None,
    include_vitals: bool = True,
) -> Bundle:
    """Generate a transaction Bundle for one patient drawn from `profile`.

    `panels` selects which laboratory panels to emit (default: all of ALL_PANELS).
    Pass `LEAN_PANELS`, a subset, or `()` for none — the clinical draw is identical
    either way, so narrowing the output never changes the values that are emitted.
    """
    _require_sex(sex)
    _require_age_range(age_range)
    selected = ALL_PANELS if panels is None else tuple(panels)
    unknown = set(selected) - set(ALL_PANELS)
    if unknown:
        raise ValueError(
            f"unknown panel(s): {sorted(unknown)}; available: {list(ALL_PANELS)}"
        )

    rng = np.random.default_rng([seed, index])
    born, age_years = _birth_date(rng, age_range, reference_date)

    patient = build_patient(
        resource_id=deterministic_uuid(seed, "patient", index),
        sex=sex,
        birth_date=born,
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )
    practitioner = build_practitioner(
        resource_id=deterministic_uuid(seed, "practitioner", index),
        family_index=3,
        given_index=5,
    )
    drawn = generate_draw(
        profile=profile, seed=seed, sex=sex, age_years=age_years, index=index
    )

    def urn(role: str) -> str:
        return urn_uuid(seed, role, index)

    def rid(role: str) -> str:
        return deterministic_uuid(seed, role, index)

    visit = reference_date.isoformat()
    start, end = f"{visit}T09:00:00Z", f"{visit}T09:30:00Z"

    entries = [
        Entry(urn("patient"), patient),
        Entry(urn("practitioner"), practitioner),
        Entry(
            urn("encounter"),
            build_encounter(
                resource_id=rid("encounter"),
                subject_urn=urn("patient"),
                start=start,
                end=end,
                type_concept=AMBULATORY_VISIT_TYPE,
            ),
        ),
    ]

    for position, code in enumerate(drawn.conditions):
        role = f"condition-{position}"
        entries.append(
            Entry(
                urn(role),
                build_condition(
                    resource_id=rid(role),
                    code=code,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter"),
                    onset_date=(reference_date - timedelta(days=730)).isoformat(),
                ),
            )
        )

    panel_members: list[tuple[str, object, list[str]]] = []
    for panel_key, panel_code, members in LAB_PANELS:
        if panel_key not in selected:
            continue
        member_urns = []
        for analyte, code, unit in members:
            if analyte not in drawn.analytes:
                continue
            role = f"obs-{analyte}"
            member_urns.append(urn(role))
            entries.append(
                Entry(
                    urn(role),
                    build_lab_observation(
                        resource_id=rid(role),
                        code=code,
                        subject_urn=urn("patient"),
                        encounter_urn=urn("encounter"),
                        performer_urn=urn("practitioner"),
                        effective=start,
                        value=drawn.analytes[analyte],
                        unit=unit,
                    ),
                )
            )
        if member_urns:
            panel_members.append((panel_key, panel_code, member_urns))

    for analyte, code, vital_profile, unit in VITAL_ANALYTES:
        if not include_vitals or analyte not in drawn.analytes:
            continue
        role = f"obs-{analyte}"
        entries.append(
            Entry(
                urn(role),
                build_vital_observation(
                    resource_id=rid(role),
                    code=code,
                    profile=vital_profile,
                    subject_urn=urn("patient"),
                    encounter_urn=urn("encounter"),
                    performer_urn=urn("practitioner"),
                    effective=start,
                    value=drawn.analytes[analyte],
                    unit=unit,
                    additional_codes=VITAL_EXTRA_CODES.get(analyte, ()),
                ),
            )
        )

    if include_vitals:
        entries.append(
        Entry(
            urn("obs-bp"),
            build_blood_pressure(
                resource_id=rid("obs-bp"),
                subject_urn=urn("patient"),
                encounter_urn=urn("encounter"),
                performer_urn=urn("practitioner"),
                effective=start,
                systolic=drawn.analytes["systolic"],
                diastolic=drawn.analytes["diastolic"],
            ),
        )
        )

    for position, code in enumerate(drawn.allergies):
        role = f"allergy-{position}"
        entries.append(
            Entry(
                urn(role),
                build_allergy_intolerance(
                    resource_id=rid(role),
                    code=code.concept(),
                    patient_urn=urn("patient"),
                    recorded_date=visit,
                ),
            )
        )

    for position, code in enumerate(drawn.medications):
        role = f"medreq-{position}"
        entries.append(
            Entry(
                urn(role),
                build_medication_request(
                    resource_id=rid(role),
                    medication=code,
                    subject_urn=urn("patient"),
                    requester_urn=urn("practitioner"),
                    encounter_urn=urn("encounter"),
                    authored_on=visit,
                ),
            )
        )

    for panel_key, panel_code, member_urns in panel_members:
        role = f"report-{panel_key}"
        entries.append(
            Entry(
                urn(role),
                build_diagnostic_report(
                    resource_id=rid(role),
                    code=panel_code,
                    subject_urn=urn("patient"),
                    performer_urn=urn("practitioner"),
                    effective=start,
                    issued=end,
                    result_urns=member_urns,
                ),
            )
        )

    return build_transaction_bundle(entries)
