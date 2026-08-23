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

**That study is from 2019 and its blood-pressure result no longer reproduces.** Run
against a current Synthea build (August 2026, 1,200 patients, default Massachusetts
settings) this module measures Synthea at **74.8%** on CBP, not 0%. Whatever was
broken in 2019 has been fixed. `carebundle.benchmark.synthea` is the harness that
measures it, so the claim is now checked rather than cited — see `BENCHMARK.md` for
the full comparison and what it means for this project's positioning.

This project models clinical state directly, which is the machinery an outcome measure
needs. That remains the architectural difference; it is no longer a claim that Synthea
scores zero.

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


# Hypertension in SNOMED CT. This package does not *emit* SNOMED — it cannot, on
# licensing grounds — but a measure that only recognises ICD-10-CM scores any
# SNOMED-coded source at zero for a terminology reason, and a zero from an empty
# denominator is indistinguishable from a zero from uncontrolled patients unless you
# go looking. Synthea codes conditions in SNOMED only, so without this the head-to-head
# would have "reproduced" the 2019 finding by accident.
#
# Read off a generated Synthea population rather than recalled: 59621000 is the only
# hypertension code that appeared. The rest are its near neighbours, included so a
# configuration that emits them is not silently dropped.
HYPERTENSION_SNOMED = frozenset({
    "59621000",   # essential hypertension
    "38341003",   # hypertensive disorder, systemic arterial
    "1201005",    # benign essential hypertension
    "10725009",   # benign hypertension
    "48146000",   # diastolic hypertension
})


def _has_hypertension(bundle: dict[str, Any]) -> bool:
    for condition in _resources(bundle, "Condition"):
        for coding in condition.get("code", {}).get("coding", []):
            system, code = coding.get("system"), coding.get("code")
            if system == systems.ICD10CM and code in HYPERTENSION_CODES:
                return True
            if system == systems.SNOMED and code in HYPERTENSION_SNOMED:
                return True
    return False


def _blood_pressures(bundle: dict[str, Any]) -> list[tuple[str, float, float]]:
    """Every (date, systolic, diastolic) recorded in the bundle, oldest first.

    Reads the panel's components rather than trusting ordering, because a BP panel is
    a single Observation with two components and their order is not guaranteed.

    Sorted by `effectiveDateTime`, because the measure asks for the *most recent*
    reading and array position is not time. On a one-visit bundle the distinction is
    invisible; on a lifetime it decides the answer, and a benchmark that silently took
    whichever reading happened to be last in the file would not be measuring CBP.
    Readings with no date are dropped — an undated observation cannot be known to be
    the most recent one.
    """
    readings: list[tuple[str, float, float]] = []
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
        when = (observation.get("effectiveDateTime") or "")[:10]
        if systolic is not None and diastolic is not None and when:
            readings.append((when, systolic, diastolic))
    return sorted(readings)


def _age_on(bundle: dict[str, Any], iso_date: str | None) -> float | None:
    """Age on a given date, from birthDate.

    Takes the date rather than reading `encounters[0]`. The measure asks whether the
    patient was 18-85 *when the blood pressure was taken*; on a single-visit bundle the
    first encounter is that visit, but on a lifetime it is usually infancy, which would
    drop most of the denominator for no clinical reason.

    Returns None when either input is missing rather than guessing — an unknown age must
    not silently enter or leave a measure denominator.
    """
    patients = _resources(bundle, "Patient")
    if not patients or not iso_date:
        return None
    birth = patients[0].get("birthDate")
    if not birth:
        return None
    birth_year, birth_month, birth_day = (int(p) for p in birth.split("-"))
    year, month, day = (int(p) for p in iso_date[:10].split("-"))
    years = year - birth_year
    if (month, day) < (birth_month, birth_day):
        years -= 1
    return float(years)


def controlling_high_blood_pressure(bundle: dict[str, Any]) -> tuple[bool, bool]:
    """HEDIS CBP for one bundle: (in denominator, in numerator).

    Denominator: age 18-85 with a coded hypertension diagnosis and a recorded BP.
    Numerator:   most recent BP below 140/90. Both components must be controlled;
                 an isolated diastolic elevation fails the measure.
    """
    readings = _blood_pressures(bundle)
    if not readings:
        return False, False
    when, systolic, diastolic = readings[-1]

    age = _age_on(bundle, when)
    if age is None or not (CBP_MIN_AGE <= age <= CBP_MAX_AGE):
        return False, False
    if not _has_hypertension(bundle):
        return False, False

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
