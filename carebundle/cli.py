"""Command line interface.

A thin shell over the library. The library is the product; this exists for people who
want files without writing Python (build doc Section 7).

argparse rather than click/typer: the install-weight claim in the README has to stay
true, and a CLI does not justify a dependency.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from datetime import date
from pathlib import Path

from carebundle.core.bundle import to_json
from carebundle.generate import (
    ALL_PANELS,
    DEFAULT_COHORT_PREVALENCE,
    DEFAULT_REFERENCE_DATE,
    LEAN_PANELS,
    generate_bundle,
    generate_cohort,
)
from carebundle.profiles.library import PROFILES

MIXED = "mixed"

EXIT_OK = 0
EXIT_USAGE = 2
# Shell convention for death by signal: 128 + signal number.
EXIT_SIGINT = 130
EXIT_SIGPIPE = 141


def _parse_reference_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"reference date must be ISO format (YYYY-MM-DD), got {value!r}"
        ) from exc


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or greater, got {number}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="carebundle",
        description=(
            "Generate clinically coherent synthetic FHIR R4 test data. "
            "Output is US Core 6.1.0 conformant and deterministic for a given seed."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="generate transaction bundles"
    )
    generate.add_argument(
        "--profile", default="type2_diabetes", choices=[*sorted(PROFILES), MIXED],
        help="clinical profile to draw from, or 'mixed' for a cohort drawn by "
             "prevalence (default: %(default)s)",
    )
    generate.add_argument(
        "--count", type=_positive_int, default=1,
        help="number of patients to generate (default: %(default)s)",
    )
    generate.add_argument(
        "--seed", type=int, default=42,
        help="random seed; the same seed always produces the same bytes "
             "(default: %(default)s)",
    )
    generate.add_argument(
        "--sex", default="F", choices=("F", "M", "mixed"),
        help="patient sex, or alternate between them (default: %(default)s)",
    )
    generate.add_argument(
        "--age-range", default="45-65", metavar="LOW-HIGH",
        help="patient age range (default: %(default)s)",
    )
    generate.add_argument(
        "--reference-date", type=_parse_reference_date,
        default=DEFAULT_REFERENCE_DATE,
        help="date the encounter occurs on; never read from the clock, so output "
             "stays reproducible (default: %(default)s)",
    )
    generate.add_argument(
        "--panels", default="all", metavar="LIST",
        help="comma-separated lab panels to emit: "
             f"{','.join(ALL_PANELS)}; or 'all', 'lean' ({','.join(LEAN_PANELS)}), "
             "or 'none' (default: %(default)s)",
    )
    generate.add_argument(
        "--no-vitals", action="store_true",
        help="omit vital-sign observations",
    )
    generate.add_argument(
        "--out", type=Path,
        help="directory to write bundles into; omit to write JSON to stdout",
    )

    subparsers.add_parser("profiles", help="list available clinical profiles")
    return parser


def _parse_age_range(value: str) -> tuple[int, int]:
    try:
        low, high = (int(part) for part in value.split("-", 1))
    except ValueError as exc:
        raise SystemExit(f"error: --age-range must look like 45-65, got {value!r}") from exc
    if low > high:
        raise SystemExit(f"error: --age-range low {low} exceeds high {high}")
    return low, high


def _parse_panels(value: str) -> tuple[str, ...]:
    if value == "all":
        return ALL_PANELS
    if value == "lean":
        return LEAN_PANELS
    if value == "none":
        return ()
    requested = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = set(requested) - set(ALL_PANELS)
    if unknown:
        raise SystemExit(
            f"error: unknown panel(s) {sorted(unknown)}; available: {list(ALL_PANELS)}"
        )
    return requested


def _sex_for(requested: str, index: int) -> str:
    return ("F", "M")[index % 2] if requested == "mixed" else requested


def command_generate(args: argparse.Namespace) -> int:
    age_range = _parse_age_range(args.age_range)
    panels = _parse_panels(args.panels)
    include_vitals = not args.no_vitals

    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)

    if args.profile == MIXED:
        bundles = generate_cohort(
            count=args.count,
            seed=args.seed,
            sex=args.sex,
            age_range=age_range,
            reference_date=args.reference_date,
            panels=panels,
            include_vitals=include_vitals,
        )
    else:
        bundles = [
            generate_bundle(
                profile=args.profile,
                seed=args.seed,
                sex=_sex_for(args.sex, index),
                age_range=age_range,
                reference_date=args.reference_date,
                index=index,
                panels=panels,
                include_vitals=include_vitals,
            )
            for index in range(args.count)
        ]

    for index, bundle in enumerate(bundles):
        rendered = to_json(bundle)
        if args.out is None:
            print(rendered)
        else:
            target = args.out / f"{args.profile}-{args.seed}-{index:04d}.json"
            target.write_text(rendered)

    if args.out is not None:
        print(
            f"wrote {args.count} bundle(s) to {args.out}", file=sys.stderr
        )
    return EXIT_OK


def command_profiles(_: argparse.Namespace) -> int:
    for key in sorted(PROFILES):
        print(key)
    weights = ", ".join(
        f"{k} {v:.0%}" for k, v in sorted(DEFAULT_COHORT_PREVALENCE.items())
    )
    print(f"{MIXED}  (cohort drawn by prevalence: {weights})")
    return EXIT_OK


COMMANDS = {"generate": command_generate, "profiles": command_profiles}


def _restore_default_sigpipe() -> None:
    """Die quietly when a downstream reader closes the pipe.

    Python installs SIGPIPE as SIG_IGN, which converts a closed pipe into a
    BrokenPipeError and — because stdout is buffered — a shutdown-time "Exception
    ignored while flushing sys.stdout" that no `except` block around the command can
    suppress. Restoring the default disposition makes `carebundle generate | head`
    behave like any other Unix filter.

    No-op where SIGPIPE does not exist (Windows) or where the signal cannot be set
    (not the main thread); the BrokenPipeError handler in `main` covers those.
    """
    if not hasattr(signal, "SIGPIPE"):
        return
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ValueError, OSError):
        pass


def _silence_stdout() -> None:
    """Redirect stdout to devnull after a broken pipe.

    `carebundle generate ... | head` is ordinary usage, and the default behaviour is a
    traceback plus "Exception ignored while flushing sys.stdout" at interpreter
    shutdown. Giving that final flush somewhere to go suppresses both.

    Guarded because stdout is not always a real file descriptor — under pytest capture,
    or whenever the CLI is driven in-process, `fileno()` raises. Failing to silence the
    stream is cosmetic; raising a second exception out of the handler is not.
    """
    try:
        target = sys.stdout.fileno()
    except (OSError, ValueError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, target)
    except OSError:
        pass
    finally:
        os.close(devnull)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except BrokenPipeError:
        # Reached on platforms without SIGPIPE (Windows), and on POSIX when `main` is
        # driven in-process rather than through `run`.
        _silence_stdout()
        return EXIT_SIGPIPE
    except KeyboardInterrupt:
        # A large cohort takes a while; Ctrl-C should not look like a crash.
        print("interrupted", file=sys.stderr)
        return EXIT_SIGINT


def run() -> int:
    """Console-script entry point: `main` plus the process-level signal disposition.

    Kept separate from `main` deliberately. Resetting SIGPIPE is a whole-process change
    and `main` is called in-process by the test suite, which should not inherit it.
    """
    _restore_default_sigpipe()
    return main()


if __name__ == "__main__":
    raise SystemExit(run())
