"""Terminology table consistency.

These run offline. The network check that every code and display matches its source
vocabulary lives in `carebundle/terminology/verify.py` and runs nightly, because a unit test
that needs three external APIs is a flaky test.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from carebundle.terminology import systems
from carebundle.terminology.codes import Code
from carebundle.terminology.verify import registered_codes

# Target subset sizes from build doc Section 6. Full coverage is a maintenance burden
# with no v1 payoff; too few codes makes the profiles repetitive.
TARGET_SIZES = {
    systems.LOINC: (30, 50),
    systems.RXNORM: (20, 30),
    systems.ICD10CM: (15, 25),
}

LOINC_PATTERN = re.compile(r"^\d{1,5}-\d$")
ICD10CM_PATTERN = re.compile(r"^[A-TV-Z]\d{2}(\.\d{1,4})?$")
RXCUI_PATTERN = re.compile(r"^\d+$")


@pytest.fixture(scope="module")
def codes() -> tuple[Code, ...]:
    return registered_codes()


def test_no_code_is_registered_twice_with_different_displays(codes):
    seen: dict[tuple[str, str], str] = {}
    for code in codes:
        key = (code.system, code.code)
        if key in seen:
            assert seen[key] == code.display, f"{key} has conflicting displays"
        seen[key] = code.display


def test_every_code_has_a_display(codes):
    for code in codes:
        assert code.display.strip(), f"{code.system}#{code.code} has an empty display"


def test_displays_are_not_truncated_or_placeholder(codes):
    for code in codes:
        assert not code.display.endswith("..."), f"{code.code} display looks truncated"
        assert "TODO" not in code.display.upper()


@pytest.mark.parametrize(
    "system,pattern",
    [
        (systems.LOINC, LOINC_PATTERN),
        (systems.ICD10CM, ICD10CM_PATTERN),
        (systems.RXNORM, RXCUI_PATTERN),
    ],
)
def test_codes_are_well_formed_for_their_system(codes, system, pattern):
    for code in codes:
        if code.system == system:
            assert pattern.match(code.code), f"{code.code} is malformed for {system}"


@pytest.mark.parametrize("system,bounds", TARGET_SIZES.items())
def test_subset_sizes_match_the_curation_target(codes, system, bounds):
    low, high = bounds
    count = sum(1 for c in codes if c.system == system)
    assert low <= count <= high, f"{system} has {count} codes, target {low}-{high}"


def test_no_snomed_codes_are_shipped(codes):
    """SNOMED CT is excluded by design — redistribution needs an affiliate licence."""
    assert not [c for c in codes if c.system == systems.SNOMED]
    assert not [c for c in codes if "snomed" in c.system.lower()]


def test_every_code_uses_a_known_system(codes):
    known = {
        value for name, value in vars(systems).items()
        if not name.startswith("_") and isinstance(value, str)
    }
    for code in codes:
        assert code.system in known, f"{code.code} uses unregistered system {code.system}"


def test_codeable_concept_round_trips(codes):
    for code in codes:
        concept = code.concept()
        assert concept.coding[0].code == code.code
        assert concept.coding[0].system == code.system
        assert concept.text == code.display


def test_display_text_can_be_overridden():
    code = Code(systems.LOINC, "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood")
    assert code.concept("HbA1c").text == "HbA1c"


def test_ckd_stage_codes_cover_every_kdigo_band():
    """A missing stage code would silently fall back to the unspecified one."""
    from carebundle.terminology import codes as table

    for expected in ("N18.1", "N18.2", "N18.30", "N18.31", "N18.32", "N18.4", "N18.5"):
        assert any(c.code == expected for c in registered_codes()), expected
    assert table.CKD_STAGE_3A.code == "N18.31"
    assert table.CKD_STAGE_3B.code == "N18.32"


def test_metformin_constants_do_not_mix_release_profiles():
    """861007 is immediate-release; 860975 is 24 HR extended-release."""
    from carebundle.terminology import codes as table

    assert table.METFORMIN_500.code == "861007"
    assert "Extended Release" not in table.METFORMIN_500.display
    assert "860975" not in {c.code for c in registered_codes()}


def test_units_pair_a_display_with_a_ucum_code():
    from carebundle.terminology import codes as table

    units = [
        value for name, value in vars(table).items()
        if name.startswith("UNIT_") and isinstance(value, tuple)
    ]
    assert units
    for display, ucum in units:
        assert display and ucum


def test_registered_codes_is_deduplicated(codes):
    counts = Counter((c.system, c.code) for c in codes)
    assert not [key for key, n in counts.items() if n > 1]


def test_every_defined_code_is_either_emitted_or_explicitly_reserved():
    """Terminology dead by accident is a defect; dead on purpose needs a reason.

    Expanding the subset to hit a target size once left 55 of 101 codes defined and
    never emitted — verified against their source vocabularies, documented, and
    completely unused. This is the guard that stops that recurring.
    """
    import subprocess
    from pathlib import Path

    from carebundle.terminology import codes as table

    package = Path(__file__).resolve().parents[1] / "carebundle"
    defined = {
        name for name, value in vars(table).items() if isinstance(value, Code)
    }
    source = subprocess.run(
        ["grep", "-rho", "codes[.][A-Z_0-9]*", str(package), "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    referenced = {token.split(".", 1)[1] for token in source.split()}

    unaccounted = sorted(defined - referenced - set(table.RESERVED_CODES))
    assert not unaccounted, (
        "these codes are defined but never emitted and not listed in RESERVED_CODES:\n  "
        + "\n  ".join(unaccounted)
        + "\n\nEither emit them from a profile or add them to RESERVED_CODES with a reason."
    )


def test_reserved_codes_all_exist():
    """A stale RESERVED_CODES entry would silently widen the exemption."""
    from carebundle.terminology import codes as table

    for name in table.RESERVED_CODES:
        assert isinstance(getattr(table, name, None), Code), f"{name} no longer exists"


def test_reserved_codes_each_carry_a_reason():
    from carebundle.terminology import codes as table

    for name, reason in table.RESERVED_CODES.items():
        assert reason.strip(), f"{name} is reserved without a reason"


# --- verification harness ---------------------------------------------------------
# These stub the network. The fetchers themselves are exercised by the nightly job;
# what matters here is that a lookup result is turned into the right verdict.

def test_matching_display_verifies_ok(monkeypatch):
    from carebundle.terminology import systems, verify

    code = Code(systems.LOINC, "1234-5", "Some analyte")
    monkeypatch.setitem(verify.FETCHERS, systems.LOINC, lambda _: "Some analyte")
    assert verify.verify(code).status == verify.OK


def test_differing_display_is_reported_with_the_authoritative_text(monkeypatch):
    """The failure mode that shipped a wrong eGFR display past review."""
    from carebundle.terminology import systems, verify

    code = Code(systems.LOINC, "98979-8", "a display from a third-party aggregator")
    monkeypatch.setitem(verify.FETCHERS, systems.LOINC, lambda _: "the real display")

    finding = verify.verify(code)
    assert finding.status == verify.DISPLAY_MISMATCH
    assert finding.authoritative_display == "the real display"
    assert finding.is_problem


def test_unknown_code_is_reported_as_missing(monkeypatch):
    from carebundle.terminology import systems, verify

    monkeypatch.setitem(verify.FETCHERS, systems.RXNORM, lambda _: None)
    finding = verify.verify(Code(systems.RXNORM, "999999999", "not a drug"))
    assert finding.status == verify.NOT_FOUND
    assert finding.is_problem


def test_systems_without_a_public_authority_are_unchecked_not_failed():
    from carebundle.terminology import systems, verify

    finding = verify.verify(Code(systems.ACT_CODE, "AMB", "ambulatory"))
    assert finding.status == verify.UNCHECKED
    assert not finding.is_problem
    assert finding.note


def test_a_network_outage_is_not_reported_as_a_bad_code(monkeypatch):
    """A 404 means "not in the prescribable subset"; a 500 means the API is down.

    Collapsing the two would turn an outage into a spurious terminology failure and
    send someone chasing a code that is perfectly valid.
    """
    import urllib.error

    from carebundle.terminology import verify

    def explode(url):
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)

    monkeypatch.setattr(verify, "_get_json", explode)
    with pytest.raises(urllib.error.HTTPError):
        verify.fetch_rxnorm_name("861007")


def test_a_missing_prescribable_code_returns_none(monkeypatch):
    import urllib.error

    from carebundle.terminology import verify

    def not_found(url):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(verify, "_get_json", not_found)
    assert verify.fetch_rxnorm_name("999999999") is None


def test_verify_all_covers_every_registered_code(monkeypatch):
    from carebundle.terminology import verify

    for system in list(verify.FETCHERS):
        monkeypatch.setitem(verify.FETCHERS, system, lambda _: None)
    findings = verify.verify_all()
    assert len(findings) == len(registered_codes())
