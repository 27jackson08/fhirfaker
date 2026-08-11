"""Bundle assembly, reference integrity and FHIR JSON serialization."""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from pkg.core.bundle import URN_UUID_RE, dangling_references, to_json
from pkg.core.safety import HTEST_CODE
from pkg.generate import generate_bundle

EXPECTED_TYPES = [
    "Patient", "Practitioner", "Encounter", "Condition",
    "Observation", "Observation", "Observation",
    "MedicationRequest", "DiagnosticReport",
]


@pytest.fixture(scope="module")
def bundle():
    return generate_bundle(seed=42, sex="F")


@pytest.fixture(scope="module")
def payload(bundle):
    return json.loads(to_json(bundle))


def test_bundle_contains_expected_resource_types(payload):
    assert [e["resource"]["resourceType"] for e in payload["entry"]] == EXPECTED_TYPES


def test_no_dangling_references(bundle):
    assert dangling_references(bundle) == set()


def test_every_full_url_is_a_urn_uuid(payload):
    for entry in payload["entry"]:
        assert URN_UUID_RE.match(entry["fullUrl"]), entry["fullUrl"]


def test_full_urls_are_unique(payload):
    urls = [e["fullUrl"] for e in payload["entry"]]
    assert len(urls) == len(set(urls))


def test_transaction_entries_carry_a_request(payload):
    assert payload["type"] == "transaction"
    for entry in payload["entry"]:
        assert entry["request"]["method"] == "POST"
        assert entry["request"]["url"] == entry["resource"]["resourceType"]


def test_bundled_resources_drop_their_id(payload):
    """In a transaction the server assigns identity; fullUrl is the reference target."""
    for entry in payload["entry"]:
        assert "id" not in entry["resource"]


def test_every_resource_carries_the_htest_label(payload):
    for entry in payload["entry"]:
        codes = [c["code"] for c in entry["resource"]["meta"]["security"]]
        assert HTEST_CODE in codes, entry["resource"]["resourceType"]


def test_every_resource_asserts_a_us_core_profile(payload):
    for entry in payload["entry"]:
        profiles = entry["resource"]["meta"]["profile"]
        assert any("us-core" in p for p in profiles), entry["resource"]["resourceType"]


# --- decimal serialization -------------------------------------------------------
# FHIR requires `decimal` to be a JSON number. Serializing it as a string produced
# four validator errors ("the primitive value must be a number"); these tests stop
# that from regressing.

def test_quantity_values_serialize_as_json_numbers(bundle):
    text = to_json(bundle)
    quoted = re.findall(r'"value": "(\d+\.?\d*)"', text)
    assert not quoted, f"numeric values serialized as strings: {quoted}"


def test_decimal_precision_is_preserved_exactly(bundle):
    payload = json.loads(to_json(bundle), parse_float=Decimal, parse_int=Decimal)
    observations = [
        e["resource"] for e in payload["entry"]
        if e["resource"]["resourceType"] == "Observation"
    ]
    values = [o["valueQuantity"]["value"] for o in observations if "valueQuantity" in o]
    assert Decimal("7.8") in values
    # 152, not 152.0 — trailing-zero drift would change the significant figures.
    assert Decimal(152) in values
    assert "152.0" not in to_json(bundle)


def test_sentinel_never_leaks_into_output(bundle):
    assert "@@FHIRDEC@@" not in to_json(bundle)


def test_unserializable_type_raises_rather_than_silently_dropping():
    from pkg.core.bundle import _mark_decimals

    with pytest.raises(TypeError, match="cannot serialize"):
        _mark_decimals(object())


# --- determinism of the whole graph ----------------------------------------------

def test_bundle_is_byte_identical_across_runs():
    assert to_json(generate_bundle(seed=42)) == to_json(generate_bundle(seed=42))


def test_different_seeds_produce_different_bundles():
    assert to_json(generate_bundle(seed=42)) != to_json(generate_bundle(seed=43))
