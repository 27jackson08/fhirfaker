"""Deliberately imperfect FHIR, for testing the code paths clean data never reaches.

Real EHR extracts contain missing fields, duplicated records, local coding habits and
timestamps that arrive out of order. Synthetic generators do not, and the literature on
synthetic health data repeatedly notes the gap. For the use case this library actually
serves — testing your application — that gap is the whole problem: software that has
only ever seen well-formed bundles has untested error paths, and the bug surfaces the
first time a real feed arrives.

Two rules govern everything here, and both are load-bearing:

1. **Off by default.** US Core conformance is Layer 1 of this project's claim and it
   stays provable. Imperfection is something you ask for.
2. **Every defect is machine-readable.** Injection returns the defects it applied, so a
   test can assert *"my parser rejected exactly these three records"* rather than
   eyeballing output. A corruption you cannot enumerate is not a fixture, it is noise.
"""

from carebundle.imperfection.defects import (
    DEFECT_KINDS,
    Defect,
    Imperfection,
    inject,
)

# Exported at the package root under a fuller name: `carebundle.inject` alone would be
# ambiguous next to the generate_* functions.
inject_defects = inject

__all__ = ["DEFECT_KINDS", "Defect", "Imperfection", "inject", "inject_defects"]
