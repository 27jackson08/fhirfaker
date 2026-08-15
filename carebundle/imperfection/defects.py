"""Defect injection over a decoded FHIR bundle.

Operates on the decoded JSON rather than the pydantic models, deliberately: the whole
point is to produce documents the models would refuse to build. A missing required
field cannot be expressed in a validated model, which is exactly why the code under
test has never seen one.

Injection is deterministic under a seed, like everything else here — a fixture you
cannot reproduce is not a fixture.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from carebundle.core.ids import deterministic_uuid

# Every defect kind this module can inject. Exported so a caller can enumerate them
# rather than hardcoding strings that later drift.
DEFECT_KINDS = (
    "missing_field",
    "duplicate_entry",
    "out_of_order_timestamp",
    "unparseable_value",
    "unknown_code_system",
)


@dataclass(frozen=True)
class Defect:
    """One injected flaw, described precisely enough to assert against."""

    kind: str
    resource_type: str
    entry_index: int
    detail: str

    def __post_init__(self) -> None:
        if self.kind not in DEFECT_KINDS:
            raise ValueError(f"unknown defect kind {self.kind!r}; known: {DEFECT_KINDS}")


@dataclass(frozen=True)
class Imperfection:
    """How dirty to make the bundle. Every rate is a per-eligible-resource probability.

    Defaults are all zero: constructing `Imperfection()` and injecting it is a no-op,
    so the only way to get a malformed bundle is to ask for one specifically.
    """

    missing_field: float = 0.0
    duplicate_entry: float = 0.0
    out_of_order_timestamp: float = 0.0
    unparseable_value: float = 0.0
    unknown_code_system: float = 0.0
    # Fields a real system plausibly omits. Not `id` or `resourceType`, which would
    # produce garbage rather than realistic mess.
    droppable_fields: tuple[str, ...] = field(
        default_factory=lambda: ("text", "status", "category", "encounter")
    )

    def __post_init__(self) -> None:
        for name in DEFECT_KINDS:
            rate = getattr(self, name)
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"{name} must be a probability in [0, 1], got {rate}")

    @property
    def is_noop(self) -> bool:
        return all(getattr(self, kind) == 0.0 for kind in DEFECT_KINDS)


def _entries(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return bundle.get("entry", [])


def _resource_type(entry: dict[str, Any]) -> str:
    return entry.get("resource", {}).get("resourceType", "unknown")


def inject(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    *,
    seed: int,
) -> tuple[dict[str, Any], tuple[Defect, ...]]:
    """Return a dirtied copy of `bundle` plus the defects applied to it.

    The input is never mutated. Defects are returned in the order applied, and each
    names the entry index it hit so a caller can point a failing assertion at it.
    """
    if imperfection.is_noop:
        return copy.deepcopy(bundle), ()

    rng = np.random.default_rng(seed)
    dirty = copy.deepcopy(bundle)
    defects: list[Defect] = []

    # Order matters. Duplication is applied last so that indices recorded by the
    # earlier passes still refer to the entries a reader will find at those positions.
    _inject_missing_fields(dirty, imperfection, rng, defects)
    _inject_bad_timestamps(dirty, imperfection, rng, defects)
    _inject_unparseable_values(dirty, imperfection, rng, defects)
    _inject_unknown_systems(dirty, imperfection, rng, defects)
    _inject_duplicates(dirty, imperfection, rng, defects, seed)

    return dirty, tuple(defects)


def _inject_missing_fields(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    rng: np.random.Generator,
    defects: list[Defect],
) -> None:
    """Drop a field a real extract plausibly omits."""
    for index, entry in enumerate(_entries(bundle)):
        resource = entry.get("resource", {})
        present = [f for f in imperfection.droppable_fields if f in resource]
        if not present or rng.random() >= imperfection.missing_field:
            continue
        dropped = present[int(rng.integers(len(present)))]
        del resource[dropped]
        defects.append(Defect(
            kind="missing_field",
            resource_type=_resource_type(entry),
            entry_index=index,
            detail=f"removed {dropped!r}",
        ))


def _inject_bad_timestamps(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    rng: np.random.Generator,
    defects: list[Defect],
) -> None:
    """Make an effective time land after the encounter that supposedly produced it.

    A backdated or future-dated result is one of the most common real-world data
    quality faults and one of the least likely to be handled.
    """
    for index, entry in enumerate(_entries(bundle)):
        resource = entry.get("resource", {})
        if "effectiveDateTime" not in resource:
            continue
        if rng.random() >= imperfection.out_of_order_timestamp:
            continue
        original = resource["effectiveDateTime"]
        year = int(original[:4]) + 1
        resource["effectiveDateTime"] = f"{year}{original[4:]}"
        defects.append(Defect(
            kind="out_of_order_timestamp",
            resource_type=_resource_type(entry),
            entry_index=index,
            detail=f"effectiveDateTime moved from {original} to {resource['effectiveDateTime']}",
        ))


def _inject_unparseable_values(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    rng: np.random.Generator,
    defects: list[Defect],
) -> None:
    """Replace a numeric result with the free text a human actually typed.

    'not detected', '<0.1' and 'QNS' all appear in production feeds where a consumer
    expects a number, and a naive float() on a value field is a real crash.
    """
    stand_ins = ("not detected", "<0.1", "QNS", "see comment")
    for index, entry in enumerate(_entries(bundle)):
        resource = entry.get("resource", {})
        quantity = resource.get("valueQuantity")
        if not isinstance(quantity, dict) or "value" not in quantity:
            continue
        if rng.random() >= imperfection.unparseable_value:
            continue
        original = quantity["value"]
        text = stand_ins[int(rng.integers(len(stand_ins)))]
        del resource["valueQuantity"]
        resource["valueString"] = text
        defects.append(Defect(
            kind="unparseable_value",
            resource_type=_resource_type(entry),
            entry_index=index,
            detail=f"valueQuantity {original} replaced by valueString {text!r}",
        ))


def _inject_unknown_systems(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    rng: np.random.Generator,
    defects: list[Defect],
) -> None:
    """Swap a coding system for a site-local one, as real interfaces do."""
    local = "urn:oid:1.2.840.114350.1.13.0.1.7.2.696580"
    for index, entry in enumerate(_entries(bundle)):
        resource = entry.get("resource", {})
        codings = resource.get("code", {}).get("coding")
        if not codings:
            continue
        if rng.random() >= imperfection.unknown_code_system:
            continue
        original = codings[0].get("system")
        codings[0]["system"] = local
        defects.append(Defect(
            kind="unknown_code_system",
            resource_type=_resource_type(entry),
            entry_index=index,
            detail=f"system {original} replaced by site-local {local}",
        ))


def _inject_duplicates(
    bundle: dict[str, Any],
    imperfection: Imperfection,
    rng: np.random.Generator,
    defects: list[Defect],
    seed: int,
) -> None:
    """Append a near-duplicate: same content, new identity.

    This is the interface-replay fault. It is appended rather than inserted so earlier
    recorded indices stay valid, and the duplicate carries a fresh `fullUrl` and id
    because a byte-identical entry is trivially dedupable and therefore not a test.
    """
    duplicates: list[tuple[int, dict[str, Any]]] = []
    for index, entry in enumerate(list(_entries(bundle))):
        if rng.random() >= imperfection.duplicate_entry:
            continue
        duplicates.append((index, copy.deepcopy(entry)))

    for source_index, entry in duplicates:
        new_id = deterministic_uuid(seed, "imperfection-duplicate", source_index)
        if "resource" in entry:
            entry["resource"]["id"] = new_id
        entry["fullUrl"] = f"urn:uuid:{new_id}"
        bundle.setdefault("entry", []).append(entry)
        defects.append(Defect(
            kind="duplicate_entry",
            resource_type=_resource_type(entry),
            entry_index=len(bundle["entry"]) - 1,
            detail=f"near-duplicate of entry {source_index} with fresh id {new_id}",
        ))
