"""Patient generation — Phase 0 walking skeleton.

This is deliberately thin. The clinical profile system and correlation engine
(build doc Sections 7-8) land in Phase 3; what this proves is the pipeline:
seeded input -> generated model -> US Core-conformant FHIR JSON.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from pkg.core.ids import deterministic_uuid
from pkg.core.safety import (
    US_CORE_PATIENT_PROFILE,
    fictional_name,
    htest_meta,
    synthetic_mrn,
    synthetic_narrative,
)
from pkg.models.r4 import Patient

# Injected rather than read from the clock: any datetime.now() call would destroy the
# determinism contract (build doc Section 9).
DEFAULT_REFERENCE_DATE = date(2026, 1, 1)

SEX_TO_FHIR_GENDER = {"F": "female", "M": "male"}


def generate_patient(
    *,
    seed: int,
    sex: str = "F",
    age_range: tuple[int, int] = (45, 65),
    reference_date: date = DEFAULT_REFERENCE_DATE,
    index: int = 0,
) -> Patient:
    """Generate one US Core-conformant Patient.

    Deterministic: the same (seed, sex, age_range, reference_date, index) always
    produces byte-identical output.
    """
    if sex not in SEX_TO_FHIR_GENDER:
        raise ValueError(f"sex must be one of {sorted(SEX_TO_FHIR_GENDER)}, got {sex!r}")

    rng = np.random.default_rng([seed, index])

    low, high = age_range
    age = int(rng.integers(low, high + 1))
    # Offset within the year so birth dates are not all January 1st.
    day_offset = int(rng.integers(0, 365))
    birth_date = reference_date - timedelta(days=age * 365 + day_offset)

    patient_id = deterministic_uuid(seed, "patient", index)
    name = fictional_name(
        family_index=int(rng.integers(0, 10)),
        given_index=int(rng.integers(0, 10)),
    )
    gender = SEX_TO_FHIR_GENDER[sex]

    return Patient(
        id=patient_id,
        meta=htest_meta(US_CORE_PATIENT_PROFILE),
        text=synthetic_narrative(
            f"{name.given[0]} {name.family}, {gender}, born {birth_date.isoformat()}."
        ),
        identifier=[synthetic_mrn(patient_id[:8].upper())],
        name=[name],
        gender=gender,
        birthDate=birth_date.isoformat(),
    )


def to_json(resource, *, indent: int = 2) -> str:
    """Serialize to FHIR JSON. exclude_none is what keeps absent elements absent."""
    import json

    payload = resource.model_dump(mode="json", exclude_none=True, by_alias=True)
    return json.dumps(payload, indent=indent, sort_keys=False)
