"""Command line interface.

A thin shell over the library. The library is the product; this exists for people who
want files without writing Python (build doc Section 7).

argparse rather than click/typer: the install-weight claim in the README has to stay
true, and a CLI does not justify a dependency.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pkg.core.bundle import to_json
from pkg.generate import DEFAULT_REFERENCE_DATE, generate_bundle
from pkg.profiles.library import PROFILES

EXIT_OK = 0
EXIT_USAGE = 2


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
        prog="pkg",
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
        "--profile", default="type2_diabetes", choices=sorted(PROFILES),
        help="clinical profile to draw from (default: %(default)s)",
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


def _sex_for(requested: str, index: int) -> str:
    return ("F", "M")[index % 2] if requested == "mixed" else requested


def command_generate(args: argparse.Namespace) -> int:
    age_range = _parse_age_range(args.age_range)

    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)

    for index in range(args.count):
        bundle = generate_bundle(
            profile=args.profile,
            seed=args.seed,
            sex=_sex_for(args.sex, index),
            age_range=age_range,
            reference_date=args.reference_date,
            index=index,
        )
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
    return EXIT_OK


COMMANDS = {"generate": command_generate, "profiles": command_profiles}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
