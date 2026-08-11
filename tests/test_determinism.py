"""The determinism contract (build doc Section 9).

seed=42 must produce byte-identical output within a major version. These tests are
the enforcement mechanism, not documentation of an aspiration.
"""

from __future__ import annotations

from datetime import date

import pytest

from pkg.core.safety import (
    HTEST_CODE,
    SSN_SAFE_AREA_MAX,
    SSN_SAFE_AREA_MIN,
    synthetic_ssn,
)
from pkg.generate import generate_patient, to_json


def test_same_seed_produces_byte_identical_output():
    first = to_json(generate_patient(seed=42, sex="F"))
    second = to_json(generate_patient(seed=42, sex="F"))
    assert first == second


def test_different_seeds_produce_different_patients():
    a = to_json(generate_patient(seed=42, sex="F"))
    b = to_json(generate_patient(seed=43, sex="F"))
    assert a != b


def test_index_varies_patients_within_a_seed():
    a = to_json(generate_patient(seed=42, sex="F", index=0))
    b = to_json(generate_patient(seed=42, sex="F", index=1))
    assert a != b


def test_reference_date_is_injected_not_read_from_clock():
    """A clock read would make this test flaky by construction."""
    early = generate_patient(seed=42, sex="F", reference_date=date(2020, 1, 1))
    late = generate_patient(seed=42, sex="F", reference_date=date(2026, 1, 1))
    assert early.birthDate != late.birthDate


def test_age_falls_inside_requested_range():
    reference = date(2026, 1, 1)
    for index in range(50):
        patient = generate_patient(
            seed=7, sex="M", age_range=(45, 65), reference_date=reference, index=index
        )
        born = date.fromisoformat(patient.birthDate)
        age = (reference - born).days / 365.25
        assert 44.5 <= age <= 66.0, f"index {index} produced age {age:.1f}"


def test_every_resource_carries_the_htest_label():
    patient = generate_patient(seed=42, sex="F")
    codes = [c.code for c in patient.meta.security]
    assert HTEST_CODE in codes


def test_ssn_outside_never_issued_range_is_refused():
    with pytest.raises(ValueError, match="never-issued range"):
        synthetic_ssn(area=123, group=45, serial=6789)


@pytest.mark.parametrize("area", [SSN_SAFE_AREA_MIN, SSN_SAFE_AREA_MAX])
def test_ssn_inside_never_issued_range_is_allowed(area):
    identifier = synthetic_ssn(area=area, group=1, serial=1)
    assert identifier.value.startswith(f"{area:03d}-")


def test_invalid_sex_is_rejected():
    with pytest.raises(ValueError, match="sex must be one of"):
        generate_patient(seed=42, sex="X")
