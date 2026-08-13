"""Verify every shipped code against its source vocabulary.

Two problems this solves.

1. **Display strings are validated, not just codes.** LOINC 98979-8 shipped with a
   display taken from a third-party code aggregator and the HL7 validator rejected it
   outright. Displays must come from the source vocabulary.
2. **Curated subsets go stale** (build doc Section 14). A one-time load is a
   maintenance liability; a command that re-checks every code against its authority is
   not.

Network-dependent, so this is a command and a nightly CI job — never a unit test.

    python -m pkg.terminology.verify

Exit code is non-zero if any code is unknown, mis-displayed, or (for RxNorm) outside
the Current Prescribable Content subset the licence position depends on.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from pkg.terminology import codes as code_module
from pkg.terminology import systems
from pkg.terminology.codes import Code

TIMEOUT_SECONDS = 30

OK = "ok"
DISPLAY_MISMATCH = "display-mismatch"
NOT_FOUND = "not-found"
UNCHECKED = "unchecked"


@dataclass(frozen=True)
class Finding:
    code: Code
    status: str
    authoritative_display: str | None = None
    note: str = ""

    @property
    def is_problem(self) -> bool:
        return self.status in (DISPLAY_MISMATCH, NOT_FOUND)


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def fetch_loinc_display(code: str) -> str | None:
    """LOINC LONG_COMMON_NAME — the display the HL7 validator checks against."""
    url = (
        "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"
        f"?terms={urllib.parse.quote(code)}&df=LOINC_NUM,LONG_COMMON_NAME&maxList=20"
    )
    payload = _get_json(url)
    for loinc_num, long_name in payload[3] or []:
        if loinc_num == code:
            return long_name
    return None


def fetch_rxnorm_name(rxcui: str) -> str | None:
    """RxNorm normalized name via the /Prescribe/ endpoint.

    Using /Prescribe/ rather than the full API is deliberate: it serves only Current
    Prescribable Content, so a code outside the openly-redistributable subset returns
    nothing instead of silently passing. The licence constraint is enforced by the
    lookup itself rather than by remembering to check.
    """
    url = (
        f"https://rxnav.nlm.nih.gov/REST/Prescribe/rxcui/{urllib.parse.quote(rxcui)}"
        "/property.json?propName=RxNorm%20Name"
    )
    try:
        payload = _get_json(url)
    except urllib.error.HTTPError as exc:
        # 404 means "not in the prescribable subset", which is a real answer. Any
        # other HTTP status is an outage and must not be reported as a bad code.
        if exc.code == 404:
            return None
        raise
    group = payload.get("propConceptGroup")
    if not group:
        return None
    return group["propConcept"][0]["propValue"]


def fetch_icd10cm_display(code: str) -> str | None:
    url = (
        "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
        f"?terms={urllib.parse.quote(code)}&sf=code&df=code,name&maxList=20"
    )
    payload = _get_json(url)
    for found_code, name in payload[3] or []:
        if found_code == code:
            return name
    return None


FETCHERS = {
    systems.LOINC: fetch_loinc_display,
    systems.RXNORM: fetch_rxnorm_name,
    systems.ICD10CM: fetch_icd10cm_display,
}


def registered_codes() -> tuple[Code, ...]:
    """Every Code defined in the terminology module.

    Introspected rather than listed, so a newly added code cannot escape verification
    by being forgotten in a registry.
    """
    found = {
        value.code + value.system: value
        for value in vars(code_module).values()
        if isinstance(value, Code)
    }
    return tuple(sorted(found.values(), key=lambda c: (c.system, c.code)))


def verify(code: Code) -> Finding:
    fetcher = FETCHERS.get(code.system)
    if fetcher is None:
        # HL7 workflow code systems ship inside the validator's packages and are
        # checked by the conformance suite, which is a stronger check than any API.
        return Finding(code, UNCHECKED, note="no public authority; covered by validator")

    authoritative = fetcher(code.code)
    if authoritative is None:
        return Finding(code, NOT_FOUND)
    if authoritative != code.display:
        return Finding(code, DISPLAY_MISMATCH, authoritative)
    return Finding(code, OK, authoritative)


def verify_all(entries: tuple[Code, ...] | None = None) -> list[Finding]:
    return [verify(code) for code in (entries or registered_codes())]


def main() -> int:
    findings = verify_all()
    problems = [f for f in findings if f.is_problem]

    for finding in findings:
        if finding.status == OK:
            print(f"  ok        {finding.code.code:<12} {finding.code.display[:60]}")
        elif finding.status == UNCHECKED:
            print(f"  unchecked {finding.code.code:<12} {finding.note}")
        elif finding.status == NOT_FOUND:
            print(f"  MISSING   {finding.code.code:<12} not found in {finding.code.system}")
        else:
            print(f"  MISMATCH  {finding.code.code:<12}")
            print(f"      shipped:       {finding.code.display}")
            print(f"      authoritative: {finding.authoritative_display}")

    checked = sum(1 for f in findings if f.status != UNCHECKED)
    print(f"\n{checked - len(problems)}/{checked} verified against source vocabularies")
    if problems:
        print(f"{len(problems)} problem(s) — fix before shipping", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
