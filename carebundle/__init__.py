"""Clinically coherent synthetic FHIR(R) R4 test data.

FHIR(R) is the registered trademark of HL7 and is used with the permission of HL7.
"""

from __future__ import annotations

from carebundle.bulk import to_ndjson
from carebundle.calibration.custom import Quartiles, calibrate_profile, forget_profile
from carebundle.core.bundle import to_json
from carebundle.generate import (
    generate_bundle,
    generate_cohort,
    generate_draw,
    generate_patient,
)
from carebundle.history import generate_history
from carebundle.imperfection import Defect, Imperfection, inject_defects
from carebundle.profiles.library import PROFILES

# The single source of truth for the version. `pyproject.toml` declares the
# version dynamic and reads it from here, so the two cannot drift — 0.1.1 shipped
# with metadata saying 0.1.1 and this attribute still saying 0.1.0.
__version__ = "0.5.0"

__all__ = [
    "PROFILES",
    "Defect",
    "Imperfection",
    "Quartiles",
    "__version__",
    "calibrate_profile",
    "forget_profile",
    "generate_bundle",
    "generate_cohort",
    "generate_draw",
    "generate_history",
    "generate_patient",
    "inject_defects",
    "to_json",
    "to_ndjson",
]
