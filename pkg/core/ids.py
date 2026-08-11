"""Deterministic identifier derivation.

The determinism contract (build doc Section 9) says seed=42 must produce
byte-identical output within a major version. A single `uuid4()` anywhere breaks
that, so every id in the system comes from here.
"""

from __future__ import annotations

import uuid

# Fixed project namespace. Changing this constant changes every generated id and is
# therefore a major-version-breaking act.
NAMESPACE = uuid.UUID("6f2a1d3e-9c47-5b8a-a1f0-2d4e6c8b0a17")


def deterministic_uuid(seed: int, role: str, index: int = 0) -> str:
    """Derive a stable UUIDv5 from (seed, role, index).

    `role` is the resource's semantic slot ("patient", "hba1c-observation"), not its
    resource type, so reordering resources within a bundle does not shift ids.
    """
    return str(uuid.uuid5(NAMESPACE, f"{seed}:{role}:{index}"))


def urn_uuid(seed: int, role: str, index: int = 0) -> str:
    """The `urn:uuid:` form used for intra-bundle references."""
    return f"urn:uuid:{deterministic_uuid(seed, role, index)}"
