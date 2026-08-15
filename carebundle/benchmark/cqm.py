"""CMS/HEDIS clinical quality measures, computed from generated bundles.

Why this module exists
----------------------
Synthea's published validation (Chen J, Chun D, Patel M, Chiang E, James J, "The
validity of synthetic clinical data: a validation study of a leading synthetic data
generator (Synthea) using clinical quality measures", BMC Med Inform Decis Mak 2019)
measured Synthea against four CMS quality measures and found it tracks reality on the
*process* measure and collapses on every *outcome* measure:

    Colorectal cancer screening   68.7%   vs 69.8% US   (process, close)
    COPD 30-day mortality          0.7%   vs  8.0% US   (outcome)
    Hip/knee complications         0.0%   vs  2.8% US   (outcome)
    Controlling high blood pressure 0.0%  vs 69.7% US   (outcome)

The authors name the mechanism: synthetic generators "do not currently model for
deviations in care and the potential outcomes that may result from care deviations."
That is a statement about architecture. A state machine over care pathways decides
*whether a patient was screened*; it has no representation of what the blood pressure
did afterwards, so a control rate cannot emerge from it.

This project models clinical state directly, which is the machinery an outcome measure
needs, so this is the ground on which it can be compared and win.

Reading the numbers honestly
----------------------------
Denominators differ between sources and conflating them produces a wrong answer that
looks right:

  * NHANES reports control over *all* adults with hypertension, including the unaware
    and untreated, and since the 2017 ACC/AHA guideline it uses a **<130/80** threshold.
    The August 2021-August 2023 figure is 20.7%.
  * HEDIS/CMS `Controlling High Blood Pressure` (CBP) uses **<140/90** over a much
    narrower denominator: members aged 18-85 with a *diagnosed* hypertension and an
    outpatient encounter. That is the ~70% figure, and it is the one the Synthea
    validation study used.

These profiles emit a coded hypertension diagnosis and an encounter, so they are the
HEDIS denominator, and <140/90 is the applicable threshold. Using NHANES's 20.7%
as the target here would be comparing against a different population and a different
cut-off.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from carebundle.terminology import codes, systems

# LOINC panel and component codes for an office blood pressure.
_BP_PANEL = "85354-9"
_SYSTOLIC = codes.BP_SYSTOLIC.code
_DIASTOLIC = codes.BP_DIASTOLIC.code

# NCQA HEDIS CBP: adults 18-85 with diagnosed hypertension, controlled at <140/90.
CBP_SYSTOLIC_THRESHOLD = 140.0
CBP_DIASTOLIC_THRESHOLD = 90.0
CBP_MIN_AGE = 18
CBP_MAX_AGE = 85

HYPERTENSION_CODES = frozenset({codes.ESSENTIAL_HYPERTENSION.code})


@dataclass(frozen=True)
class MeasureResult:
    """One measure evaluated over a population of bundles."""

    measure: str
    numerator: int
    denominator: int

    @property
    def rate(self) -> float:
        """Proportion meeting the measure, or 0.0 when nobody qualifies.

        A zero denominator is reported as a zero rate *and* a zero denominator, so a
        measure nobody qualified for cannot be mistaken for a measure everybody failed.
        That distinction is the whole difference between "not modelled" and "0%", and
        it is the row most worth being honest about when comparing against Synthea.
        """
        if self.denominator == 0:
            return 0.0
        return self.numerator / self.denominator


def _resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    return [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if entry.get("resource", {}).get("resourceType") == resource_type
    ]


def _has_hypertension(bundle: dict[str, Any]) -> bool:
    for condition in _resources(bundle, "Condition"):
        for coding in condition.get("code", {}).get("coding", []):
            if (
                coding.get("system") == systems.ICD10CM
                and coding.get("code") in HYPERTENSION_CODES
            ):
                return True
    return False


def _blood_pressures(bundle: dict[str, Any]) -> list[tuple[float, float]]:
    """Every (systolic, diastolic) pair recorded in the bundle.

    Reads the panel's components rather than trusting ordering, because a BP panel is
    a single Observation with two components and their order is not guaranteed.
    """
    readings: list[tuple[float, float]] = []
    for observation in _resources(bundle, "Observation"):
        panel = {
            coding.get("code")
            for coding in observation.get("code", {}).get("coding", [])
        }
        if _BP_PANEL not in panel:
            continue
        systolic = diastolic = None
        for component in observation.get("component", []):
            found = {
                coding.get("code")
                for coding in component.get("code", {}).get("coding", [])
            }
            value = component.get("valueQuantity", {}).get("value")
            if value is None:
                continue
            if _SYSTOLIC in found:
                systolic = float(value)
            elif _DIASTOLIC in found:
                diastolic = float(value)
        if systolic is not None and diastolic is not None:
            readings.append((systolic, diastolic))
    return readings


def _age_years(bundle: dict[str, Any]) -> float | None:
    """Age at the encounter, from birthDate and the encounter period.

    Returns None when either is missing rather than guessing — an unknown age must not
    silently enter or leave a measure denominator.
    """
    patients = _resources(bundle, "Patient")
    encounters = _resources(bundle, "Encounter")
    if not patients or not encounters:
        return None
    birth = patients[0].get("birthDate")
    start = encounters[0].get("period", {}).get("start")
    if not birth or not start:
        return None
    birth_year, birth_month, birth_day = (int(p) for p in birth.split("-"))
    enc_year, enc_month, enc_day = (int(p) for p in start[:10].split("-"))
    years = enc_year - birth_year
    if (enc_month, enc_day) < (birth_month, birth_day):
        years -= 1
    return float(years)


def controlling_high_blood_pressure(bundle: dict[str, Any]) -> tuple[bool, bool]:
    """HEDIS CBP for one bundle: (in denominator, in numerator).

    Denominator: age 18-85 with a coded hypertension diagnosis and a recorded BP.
    Numerator:   most recent BP below 140/90. Both components must be controlled;
                 an isolated diastolic elevation fails the measure.
    """
    age = _age_years(bundle)
    if age is None or not (CBP_MIN_AGE <= age <= CBP_MAX_AGE):
        return False, False
    if not _has_hypertension(bundle):
        return False, False

    readings = _blood_pressures(bundle)
    if not readings:
        return False, False

    systolic, diastolic = readings[-1]
    controlled = (
        systolic < CBP_SYSTOLIC_THRESHOLD and diastolic < CBP_DIASTOLIC_THRESHOLD
    )
    return True, controlled


MEASURES: dict[str, Callable[[dict[str, Any]], tuple[bool, bool]]] = {
    "controlling_high_blood_pressure": controlling_high_blood_pressure,
}


def run_measure(
    measure: str, bundles: Iterable[dict[str, Any]] | Sequence[dict[str, Any]]
) -> MeasureResult:
    """Evaluate a named measure across a population of decoded bundles."""
    if measure not in MEASURES:
        raise KeyError(f"unknown measure {measure!r}; known: {sorted(MEASURES)}")
    evaluate = MEASURES[measure]

    numerator = denominator = 0
    for bundle in bundles:
        in_denominator, in_numerator = evaluate(bundle)
        denominator += in_denominator
        numerator += in_numerator
    return MeasureResult(
        measure=measure, numerator=numerator, denominator=denominator
    )
