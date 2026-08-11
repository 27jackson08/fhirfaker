"""Harness around the official HL7 FHIR validator.

This is a DEV/CI dependency only. The JVM never appears at runtime or install time —
that separation is load-bearing for the project's positioning (build doc Section 10).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_JAR = REPO_ROOT / ".tools" / "validator_cli.jar"

FHIR_VERSION = "4.0.1"
US_CORE_IG = "hl7.fhir.us.core#6.1.0"

# The validator colourises its output, so every line arrives prefixed with escape
# sequences. Stripping them is load-bearing: without it the issue regex silently
# matches nothing and a failing validation parses as a clean pass.
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\[[0-9;]+m")

# Validator prints e.g. "  Error @ Patient.identifier (line 5, col12): message"
ISSUE_RE = re.compile(r"^\s*(Error|Warning|Information)\s+@\s+(.+?)\s*:\s*(.*)$")

# Emitted as "*FAILURE*: 3 errors, 1 warnings, 0 notes" / "Success...".
SUMMARY_RE = re.compile(r"(\d+)\s+errors?,\s+(\d+)\s+warnings?", re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    severity: str
    location: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    issues: tuple[Issue, ...]
    raw: str

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "Error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "Warning")

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(
    path: Path,
    *,
    profile: str | None = None,
    ig: str = US_CORE_IG,
    timeout: int = 900,
) -> ValidationResult:
    """Run the HL7 validator against one file.

    First invocation downloads the IG packages it needs and is slow; later runs hit
    the local package cache.
    """
    if not VALIDATOR_JAR.exists():
        raise FileNotFoundError(
            f"validator jar not found at {VALIDATOR_JAR}. Fetch it with:\n"
            "  curl -sSL -o .tools/validator_cli.jar "
            "https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/"
            "download/validator_cli.jar"
        )

    cmd = [
        "java", "-jar", str(VALIDATOR_JAR),
        str(path),
        "-version", FHIR_VERSION,
        "-ig", ig,
    ]
    if profile:
        cmd += ["-profile", profile]

    completed = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    output = ANSI_RE.sub("", completed.stdout + completed.stderr)

    issues = tuple(
        Issue(severity=m.group(1), location=m.group(2).strip(), message=m.group(3).strip())
        for line in output.splitlines()
        if (m := ISSUE_RE.match(line))
    )

    # Cross-check the parse against the validator's own tally. A silent parse failure
    # here would report a failing resource as conformant, which is the single worst
    # way this harness could break.
    summary = SUMMARY_RE.search(output)
    if summary is None:
        raise RuntimeError(
            f"could not find a validator summary line in output for {path}; "
            f"the validator likely failed to run.\n{output[-2000:]}"
        )
    reported_errors, reported_warnings = int(summary.group(1)), int(summary.group(2))
    parsed_errors = sum(1 for i in issues if i.severity == "Error")
    parsed_warnings = sum(1 for i in issues if i.severity == "Warning")
    if (reported_errors, reported_warnings) != (parsed_errors, parsed_warnings):
        raise RuntimeError(
            f"validator output parse mismatch for {path}: validator reported "
            f"{reported_errors} errors/{reported_warnings} warnings but the harness "
            f"parsed {parsed_errors}/{parsed_warnings}. Refusing to report a result."
        )

    return ValidationResult(path=path, issues=issues, raw=output)
