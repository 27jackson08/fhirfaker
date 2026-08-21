"""FHIR Bulk Data (ndjson) output.

A transaction Bundle and a bulk export differ in exactly the ways that break importers:
identity and reference form. A converter that only strips the Bundle wrapper produces
resources with no `id` and dangling `urn:uuid:` references — parseable, and useless for
exercising the thing under test. These tests are mostly about that conversion.
"""

from __future__ import annotations

import json

import pytest

from carebundle import generate_bundle, to_ndjson
from carebundle.generate import generate_cohort


@pytest.fixture(scope="module")
def export() -> dict[str, str]:
    """A cohort export, which is the realistic shape — a population, not one patient."""
    return to_ndjson(generate_cohort(count=12, seed=42))


def _resources(export: dict[str, str]) -> list[dict]:
    return [json.loads(line) for text in export.values() for line in text.splitlines()]


# --- the conversion ------------------------------------------------------------------

def test_every_line_is_a_complete_json_resource(export):
    for resource_type, text in export.items():
        for line in text.splitlines():
            parsed = json.loads(line)
            assert parsed["resourceType"] == resource_type, (
                "each file must contain only its own resource type"
            )


def test_every_resource_carries_an_id(export):
    """A bulk export is a snapshot of resources that exist; the Bundle form drops ids."""
    for resource in _resources(export):
        assert resource.get("id"), f"{resource['resourceType']} exported without an id"


def test_no_reference_is_left_as_a_urn(export):
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "reference" and isinstance(value, str):
                    assert not value.startswith("urn:uuid:"), (
                        f"unrewritten bundle-local reference: {value}"
                    )
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for resource in _resources(export):
        walk(resource)


def test_every_reference_resolves_within_the_export(export):
    """The property that makes the output usable: no dangling `ResourceType/id`.

    Checked across the whole export rather than per bundle, because that is how an
    importer sees it — the files arrive together and references cross between them.
    """
    resources = _resources(export)
    present = {f"{r['resourceType']}/{r['id']}" for r in resources}

    referenced: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "reference" and isinstance(value, str):
                    referenced.add(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for resource in resources:
        walk(resource)

    assert referenced, "precondition: the export should contain references at all"
    assert not (referenced - present), f"dangling: {sorted(referenced - present)}"


def test_identifier_systems_keep_their_urn_form(export):
    """`identifier.system` is deliberately `urn:uuid:` and must not be rewritten.

    The validator rejects `example.org` there, so a urn was chosen on purpose (build doc
    Section 18). Only `reference` values are bundle-local pointers.
    """
    systems = [
        identifier.get("system")
        for resource in _resources(export)
        for identifier in resource.get("identifier", [])
    ]
    assert any(s and s.startswith("urn:uuid:") for s in systems), (
        "identifier systems were rewritten along with the references"
    )


def test_ids_match_the_bundle_form_for_the_same_seed():
    """Same seed, both formats, comparable ids — so the two outputs can be diffed."""
    bundle = json.loads(
        __import__("carebundle").to_json(generate_bundle(profile="healthy", seed=42))
    )
    export = to_ndjson(generate_bundle(profile="healthy", seed=42))
    patient_urn = next(
        e["fullUrl"] for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Patient"
    )
    exported = json.loads(export["Patient"].splitlines()[0])
    assert patient_urn.endswith(exported["id"])


def test_a_single_bundle_is_accepted_as_well_as_an_iterable():
    single = to_ndjson(generate_bundle(profile="healthy", seed=1))
    assert "Patient" in single and single["Patient"].endswith("\n")


def test_output_is_deterministic():
    assert to_ndjson(generate_cohort(count=5, seed=9)) == to_ndjson(
        generate_cohort(count=5, seed=9)
    )


# --- the CLI -------------------------------------------------------------------------

def test_cli_writes_one_file_per_resource_type(tmp_path, capsys):
    from carebundle.cli import main

    assert main(["generate", "--profile", "healthy", "--count", "3", "--seed", "5",
                 "--out", str(tmp_path), "--format", "ndjson"]) == 0
    capsys.readouterr()
    written = sorted(p.name for p in tmp_path.glob("*.ndjson"))
    assert "Patient.ndjson" in written
    assert len(json.loads((tmp_path / "Patient.ndjson").read_text().splitlines()[0])["id"]) > 0


def test_cli_refuses_ndjson_without_an_output_directory(capsys):
    """A bulk export is a set of files; there is no single-document form for stdout."""
    from carebundle.cli import main

    assert main(["generate", "--profile", "healthy", "--seed", "1",
                 "--format", "ndjson"]) == 2
    assert "needs --out" in capsys.readouterr().err
