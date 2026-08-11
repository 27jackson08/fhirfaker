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
