"""Regression tests for the validator output parser.

These run without a JVM. They exist because the parser failed silently once: the
validator colourises output, the issue regex matched nothing, and a resource with a
real conformance error was reported as a clean pass. A conformance gate that cannot
fail is worse than no gate, so the parsing is tested directly.
"""

from __future__ import annotations

import pytest

from pkg.conformance.validator import ANSI_RE, ISSUE_RE, SUMMARY_RE

# Real validator output, colour codes and all.
COLOURED_ERROR = (
    "\x1b[0;39m\x1b[39m  Error @ Patient.identifier[0].system (line 18, col60): "
    "Example URLs are not allowed in this context (http://example.org/x), "
    "validating against Base FHIR Standard"
)
COLOURED_SUMMARY = "\x1b[0;39m\x1b[39m*FAILURE*: 1 errors, 1 warnings, 0 notes"


def test_issue_regex_does_not_match_until_ansi_is_stripped():
    """The exact failure mode that made the harness report a false pass."""
    assert ISSUE_RE.match(COLOURED_ERROR) is None
    assert ISSUE_RE.match(ANSI_RE.sub("", COLOURED_ERROR)) is not None


def test_parses_severity_location_and_message():
    match = ISSUE_RE.match(ANSI_RE.sub("", COLOURED_ERROR))
    assert match.group(1) == "Error"
    assert match.group(2) == "Patient.identifier[0].system (line 18, col60)"
    assert match.group(3).startswith("Example URLs are not allowed")


def test_summary_counts_are_recovered():
    match = SUMMARY_RE.search(ANSI_RE.sub("", COLOURED_SUMMARY))
    assert (match.group(1), match.group(2)) == ("1", "1")


@pytest.mark.parametrize(
    "line,severity",
    [
        ("  Error @ Patient (line 1, col2): boom", "Error"),
        ("  Warning @ Patient.name (line 3, col4): meh", "Warning"),
        ("  Information @ Patient (line 1, col2): fyi", "Information"),
    ],
)
def test_all_severities_parse(line, severity):
    assert ISSUE_RE.match(line).group(1) == severity


def test_message_containing_colons_is_not_truncated_at_the_wrong_one():
    line = "  Error @ Patient.x (line 1, col2): url http://a.b/c is bad"
    match = ISSUE_RE.match(line)
    assert match.group(2) == "Patient.x (line 1, col2)"
    assert match.group(3) == "url http://a.b/c is bad"


# --- retry policy -----------------------------------------------------------------
# Retrying is only safe because it is scoped to failures that mean "the validator
# could not run". Retrying a genuine validation failure would hide real defects, so
# the discrimination is tested directly rather than trusted.

def test_transient_network_failures_are_recognised():
    from pkg.conformance.validator import _looks_transient

    for signature in (
        "java.net.SocketException: Socket closed",
        "java.net.UnknownHostException: tx.fhir.org",
        "SocketTimeoutException: Read timed out",
        "at ...FHIRToolingClient.getCapabilitiesStatement(FHIRToolingClient.java:142)",
    ):
        assert _looks_transient(signature), signature


def test_a_genuine_validation_failure_is_not_treated_as_transient():
    from pkg.conformance.validator import _looks_transient

    output = (
        "*FAILURE*: 2 errors, 0 warnings, 0 notes\n"
        "  Error @ Patient.identifier: minimum required = 1, but only found 0\n"
    )
    assert not _looks_transient(output)


def test_validate_retries_only_while_the_run_fails_transiently(monkeypatch, tmp_path):
    from pkg.conformance import validator

    target = tmp_path / "patient.json"
    target.write_text("{}")
    monkeypatch.setattr(validator, "VALIDATOR_JAR", tmp_path / "validator.jar")
    (tmp_path / "validator.jar").write_text("")
    monkeypatch.setattr(validator.time, "sleep", lambda _: None)

    attempts = []

    class _Result:
        def __init__(self, out):
            self.stdout, self.stderr = out, ""

    def fake_run(cmd, **kwargs):
        attempts.append(cmd)
        if len(attempts) < 3:
            return _Result("java.net.SocketException: Socket closed")
        return _Result("Success: 0 errors, 0 warnings, 0 notes")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(target)

    assert len(attempts) == 3, "should retry through transient failures"
    assert result.ok


def test_validate_does_not_retry_a_run_that_produced_a_verdict(monkeypatch, tmp_path):
    from pkg.conformance import validator

    target = tmp_path / "patient.json"
    target.write_text("{}")
    monkeypatch.setattr(validator, "VALIDATOR_JAR", tmp_path / "validator.jar")
    (tmp_path / "validator.jar").write_text("")

    attempts = []

    class _Result:
        def __init__(self, out):
            self.stdout, self.stderr = out, ""

    def fake_run(cmd, **kwargs):
        attempts.append(cmd)
        return _Result(
            "  Error @ Patient.gender: bad code\n"
            "*FAILURE*: 1 errors, 0 warnings, 0 notes\n"
        )

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(target)

    assert len(attempts) == 1, "a real verdict must not be retried away"
    assert not result.ok
    assert len(result.errors) == 1
