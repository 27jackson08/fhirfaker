"""Safety by construction.

Synthetic clinical data that looks real is a liability if it ever reaches a real
system. Everything here exists so that a generated resource is self-identifying as
test data and can never collide with a real person's identifiers.

See build doc Section 7.
"""

from __future__ import annotations

from pkg.models.r4 import Coding, HumanName, Identifier, Meta, Narrative

# FHIR's own security label for test health data. Tagging every resource with this is
# what stops synthetic records from silently contaminating a production system.
HTEST_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
HTEST_CODE = "HTEST"

# The assigning authority for synthetic MRNs is this generator itself. A urn:uuid is
# globally unique by construction, so it needs no domain ownership and survives the
# pending rename (build doc Section 15).
#
# Do NOT substitute an example.org/example.com URL here: the HL7 validator rejects
# example URLs in identifier.system outright ("Example URLs are not allowed in this
# context"). Collision-safety and spec-conformance are separate requirements and the
# urn:uuid form is the only thing that satisfies both.
SYNTHETIC_MRN_SYSTEM = "urn:uuid:6f2a1d3e-9c47-5b8a-a1f0-2d4e6c8b0a17"
SYNTHETIC_SSN_SYSTEM = "http://hl7.org/fhir/sid/us-ssn"

US_CORE_PATIENT_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
)

# SSA has never issued an SSN with an area number in 900-999, so this range is
# permanently safe for synthetic data.
SSN_SAFE_AREA_MIN = 900
SSN_SAFE_AREA_MAX = 999

# Deliberately fictional. Not sampled from census frequency tables, because a realistic
# name distribution is exactly what makes synthetic records mistakable for real ones.
FICTIONAL_FAMILY_NAMES = (
    "Testerson", "Sampleton", "Fixtureby", "Mocklin", "Stubfield",
    "Placeholt", "Dummett", "Syntheson", "Fakeworth", "Provingham",
)
FICTIONAL_GIVEN_NAMES = (
    "Ada", "Bex", "Cato", "Dara", "Emet",
    "Fen", "Gale", "Hux", "Ives", "Juno",
)


def htest_meta(profile: str | None = None) -> Meta:
    """Build a Meta carrying the HTEST label, optionally asserting a profile."""
    return Meta(
        profile=[profile] if profile else None,
        security=[
            Coding(system=HTEST_SYSTEM, code=HTEST_CODE, display="test health data")
        ],
    )


def synthetic_narrative(summary: str) -> Narrative:
    """Build the human-readable narrative FHIR's dom-6 best practice asks for.

    The text says SYNTHETIC out loud: the narrative is what a human sees first in any
    FHIR viewer, so it is the highest-value place to state that this is not real data.
    """
    return Narrative(
        status="generated",
        div=(
            '<div xmlns="http://www.w3.org/1999/xhtml">'
            "<p><b>SYNTHETIC TEST DATA — not a real person.</b></p>"
            f"<p>{summary}</p>"
            "</div>"
        ),
    )


def synthetic_mrn(value: str) -> Identifier:
    """A medical record number under a documentation-reserved system."""
    return Identifier(
        system=SYNTHETIC_MRN_SYSTEM,
        value=value,
        type=None,
    )


def synthetic_ssn(area: int, group: int, serial: int) -> Identifier:
    """An SSN drawn from the never-issued 900-999 area range."""
    if not SSN_SAFE_AREA_MIN <= area <= SSN_SAFE_AREA_MAX:
        raise ValueError(
            f"SSN area {area} is outside the never-issued range "
            f"{SSN_SAFE_AREA_MIN}-{SSN_SAFE_AREA_MAX}; refusing to mint an "
            "identifier that could collide with a real person."
        )
    return Identifier(system=SYNTHETIC_SSN_SYSTEM, value=f"{area:03d}-{group:02d}-{serial:04d}")


def fictional_name(family_index: int, given_index: int) -> HumanName:
    """Pick a name from the fictional pool by index (caller supplies the seeding)."""
    return HumanName(
        use="official",
        family=FICTIONAL_FAMILY_NAMES[family_index % len(FICTIONAL_FAMILY_NAMES)],
        given=[FICTIONAL_GIVEN_NAMES[given_index % len(FICTIONAL_GIVEN_NAMES)]],
    )
