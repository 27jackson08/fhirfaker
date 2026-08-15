"""Clinical quality measures computed over generated output.

This exists to answer one question with evidence rather than assertion: does the
generated population reproduce the quality-measure rates a real population produces?

The measures are computed from the emitted FHIR, not from the internal draw. That is
deliberate — a measure engine reading `ProfileDraw` would be marking its own homework,
and the thing users receive is the bundle.
"""

from carebundle.benchmark.cqm import (
    MEASURES,
    MeasureResult,
    controlling_high_blood_pressure,
    run_measure,
)

__all__ = [
    "MEASURES",
    "MeasureResult",
    "controlling_high_blood_pressure",
    "run_measure",
]
