"""Condition, Observation and AllergyIntolerance builders."""

from __future__ import annotations

from decimal import Decimal

from carebundle.core import uscore
from carebundle.core.safety import htest_meta, synthetic_narrative
from carebundle.models.r4 import (
    AllergyIntolerance,
    CodeableConcept,
    Condition,
    Observation,
    ObservationComponent,
    Quantity,
    Reference,
)
from carebundle.terminology import codes
from carebundle.terminology.systems import UCUM


def _ref(urn: str) -> Reference:
    return Reference(reference=urn)


def build_condition(
    *,
    resource_id: str,
    code: codes.Code,
    subject_urn: str,
    onset_date: str,
    encounter_urn: str | None = None,
) -> Condition:
    """A US Core problem-list Condition.

    Coded with ICD-10-CM. US Core's Condition code binding is extensible and admits
    ICD-10-CM alongside SNOMED, which is what makes the no-SNOMED decision
    (build doc Section 6) survivable here.
    """
    return Condition(
        id=resource_id,
        meta=htest_meta(uscore.CONDITION_PROBLEMS),
        text=synthetic_narrative(f"Condition: {code.display} (synthetic)."),
        clinicalStatus=codes.CLINICAL_ACTIVE.concept(),
        verificationStatus=codes.VERIFICATION_CONFIRMED.concept(),
        category=[codes.CATEGORY_PROBLEM_LIST.concept()],
        code=code.concept(),
        subject=_ref(subject_urn),
        encounter=_ref(encounter_urn) if encounter_urn else None,
        onsetDateTime=onset_date,
    )


def build_lab_observation(
    *,
    resource_id: str,
    code: codes.Code,
    subject_urn: str,
    effective: str,
    value: Decimal,
    unit: tuple[str, str],
    encounter_urn: str | None = None,
    performer_urn: str | None = None,
) -> Observation:
    """A US Core laboratory result.

    `unit` is (human display, UCUM code) — they differ often enough (mmHg vs mm[Hg])
    that conflating them silently produces non-conformant output.
    """
    display_unit, ucum_code = unit
    return Observation(
        id=resource_id,
        meta=htest_meta(uscore.OBSERVATION_LAB),
        text=synthetic_narrative(f"{code.display}: {value} {display_unit} (synthetic)."),
        status="final",
        category=[codes.CATEGORY_LABORATORY.concept()],
        code=code.concept(),
        subject=_ref(subject_urn),
        encounter=_ref(encounter_urn) if encounter_urn else None,
        effectiveDateTime=effective,
        performer=[_ref(performer_urn)] if performer_urn else None,
        valueQuantity=Quantity(
            value=value, unit=display_unit, system=UCUM, code=ucum_code
        ),
    )


def build_blood_pressure(
    *,
    resource_id: str,
    subject_urn: str,
    effective: str,
    systolic: Decimal,
    diastolic: Decimal,
    encounter_urn: str | None = None,
    performer_urn: str | None = None,
) -> Observation:
    """A US Core blood pressure: one Observation with two components, never two
    independent Observations. The panel code plus components is the profile's shape."""
    display_unit, ucum_code = codes.UNIT_MMHG

    def _component(code: codes.Code, value: Decimal) -> ObservationComponent:
        return ObservationComponent(
            code=code.concept(),
            valueQuantity=Quantity(
                value=value, unit=display_unit, system=UCUM, code=ucum_code
            ),
        )

    return Observation(
        id=resource_id,
        meta=htest_meta(uscore.BLOOD_PRESSURE),
        text=synthetic_narrative(
            f"Blood pressure {systolic}/{diastolic} {display_unit} (synthetic)."
        ),
        status="final",
        category=[codes.CATEGORY_VITAL_SIGNS.concept()],
        code=codes.BP_PANEL.concept(),
        subject=_ref(subject_urn),
        encounter=_ref(encounter_urn) if encounter_urn else None,
        effectiveDateTime=effective,
        performer=[_ref(performer_urn)] if performer_urn else None,
        component=[
            _component(codes.BP_SYSTOLIC, systolic),
            _component(codes.BP_DIASTOLIC, diastolic),
        ],
    )


def build_vital_observation(
    *,
    resource_id: str,
    code: codes.Code,
    profile: str,
    subject_urn: str,
    effective: str,
    value: Decimal,
    unit: tuple[str, str],
    encounter_urn: str | None = None,
    performer_urn: str | None = None,
    additional_codes: tuple[codes.Code, ...] = (),
) -> Observation:
    """A US Core vital-sign Observation (height, weight, BMI).

    Same shape as a lab result but categorised vital-signs and asserting the specific
    US Core vitals profile, whose value[x] must be a UCUM Quantity.
    """
    display_unit, ucum_code = unit
    # Some US Core vitals profiles slice Observation.code and require more than one
    # coding — pulse oximetry needs both the method code and the base oxygensat code.
    concept = CodeableConcept(
        coding=[code.coding(), *(extra.coding() for extra in additional_codes)],
        text=code.display,
    )
    return Observation(
        id=resource_id,
        meta=htest_meta(profile),
        text=synthetic_narrative(f"{code.display}: {value} {display_unit} (synthetic)."),
        status="final",
        category=[codes.CATEGORY_VITAL_SIGNS.concept()],
        code=concept,
        subject=_ref(subject_urn),
        encounter=_ref(encounter_urn) if encounter_urn else None,
        effectiveDateTime=effective,
        performer=[_ref(performer_urn)] if performer_urn else None,
        valueQuantity=Quantity(
            value=value, unit=display_unit, system=UCUM, code=ucum_code
        ),
    )


def build_allergy_intolerance(
    *,
    resource_id: str,
    code: CodeableConcept,
    patient_urn: str,
    recorded_date: str,
) -> AllergyIntolerance:
    return AllergyIntolerance(
        id=resource_id,
        meta=htest_meta(uscore.ALLERGY_INTOLERANCE),
        text=synthetic_narrative("Allergy record (synthetic)."),
        clinicalStatus=codes.ALLERGY_ACTIVE.concept(),
        verificationStatus=codes.ALLERGY_CONFIRMED.concept(),
        code=code,
        patient=_ref(patient_urn),
        recordedDate=recorded_date,
    )
