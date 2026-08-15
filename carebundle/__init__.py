"""Clinically coherent synthetic FHIR(R) R4 test data.

FHIR(R) is the registered trademark of HL7 and is used with the permission of HL7.
"""

from __future__ import annotations

from carebundle.core.bundle import to_json
from carebundle.generate import generate_bundle, generate_draw, generate_patient
from carebundle.profiles.library import PROFILES

__version__ = "0.1.0"

__all__ = [
    "PROFILES",
    "__version__",
    "generate_bundle",
    "generate_draw",
    "generate_patient",
    "to_json",
]
