"""FHIR Bulk Data (ndjson) output, for testing `$export` ingest.

A transaction Bundle and a bulk export are not the same document in a different
wrapper, and converting between them is the whole content of this module.

In a transaction the server assigns identity, so `build_transaction_bundle` drops
`Resource.id` and lets `fullUrl` carry the intra-bundle reference target — references
read `urn:uuid:2f9a…`. A bulk export is the opposite: it is a snapshot of resources that
already exist, each with an `id`, and references read `Patient/2f9a…`. A naive converter
that strips the Bundle wrapper and writes the entries out produces resources with no id
and dangling `urn:uuid:` references — structurally parseable and useless to the importer
under test, which is the case this is supposed to exercise.

So the conversion here does three things: mints each resource's `id` from its `fullUrl`,
rewrites every `urn:uuid:` reference to the relative `ResourceType/id` form, and groups
the result by resource type, one ndjson stream per type, as the Bulk Data IG specifies.

    from carebundle import generate_cohort, to_ndjson

    for resource_type, lines in to_ndjson(generate_cohort(count=100, seed=42)).items():
        Path(f"{resource_type}.ndjson").write_text(lines, encoding="utf-8")
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from carebundle.core.bundle import to_json
from carebundle.models.r4 import Bundle

URN_PREFIX = "urn:uuid:"


def _resource_id(full_url: str) -> str:
    """The `id` a bulk-exported resource carries, taken from its bundle `fullUrl`.

    A UUID is a valid FHIR id, so the uuid part is used verbatim rather than minting a
    second identifier — the ids then match the bundle output for the same seed, which
    makes the two formats comparable.
    """
    return full_url.removeprefix(URN_PREFIX)


def _rewrite_references(node: object, targets: dict[str, str]) -> object:
    """Replace every `urn:uuid:` reference with its relative `ResourceType/id` form.

    A reference to something outside this bundle is left alone rather than guessed at:
    an unresolvable `urn:uuid:` in the output is a visible defect, while a fabricated
    `Patient/…` pointing at nothing is a silent one.
    """
    if isinstance(node, dict):
        rewritten = {}
        for key, value in node.items():
            if key == "reference" and isinstance(value, str) and value in targets:
                rewritten[key] = targets[value]
            else:
                rewritten[key] = _rewrite_references(value, targets)
        return rewritten
    if isinstance(node, list):
        return [_rewrite_references(item, targets) for item in node]
    return node


def to_ndjson(bundles: Bundle | Iterable[Bundle]) -> dict[str, str]:
    """Convert bundles to one newline-delimited JSON stream per resource type.

    Accepts a single Bundle or any iterable of them, so a cohort can be exported as one
    dataset — which is the realistic shape, since a bulk export covers a population
    rather than a patient.

    Returns `{resource_type: ndjson_text}`. Each line is a complete FHIR resource with
    an `id`, and every intra-bundle reference has been rewritten to `ResourceType/id`.
    """
    if isinstance(bundles, Bundle):
        bundles = [bundles]

    streams: dict[str, list[str]] = {}
    for bundle in bundles:
        payload = json.loads(to_json(bundle))
        entries = payload.get("entry", [])

        # Resolve every fullUrl to its relative reference first: a resource can point at
        # one that appears later in the bundle.
        targets = {
            entry["fullUrl"]: f"{entry['resource']['resourceType']}/{_resource_id(entry['fullUrl'])}"
            for entry in entries
            if "fullUrl" in entry and "resource" in entry
        }

        for entry in entries:
            resource = entry.get("resource")
            if resource is None:
                continue
            converted = _rewrite_references(resource, targets)
            if "fullUrl" in entry:
                converted = {"resourceType": converted["resourceType"],
                             "id": _resource_id(entry["fullUrl"]),
                             **{k: v for k, v in converted.items() if k != "resourceType"}}
            streams.setdefault(converted["resourceType"], []).append(
                json.dumps(converted, separators=(",", ":"), sort_keys=True)
            )

    return {kind: "\n".join(lines) + "\n" for kind, lines in sorted(streams.items())}


__all__ = ["to_ndjson"]
