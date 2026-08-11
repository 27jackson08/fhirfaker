"""Bundle generation.

Phase 1 wires the resource graph and proves each type is US Core-conformant. The
observation VALUES here are placeholders drawn from plausible ranges but sampled
independently — that is exactly the naive approach the build doc argues against
(Section 8). Phase 3 replaces this with the copula-based correlation engine; until
then this module makes no clinical-coherence claim.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from pkg.builders.clinical import (
    build_blood_pressure,
    build_condition,
    build_lab_observation,
)
from pkg.builders.orders import (
    build_diagnostic_report,
    build_encounter,
    build_medication_request,
)
from pkg.builders.people import build_patient, build_practitioner
from pkg.core.bundle import Entry, build_transaction_bundle, to_json  # noqa: F401
from pkg.core.ids import deterministic_uuid, urn_uuid
from pkg.models.r4 import Bundle, CodeableConcept
from pkg.terminology import codes

# Injected rather than read from the clock: any datetime.now() call would destroy the
# determinism contract (build doc Section 9).
DEFAULT_REFERENCE_DATE = date(2026, 1, 1)

# US Core's Encounter.type value set draws on CPT-4 (AMA-licensed) and SNOMED CT
# (affiliate-licensed). Neither can ship here, so we assert text only and let the
# extensible binding degrade to a warning rather than embed an unlicensed code.
AMBULATORY_VISIT_TYPE = CodeableConcept(text="Ambulatory visit")


def generate_patient(
    *,
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
):
    """Generate a single US Core Patient (no clinical history)."""
    rng = np.random.default_rng([seed, index])
    low, high = age_range
    age = int(rng.integers(low, high + 1))
    day_offset = int(rng.integers(0, 365))
    birth_date = reference_date - timedelta(days=age * 365 + day_offset)

    return build_patient(
        resource_id=deterministic_uuid(seed, "patient", index),
        sex=sex,
        birth_date=birth_date,
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )


def generate_bundle(
    *,
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
) -> Bundle:
    """Generate a transaction Bundle for one patient with a type 2 diabetes history."""
    patient = generate_patient(
        seed=seed, sex=sex, age_range=age_range, reference_date=reference_date, index=index
    )
    practitioner = build_practitioner(
        resource_id=deterministic_uuid(seed, "practitioner", index),
        family_index=3,
        given_index=5,
    )

    urn = {
        role: urn_uuid(seed, role, index)
        for role in (
            "patient", "practitioner", "encounter", "condition-t2dm",
            "obs-hba1c", "obs-glucose", "obs-bp", "medreq-metformin", "report-lab",
        )
    }

    visit = reference_date.isoformat()
    visit_start = f"{visit}T09:00:00Z"
    visit_end = f"{visit}T09:30:00Z"

    encounter = build_encounter(
        resource_id=deterministic_uuid(seed, "encounter", index),
        subject_urn=urn["patient"],
        start=visit_start,
        end=visit_end,
        type_concept=AMBULATORY_VISIT_TYPE,
    )
    condition = build_condition(
        resource_id=deterministic_uuid(seed, "condition-t2dm", index),
        code=codes.T2DM_NO_COMPLICATIONS,
        subject_urn=urn["patient"],
        encounter_urn=urn["encounter"],
        onset_date=(reference_date - timedelta(days=730)).isoformat(),
    )

    # Placeholder values — see the module docstring. Not yet jointly sampled.
    hba1c = build_lab_observation(
        resource_id=deterministic_uuid(seed, "obs-hba1c", index),
        code=codes.HBA1C,
        subject_urn=urn["patient"],
        encounter_urn=urn["encounter"],
        performer_urn=urn["practitioner"],
        effective=visit_start,
        value=Decimal("7.8"),
        unit=codes.UNIT_PERCENT,
    )
    glucose = build_lab_observation(
        resource_id=deterministic_uuid(seed, "obs-glucose", index),
        code=codes.GLUCOSE_FASTING,
        subject_urn=urn["patient"],
        encounter_urn=urn["encounter"],
        performer_urn=urn["practitioner"],
        effective=visit_start,
        value=Decimal(152),
        unit=codes.UNIT_MG_DL,
    )
    blood_pressure = build_blood_pressure(
        resource_id=deterministic_uuid(seed, "obs-bp", index),
        subject_urn=urn["patient"],
        encounter_urn=urn["encounter"],
        performer_urn=urn["practitioner"],
        effective=visit_start,
        systolic=Decimal(138),
        diastolic=Decimal(84),
    )
    medication = build_medication_request(
        resource_id=deterministic_uuid(seed, "medreq-metformin", index),
        medication=codes.METFORMIN_500,
        subject_urn=urn["patient"],
        requester_urn=urn["practitioner"],
        encounter_urn=urn["encounter"],
        authored_on=visit,
    )
    report = build_diagnostic_report(
        resource_id=deterministic_uuid(seed, "report-lab", index),
        subject_urn=urn["patient"],
        performer_urn=urn["practitioner"],
        effective=visit_start,
        issued=visit_end,
        result_urns=[urn["obs-hba1c"], urn["obs-glucose"]],
    )

    return build_transaction_bundle(
        [
            Entry(urn["patient"], patient),
            Entry(urn["practitioner"], practitioner),
            Entry(urn["encounter"], encounter),
            Entry(urn["condition-t2dm"], condition),
            Entry(urn["obs-hba1c"], hba1c),
            Entry(urn["obs-glucose"], glucose),
            Entry(urn["obs-bp"], blood_pressure),
            Entry(urn["medreq-metformin"], medication),
            Entry(urn["report-lab"], report),
        ]
    )
