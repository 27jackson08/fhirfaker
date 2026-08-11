"""US Core conformance — the authoritative quality gate (build doc Section 10).

These tests shell out to the official HL7 validator and need a JVM. That JVM is a
dev/CI dependency only; it is never required to install or run the library.
"""

from __future__ import annotations

import pytest

from pkg.conformance.validator import validate
from pkg.generate import generate_patient, to_json

pytestmark = pytest.mark.conformance


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """Write generated resources to disk once, then validate them."""
    directory = tmp_path_factory.mktemp("conformance")

    def _write(resource, name: str):
        path = directory / f"{name}.json"
        path.write_text(to_json(resource))
        return path

    return _write


def test_patient_is_us_core_conformant(written, conformance_seeds):
    failures = []
    for seed in conformance_seeds:
        path = written(generate_patient(seed=seed, sex="F"), f"patient-{seed}")
        result = validate(path)
        if not result.ok:
            failures.append(
                f"seed {seed}: "
                + "; ".join(f"{i.location} :: {i.message}" for i in result.errors)
            )
    assert not failures, "US Core conformance errors:\n" + "\n".join(failures)


def test_both_sexes_are_conformant(written):
    for sex in ("F", "M"):
        path = written(generate_patient(seed=42, sex=sex), f"patient-{sex}")
        result = validate(path)
        assert result.ok, "\n".join(
            f"{i.location} :: {i.message}" for i in result.errors
        )
