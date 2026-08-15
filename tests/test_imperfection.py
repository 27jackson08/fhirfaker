"""Deliberately imperfect bundles (ROADMAP.md Phase 9).

The feature's value rests entirely on two guarantees, so most of this file tests those
rather than the individual corruptions: imperfection is off unless asked for, and every
injected defect is enumerable.
"""

from __future__ import annotations

import copy
import json

import pytest

from carebundle import generate_bundle
from carebundle.core.bundle import to_json
from carebundle.imperfection import DEFECT_KINDS, Defect, Imperfection, inject


@pytest.fixture
def bundle():
    return json.loads(to_json(generate_bundle(profile="type2_diabetes", seed=42)))


# --- the two guarantees -------------------------------------------------------------

def test_default_imperfection_is_a_no_op(bundle):
    """Conformance is Layer 1 of the project's claim; dirt must never be the default."""
    dirty, defects = inject(bundle, Imperfection(), seed=1)
    assert defects == ()
    assert dirty == bundle


def test_injection_never_mutates_the_input(bundle):
    before = copy.deepcopy(bundle)
    inject(bundle, Imperfection(missing_field=1.0, duplicate_entry=1.0), seed=1)
    assert bundle == before


def test_every_defect_is_reported(bundle):
    """A corruption you cannot enumerate is noise, not a fixture."""
    dirty, defects = inject(
        bundle,
        Imperfection(missing_field=1.0, duplicate_entry=1.0,
                     out_of_order_timestamp=1.0, unparseable_value=1.0,
                     unknown_code_system=1.0),
        seed=3,
    )
    assert defects, "maximum rates should produce defects"
    for defect in defects:
        assert defect.kind in DEFECT_KINDS
        assert 0 <= defect.entry_index < len(dirty["entry"])
        assert defect.detail


def test_injection_is_deterministic_under_a_seed(bundle):
    config = Imperfection(missing_field=0.4, duplicate_entry=0.2, unparseable_value=0.3)
    first, first_defects = inject(bundle, config, seed=11)
    second, second_defects = inject(bundle, config, seed=11)
    assert first == second
    assert first_defects == second_defects


def test_different_seeds_produce_different_dirt(bundle):
    config = Imperfection(missing_field=0.5, unparseable_value=0.5)
    _, a = inject(bundle, config, seed=1)
    _, b = inject(bundle, config, seed=2)
    assert a != b, "seeding must actually vary the corruption"


# --- individual defects -------------------------------------------------------------

def test_missing_field_actually_removes_the_named_field(bundle):
    dirty, defects = inject(bundle, Imperfection(missing_field=1.0), seed=5)
    for defect in defects:
        assert defect.kind == "missing_field"
        dropped = defect.detail.split("removed ")[1].strip("'")
        assert dropped not in dirty["entry"][defect.entry_index]["resource"]


def test_duplicates_are_appended_with_a_fresh_identity(bundle):
    dirty, defects = inject(bundle, Imperfection(duplicate_entry=1.0), seed=6)
    dupes = [d for d in defects if d.kind == "duplicate_entry"]
    assert dupes
    assert len(dirty["entry"]) == len(bundle["entry"]) + len(dupes)

    urls = [e.get("fullUrl") for e in dirty["entry"]]
    assert len(urls) == len(set(urls)), (
        "a byte-identical duplicate is trivially dedupable and tests nothing"
    )


def test_unparseable_value_replaces_the_quantity_not_just_its_number(bundle):
    dirty, defects = inject(bundle, Imperfection(unparseable_value=1.0), seed=7)
    for defect in (d for d in defects if d.kind == "unparseable_value"):
        resource = dirty["entry"][defect.entry_index]["resource"]
        assert "valueQuantity" not in resource
        assert isinstance(resource["valueString"], str)


def test_out_of_order_timestamp_moves_the_effective_time(bundle):
    dirty, defects = inject(bundle, Imperfection(out_of_order_timestamp=1.0), seed=8)
    for defect in (d for d in defects if d.kind == "out_of_order_timestamp"):
        resource = dirty["entry"][defect.entry_index]["resource"]
        original = bundle["entry"][defect.entry_index]["resource"]["effectiveDateTime"]
        assert resource["effectiveDateTime"] > original


def test_unknown_code_system_replaces_the_system_but_keeps_the_code(bundle):
    dirty, defects = inject(bundle, Imperfection(unknown_code_system=1.0), seed=9)
    for defect in (d for d in defects if d.kind == "unknown_code_system"):
        before = bundle["entry"][defect.entry_index]["resource"]["code"]["coding"][0]
        after = dirty["entry"][defect.entry_index]["resource"]["code"]["coding"][0]
        assert after["system"] != before["system"]
        assert after.get("code") == before.get("code")


# --- validation ---------------------------------------------------------------------

@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_rates_outside_zero_to_one_are_rejected(rate):
    with pytest.raises(ValueError, match="probability"):
        Imperfection(missing_field=rate)


def test_an_unknown_defect_kind_cannot_be_constructed():
    with pytest.raises(ValueError, match="unknown defect kind"):
        Defect(kind="not_a_kind", resource_type="Patient", entry_index=0, detail="x")


# --- the claim that makes the feature worth having ---------------------------------

@pytest.mark.conformance
def test_imperfection_off_stays_conformant_and_on_genuinely_is_not(tmp_path):
    """Both halves matter.

    Off, US Core conformance must still be provable — that is Layer 1 of the project's
    claim and imperfection must not quietly erode it. On, the output must actually
    break a validator, or the fixture is theatre: it would exercise none of the error
    paths it was generated to exercise.
    """
    from carebundle.conformance.validator import validate

    clean = json.loads(to_json(generate_bundle(profile="type2_diabetes", seed=42)))
    dirty, defects = inject(
        clean,
        Imperfection(missing_field=0.3, unparseable_value=0.2,
                     unknown_code_system=0.2, duplicate_entry=0.1),
        seed=5,
    )
    assert defects, "precondition: defects were injected"

    clean_path = tmp_path / "clean.json"
    clean_path.write_text(json.dumps(clean))
    assert not validate(clean_path).errors, "injection must not dirty the original"

    dirty_path = tmp_path / "dirty.json"
    dirty_path.write_text(json.dumps(dirty))
    assert validate(dirty_path).errors, (
        "a 'malformed' bundle the validator accepts exercises no error path"
    )
