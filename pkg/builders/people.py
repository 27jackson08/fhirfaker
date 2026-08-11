"""Patient and Practitioner builders."""

from __future__ import annotations

from datetime import date

from pkg.core import uscore
from pkg.core.safety import (
    fictional_name,
    htest_meta,
    synthetic_mrn,
    synthetic_narrative,
    synthetic_npi,
)
from pkg.models.r4 import Patient, Practitioner

SEX_TO_FHIR_GENDER = {"F": "female", "M": "male"}


def build_patient(
    *,
    resource_id: str,
    sex: str,
    birth_date: date,
    family_index: int,
    given_index: int,
) -> Patient:
    """A US Core Patient. Callers supply every varying input, keeping this pure."""
    if sex not in SEX_TO_FHIR_GENDER:
        raise ValueError(f"sex must be one of {sorted(SEX_TO_FHIR_GENDER)}, got {sex!r}")

    name = fictional_name(family_index=family_index, given_index=given_index)
    gender = SEX_TO_FHIR_GENDER[sex]

    return Patient(
        id=resource_id,
        meta=htest_meta(uscore.PATIENT),
        text=synthetic_narrative(
            f"{name.given[0]} {name.family}, {gender}, born {birth_date.isoformat()}."
        ),
        identifier=[synthetic_mrn(resource_id[:8].upper())],
        name=[name],
        gender=gender,
        birthDate=birth_date.isoformat(),
    )


def build_practitioner(
    *, resource_id: str, family_index: int, given_index: int
) -> Practitioner:
    """A US Core Practitioner.

    Exists because US Core requires MedicationRequest.requester — see the Phase 1
    notes in the build doc. Identifiers use the synthetic urn:uuid system rather than
    the real NPI namespace: a checksum-valid NPI could collide with a real clinician.
    """
    name = fictional_name(family_index=family_index, given_index=given_index)
    return Practitioner(
        id=resource_id,
        meta=htest_meta(uscore.PRACTITIONER),
        text=synthetic_narrative(f"Dr {name.given[0]} {name.family} (synthetic)."),
        identifier=[synthetic_npi(resource_id[:10].upper())],
        name=[name],
    )
