"""Calibration tooling: XPT parsing and distribution fitting.

Both halves of this are silent-failure formats. IBM hexadecimal floats read as IEEE
doubles produce numbers, not errors. NAMESTR offsets that are wrong by a few bytes
produce plausible-looking variables with 1-byte widths and garbage labels — which is
exactly what happened on the first attempt, and nothing raised.
"""

from __future__ import annotations

import math
import struct

import numpy as np
import pytest

from pkg.calibration.xpt import NAMESTR_SIZE, _parse_namestrs, ibm_to_double
from pkg.correlation.distributions import (
    LogNormalMarginal,
    Marginal,
    fit_truncated_normal,
    lognormal_from_quartiles,
)

# --- IBM hexadecimal floating point -----------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"\x00\x00\x00\x00\x00\x00\x00\x00", None),   # missing
        (b"\x41\x10\x00\x00\x00\x00\x00\x00", 1.0),
        (b"\x41\x20\x00\x00\x00\x00\x00\x00", 2.0),
        (b"\x42\x64\x00\x00\x00\x00\x00\x00", 100.0),
        (b"\xc1\x10\x00\x00\x00\x00\x00\x00", -1.0),
        (b"\x41\x80\x00\x00\x00\x00\x00\x00", 8.0),
    ],
)
def test_known_ibm_floats_decode_correctly(raw, expected):
    result = ibm_to_double(raw)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, rel=1e-12)


def test_ibm_float_is_not_an_ieee_double():
    """Reading IBM bytes as IEEE gives a number, not an error — hence this test."""
    raw = b"\x41\x10\x00\x00\x00\x00\x00\x00"
    assert ibm_to_double(raw) == pytest.approx(1.0)
    assert struct.unpack(">d", raw)[0] != pytest.approx(1.0)


def test_short_fields_are_padded_not_misread():
    assert ibm_to_double(b"\x41\x10\x00\x00") == pytest.approx(1.0)


# --- NAMESTR parsing ---------------------------------------------------------------

def _namestr(name: str, label: str, *, numeric: bool, length: int, position: int) -> bytes:
    chunk = bytearray(b" " * NAMESTR_SIZE)
    chunk[0:2] = struct.pack(">h", 1 if numeric else 2)
    chunk[4:6] = struct.pack(">h", length)
    chunk[8:16] = name.ljust(8).encode()
    chunk[16:56] = label.ljust(40).encode()
    chunk[84:88] = struct.pack(">i", position)
    return bytes(chunk)


def test_namestr_fields_are_read_from_the_right_offsets():
    block = _namestr("SEQN", "Respondent sequence number", numeric=True, length=8,
                     position=0) + _namestr(
        "LBXGH", "Glycohemoglobin (%)", numeric=True, length=8, position=8)
    variables = _parse_namestrs(block, 2)

    assert [v.name for v in variables] == ["SEQN", "LBXGH"]
    assert [v.length for v in variables] == [8, 8]
    assert [v.position for v in variables] == [0, 8]
    assert variables[1].label == "Glycohemoglobin (%)"
    assert all(v.is_numeric for v in variables)


def test_character_variables_are_distinguished_from_numeric():
    block = _namestr("CODE", "A label", numeric=False, length=4, position=0)
    assert _parse_namestrs(block, 1)[0].is_numeric is False


# --- truncated-normal fitting ------------------------------------------------------

def test_fit_recovers_targets_the_naive_constructor_would_miss():
    target_mean, target_sd = 74.9, 19.64
    naive = Marginal("weight_kg", mean=target_mean, sd=target_sd, low=47.54, high=133.7)
    fitted = fit_truncated_normal(
        "weight_kg", target_mean=target_mean, target_sd=target_sd,
        low=47.54, high=133.7,
    )
    _, naive_sd = naive.moments()
    fitted_mean, fitted_sd = fitted.moments()

    assert fitted_mean == pytest.approx(target_mean, abs=0.01)
    assert fitted_sd == pytest.approx(target_sd, abs=0.01)
    # The naive construction is visibly off, which is the reason fitting exists.
    assert abs(naive_sd - target_sd) > abs(fitted_sd - target_sd)


