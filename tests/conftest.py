from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--conformance-scale",
        action="store",
        default="sample",
        choices=("sample", "full"),
        help=(
            "sample: a few seeds, for the PR gate (JVM cold start is slow). "
            "full: the whole profile x resource-type matrix, for the nightly run."
        ),
    )


@pytest.fixture(scope="session")
def conformance_scale(request) -> str:
    return request.config.getoption("--conformance-scale")


@pytest.fixture(scope="session")
def conformance_seeds(conformance_scale) -> tuple[int, ...]:
    return (42,) if conformance_scale == "sample" else tuple(range(42, 62))
