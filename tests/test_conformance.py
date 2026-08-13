"""US Core conformance — the authoritative quality gate (build doc Section 10).

These tests shell out to the official HL7 validator and need a JVM. That JVM is a
dev/CI dependency only; it is never required to install or run the library.
"""

from __future__ import annotations

import pytest

from pkg.conformance.validator import validate
from pkg.generate import generate_bundle, generate_patient, to_json

pytestmark = pytest.mark.conformance

# Warnings we have examined and accept. Each needs a reason, so that "we ignore
# warnings" never becomes the default. See CONFORMANCE.md.
ACCEPTED_WARNING_FRAGMENTS = (
    # US Core Encounter.type draws on CPT-4 and SNOMED CT; neither is shippable.
    "US Core Encounter Type",
    # The validator ships a different RxNorm version than the value set binding names.
    "could not be found, so the code cannot be validated",
    # VSAC snapshot from 2017; RXCUI 861007 is current prescribable content.
    "Medication Clinical Drug",
    # Generic best-practice advice fired by ANY annotated UCUM code.
    # mL/min/{1.73_m2} is the standard representation for eGFR.
    "UCUM Codes that contain human readable annotations",
)


def unexpected_warnings(result):
    return [
        w for w in result.warnings
        if not any(f in w.message for f in ACCEPTED_WARNING_FRAGMENTS)
    ]


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


def test_full_bundle_is_us_core_conformant(written, conformance_seeds):
    """Every resource type in the graph, validated together against its profile."""
    failures = []
    for seed in conformance_seeds:
        path = written(generate_bundle(seed=seed, sex="F"), f"bundle-{seed}")
        result = validate(path)
        if not result.ok:
            failures.append(
                f"seed {seed}: "
                + "; ".join(f"{i.location} :: {i.message}" for i in result.errors)
            )
    assert not failures, "US Core conformance errors:\n" + "\n".join(failures)


@pytest.mark.parametrize(
    "profile", ["healthy", "hypertension", "type2_diabetes", "ckd_stage3"]
)
def test_every_clinical_profile_is_conformant(written, profile):
    """Each profile emits a different resource mix, so each needs its own gate."""
    path = written(generate_bundle(profile=profile, seed=42, sex="F"), f"bundle-{profile}")
    result = validate(path)
    assert result.ok, f"{profile}:\n" + "\n".join(
        f"  {i.location} :: {i.message}" for i in result.errors
    )


def test_bundle_raises_no_unexamined_warnings(written):
    """Guards against warning drift: a NEW warning should surface, not blend in."""
    path = written(generate_bundle(seed=42, sex="F"), "bundle-warnings")
    unexpected = unexpected_warnings(validate(path))
    assert not unexpected, "unexamined warnings:\n" + "\n".join(
        f"{w.location} :: {w.message}" for w in unexpected
    )