def test_fit_refuses_unattainable_targets_rather_than_approximating():
    """Diabetic HbA1c is exactly this shape: mode at the bound, long upper tail."""
    with pytest.raises(ValueError, match="could not fit|strong skew"):
        fit_truncated_normal(
            "hba1c", target_mean=7.4, target_sd=1.501, low=6.5, high=12.64
        )


def test_fit_rejects_a_target_outside_its_bounds():
    with pytest.raises(ValueError, match="must lie inside"):
        fit_truncated_normal("x", target_mean=5.0, target_sd=1.0, low=10.0, high=20.0)


# --- log-normal marginals ----------------------------------------------------------

def test_lognormal_moments_match_an_empirical_sample():
    marginal = LogNormalMarginal("tg", median=100.0, sigma=0.5, low=30.0, high=400.0)
    analytic_mean, analytic_sd = marginal.moments()
    drawn = marginal.ppf(np.random.default_rng(0).uniform(1e-9, 1 - 1e-9, 200_000))
    assert analytic_mean == pytest.approx(float(drawn.mean()), rel=0.01)
    assert analytic_sd == pytest.approx(float(drawn.std()), rel=0.02)


def test_lognormal_fit_matches_the_truncated_median_not_the_raw_one():
    """The bound at 6.5 defines the diabetic population and removes ~25% of the fit."""
    fitted = lognormal_from_quartiles(
        "hba1c", median=7.4, q1=6.8, q3=8.8, low=6.5, high=12.64
    )
    realized_median = float(fitted.ppf(np.array([0.5]))[0])
    assert realized_median == pytest.approx(7.4, abs=0.01)
    # Solving post-truncation moves the location below the empirical median.
    assert fitted.median < 7.4


def test_lognormal_sigma_comes_from_the_quartile_ratio():
    fitted = lognormal_from_quartiles(
        "x", median=100.0, q1=70.0, q3=140.0, low=1.0, high=10_000.0
    )
    assert fitted.sigma == pytest.approx(math.log(140.0 / 70.0) / 1.3489795, rel=1e-6)


def test_lognormal_is_right_skewed():
    marginal = LogNormalMarginal("x", median=100.0, sigma=0.6, low=10.0, high=2000.0)
    mean, _ = marginal.moments()
    assert mean > 100.0, "a log-normal's mean sits above its median"


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"median": -1.0, "sigma": 0.5, "low": 1.0, "high": 10.0}, "positive support"),
        ({"median": 5.0, "sigma": 0.0, "low": 1.0, "high": 10.0}, "sigma must be"),
        ({"median": 5.0, "sigma": 0.5, "low": 10.0, "high": 1.0}, "low must be below"),
    ],
)
def test_invalid_lognormals_are_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        LogNormalMarginal("x", **kwargs)


def test_quartiles_must_be_ordered():
    with pytest.raises(ValueError, match="positive and ordered"):
        lognormal_from_quartiles("x", median=5.0, q1=9.0, q3=2.0, low=1.0, high=10.0)


def test_mixed_marginal_families_work_inside_one_joint_model():
    """The copula only calls ppf, which is what makes mixing families free."""
    from pkg.correlation.engine import JointModel

    model = JointModel(
        marginals=(
            Marginal("normal", 100.0, 15.0, 40.0, 160.0),
            LogNormalMarginal("skewed", median=100.0, sigma=0.5, low=30.0, high=400.0),
        ),
        correlations=(("normal", "skewed", 0.5),),
    )
    drawn = model.sample(np.random.default_rng(1), size=20_000)
    observed = float(np.corrcoef(drawn["normal"], drawn["skewed"])[0, 1])
    assert observed == pytest.approx(0.5, abs=0.04)
    assert float(np.median(drawn["skewed"])) == pytest.approx(100.0, rel=0.05)
