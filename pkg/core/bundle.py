"""Transaction bundle assembly and reference wiring."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal

from pkg.models.r4 import Bundle, BundleEntry, BundleEntryRequest

# FHIR requires `decimal` to be a JSON *number*, and requires its precision to be
# preserved exactly ("1.50" carries three significant figures and is not "1.5").
# Python's json module cannot emit a Decimal unquoted, and float would silently
# discard the precision, so Decimals are marked during encoding and unquoted after.
# The validator rejects the alternative outright: "the primitive value must be a
# number".
# The sentinel must be printable ASCII: json.dumps escapes control characters, so a
# NUL-delimited sentinel arrives in the output as an escape sequence and never matches.
_DEC = "@@FHIRDEC@@"
_DEC_RE = re.compile(rf'"{re.escape(_DEC)}([-+0-9.eE]+){re.escape(_DEC)}"')

URN_UUID_RE = re.compile(r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class Entry:
    """One resource plus the urn:uuid other resources use to reference it."""

    urn: str
    resource: object

    @property
    def resource_type(self) -> str:
        return self.resource.resourceType


def build_transaction_bundle(entries: list[Entry]) -> Bundle:
    """Assemble a transaction Bundle.

    Resource `id` is dropped: in a transaction the server assigns identity, and
    fullUrl carries the intra-bundle reference target. Leaving both in place invites
    the two to disagree.
    """
    bundle_entries = []
    for entry in entries:
        # BundleEntry.resource is `Resource` in the spec, which the codegen treats as
        # opaque, so nested resources are serialized here rather than held as models.
        # mode="python" keeps Decimals intact for to_json(); mode="json" would coerce
        # them to strings here and the precision could never be recovered downstream.
        payload = entry.resource.model_dump(
            mode="python", exclude_none=True, by_alias=True
        )
        payload.pop("id", None)
        bundle_entries.append(
            BundleEntry(
                fullUrl=entry.urn,
                resource=payload,
                request=BundleEntryRequest(method="POST", url=entry.resource_type),
            )
        )
    return Bundle(type="transaction", entry=bundle_entries)


def collect_references(payload: object) -> set[str]:
    """Every urn:uuid reference anywhere in a serialized bundle."""
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "reference" and isinstance(value, str) and value.startswith("urn:uuid:"):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def dangling_references(bundle: Bundle) -> set[str]:
    """References that point at nothing in this bundle.

    A dangling urn:uuid is the classic bundle-assembly bug: the resource validates
    fine on its own and the bundle is structurally well-formed, but the graph is
    broken. This is asserted as a property test rather than left to review.
    """
    payload = bundle.model_dump(mode="json", exclude_none=True, by_alias=True)
    targets = {e["fullUrl"] for e in payload.get("entry", []) if "fullUrl" in e}
    return collect_references(payload) - targets


def _mark_decimals(value: object) -> str:
    if isinstance(value, Decimal):
        return f"{_DEC}{value}{_DEC}"
    raise TypeError(f"cannot serialize {type(value).__name__} to FHIR JSON")


def to_json(resource, *, indent: int = 2) -> str:
    """Serialize to FHIR JSON.

    exclude_none is what keeps absent elements absent; the decimal pass is what keeps
    numeric values numeric (see the _DEC note above).
    """
    payload = resource.model_dump(mode="python", exclude_none=True, by_alias=True)
    text = json.dumps(payload, indent=indent, sort_keys=False, default=_mark_decimals)
    return _DEC_RE.sub(r"\1", text)
