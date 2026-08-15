"""Encounter, MedicationRequest and DiagnosticReport builders."""

from __future__ import annotations

from carebundle.core import uscore
from carebundle.core.safety import htest_meta, synthetic_narrative
from carebundle.models.r4 import (
    DiagnosticReport,
    Encounter,
    MedicationRequest,
    Period,
    Reference,
)
from carebundle.terminology import codes


def _ref(urn: str) -> Reference:
    return Reference(reference=urn)


def build_encounter(
    *,
    resource_id: str,
    subject_urn: str,
    start: str,
    end: str,
    type_concept,
) -> Encounter:
    """A US Core ambulatory Encounter.

    `type_concept` is injected because US Core's Encounter.type value set draws on
    CPT-4 and SNOMED CT — neither of which this project can ship (build doc Section 6).
    Making it a caller-supplied argument keeps that constraint visible instead of
    burying an unlicensed code in the library.
    """
    return Encounter(
        id=resource_id,
        meta=htest_meta(uscore.ENCOUNTER),
        text=synthetic_narrative("Ambulatory encounter (synthetic)."),
        status="finished",
        class_=codes.ENCOUNTER_AMBULATORY.coding(),
        type=[type_concept],
        subject=_ref(subject_urn),
        period=Period(start=start, end=end),
    )


def build_medication_request(
    *,
    resource_id: str,
    medication: codes.Code,
    subject_urn: str,
    requester_urn: str,
    authored_on: str,
    encounter_urn: str | None = None,
) -> MedicationRequest:
    """A US Core MedicationRequest.

    `requester_urn` is mandatory rather than optional: US Core requires a requester,
    so allowing it to default to None would let non-conformant output be constructed.
    """
    return MedicationRequest(
        id=resource_id,
        meta=htest_meta(uscore.MEDICATION_REQUEST),
        text=synthetic_narrative(f"Prescription: {medication.display} (synthetic)."),
        status="active",
        intent="order",
        medicationCodeableConcept=medication.concept(),
        subject=_ref(subject_urn),
        encounter=_ref(encounter_urn) if encounter_urn else None,
        authoredOn=authored_on,
        requester=_ref(requester_urn),
    )


def build_diagnostic_report(
    *,
    resource_id: str,
    code: codes.Code,
    subject_urn: str,
    effective: str,
    issued: str,
    result_urns: list[str],
    performer_urn: str | None = None,
) -> DiagnosticReport:
    """A US Core laboratory DiagnosticReport tying together its member Observations.

    `code` is the panel's own LOINC code. The generic "Laboratory report" document
    code (11502-2) is excluded from US Core's lab test value set for good reason —
    it describes the document, not what was measured.
    """
    return DiagnosticReport(
        id=resource_id,
        meta=htest_meta(uscore.DIAGNOSTIC_REPORT_LAB),
        text=synthetic_narrative("Laboratory report (synthetic)."),
        status="final",
        category=[codes.SERVICE_SECTION_LAB.concept()],
        code=code.concept(),
        subject=_ref(subject_urn),
        effectiveDateTime=effective,
        issued=issued,
        performer=[_ref(performer_urn)] if performer_urn else None,
        result=[_ref(urn) for urn in result_urns],
    )
