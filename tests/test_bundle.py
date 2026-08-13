"""Bundle assembly, reference integrity and FHIR JSON serialization."""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from pkg.core.bundle import URN_UUID_RE, dangling_references, to_json
from pkg.core.safety import HTEST_CODE
from pkg.generate import generate_bundle

PROFILES = ("healthy", "hypertension", "type2_diabetes", "ckd_stage3")

# Present in every bundle regardless of profile. Conditions and MedicationRequests
# are profile-dependent, so asserting an exact entry list would just encode today's
# draw rather than an invariant.
ALWAYS_PRESENT = {"Patient", "Practitioner", "Encounter", "Observation", "DiagnosticReport"}


@pytest.fixture(scope="module")
def bundle():
    return generate_bundle(seed=42, sex="F")


@pytest.fixture(scope="module")
def payload(bundle):
    return json.loads(to_json(bundle))


def test_bundle_contains_the_core_resource_types(payload):
    present = {e["resource"]["resourceType"] for e in payload["entry"]}
    assert ALWAYS_PRESENT <= present


# Chronic disease codes. "Healthy baseline" means free of these — it does not mean
# free of every finding: a typical adult population carries incidental raised LDL and
# obesity at real rates, and suppressing those would make the data less realistic, not
# more. Coding them is the coherence rule working (see profiles.library).
CHRONIC_DISEASE_PREFIXES = ("E11", "I10", "N18", "I50", "I25")


def _condition_codes(payload) -> list[str]:
    return [
        coding["code"]
        for entry in payload["entry"]
        if entry["resource"]["resourceType"] == "Condition"
        for coding in entry["resource"]["code"]["coding"]
    ]


@pytest.mark.parametrize("seed", range(12))
def test_healthy_profile_never_carries_a_chronic_disease_diagnosis(seed):
    payload = json.loads(to_json(generate_bundle(profile="healthy", seed=seed)))
    for code in _condition_codes(payload):
        assert not code.startswith(CHRONIC_DISEASE_PREFIXES), (
            f"seed {seed}: healthy baseline emitted chronic disease code {code}"
        )


@pytest.mark.parametrize("seed", range(12))
def test_healthy_profile_prescribes_nothing(seed):
    payload = json.loads(to_json(generate_bundle(profile="healthy", seed=seed)))
    types = [e["resource"]["resourceType"] for e in payload["entry"]]
    assert "MedicationRequest" not in types


@pytest.mark.parametrize("seed", range(12))
def test_diabetes_code_never_contradicts_the_generated_egfr(seed):
    """E11.9 'without complications' beside an eGFR of 45 is a contradiction."""
    from pkg.generate import generate_draw

    drawn = generate_draw(profile="type2_diabetes", seed=seed, sex="F", age_years=58.0)
    emitted = {c.code for c in drawn.conditions}
    if drawn.raw["egfr"] < 60.0:
        assert "E11.22" in emitted, f"seed {seed}: eGFR {drawn.raw['egfr']:.0f} needs E11.22"
        assert "E11.9" not in emitted
    else:
        assert "E11.22" not in emitted


@pytest.mark.parametrize("seed", range(12))
def test_lipid_panel_is_internally_consistent(seed):
    """LDL is calculated from the panel, so the four numbers cannot disagree."""
    from pkg.correlation.relations import friedewald_ldl
    from pkg.generate import generate_draw

    drawn = generate_draw(profile="type2_diabetes", seed=seed, sex="M", age_years=58.0)
    expected = friedewald_ldl(
        total_cholesterol=drawn.raw["cholesterol_total"],
        hdl=drawn.raw["hdl"],
        triglycerides=drawn.raw["triglycerides"],
    )
    assert drawn.raw["ldl"] == pytest.approx(expected, abs=1e-9)


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


def test_decimal_precision_matches_laboratory_reporting(bundle):
    """Each analyte keeps the precision a lab would actually report.

    Significant figures are an assertion in FHIR: emitting 95.0 where the lab reports
    95 claims a precision the measurement does not have, and float round-tripping
    introduces exactly that drift.
    """
    text = to_json(bundle)
    payload = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    by_code = {}
    for entry in payload["entry"]:
        resource = entry["resource"]
        if resource["resourceType"] == "Observation" and "valueQuantity" in resource:
            by_code[resource["code"]["coding"][0]["code"]] = resource["valueQuantity"]["value"]

    expected_decimal_places = {
        "4548-4": 1,   # HbA1c, reported to 0.1 %
        "2345-7": 0,   # glucose, reported as whole mg/dL
        "2160-0": 2,   # creatinine, reported to 0.01 mg/dL
        "98979-8": 0,  # eGFR, reported as a whole number
    }
    # The exponent check is the real assertion, and it is two-sided: a value rendered
    # as 95.0 has exponent -1 and fails a 0-place analyte, while 95 fails a 1-place
    # one. Both directions matter.
    #
    # A blanket `"value": \d+\.0` search looks like it says the same thing and does
    # not — an HbA1c of exactly 8.0 is *correctly* rendered "8.0", because 0.1 is the
    # precision a laboratory reports it to. Dropping the trailing zero there would
    # discard a significant figure.
    for code, places in expected_decimal_places.items():
        value = by_code[code]
        assert -value.as_tuple().exponent == places, f"{code} -> {value}"


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


@pytest.mark.parametrize("profile", PROFILES)
def test_every_profile_produces_a_referentially_intact_bundle(profile):
    built = generate_bundle(profile=profile, seed=42, sex="F")
    assert dangling_references(built) == set()
    assert json.loads(to_json(built))["entry"]


def test_profiles_do_not_collide_at_the_same_seed():
    """Two profiles sharing a marginal must not draw identical values.

    They did until the profile key entered the RNG seed: `healthy` and
    `hypertension` share the normoglycaemic marginals and emitted the same HbA1c,
    glucose and creatinine for a given seed.
    """
    rendered = {p: to_json(generate_bundle(profile=p, seed=42)) for p in PROFILES}
    assert len(set(rendered.values())) == len(PROFILES)


def test_output_does_not_depend_on_python_hash_randomization():
    """`hash()` is salted per process; anything seeded from it breaks determinism."""
    from pkg.core.ids import stable_digest

    assert stable_digest("type2_diabetes") == stable_digest("type2_diabetes")
    assert stable_digest("healthy") != stable_digest("hypertension")


def test_ckd_condition_code_agrees_with_the_generated_egfr():
    """The coded diagnosis and the lab value must not contradict each other."""
    from pkg.correlation.relations import ckd_stage_for
    from pkg.generate import generate_draw

    for seed in range(20):
        drawn = generate_draw(profile="ckd_stage3", seed=seed, sex="M", age_years=58.0)
        expected = {"G3a": "N18.31", "G3b": "N18.32"}[ckd_stage_for(drawn.raw["egfr"])]
        assert any(c.code == expected for c in drawn.conditions), (
            f"seed {seed}: eGFR {drawn.raw['egfr']:.1f} should code {expected}"
        )
