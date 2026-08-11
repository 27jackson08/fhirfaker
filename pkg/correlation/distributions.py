"""Marginal distributions and the normal transforms the copula needs.

scipy is deliberately not a dependency. It would pull ~30 MB into every install to
provide two functions, and "fast, dependency-light install" is one of the project's
stated differentiators (build doc Section 3). Both transforms are implemented from
published approximations and accuracy-tested in `tests/test_correlation.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

SQRT2 = math.sqrt(2.0)

# math.erf is correctly rounded; vectorizing it keeps the CDF exact rather than
# introducing a second approximation on top of the inverse's.
_erf = np.vectorize(math.erf, otypes=[float])


def standard_normal_cdf(z: np.ndarray | float) -> np.ndarray:
    """Phi(z)."""
    return 0.5 * (1.0 + _erf(np.asarray(z, dtype=float) / SQRT2))


# Acklam's inverse normal CDF approximation. Relative error < 1.15e-9 over the whole
# open interval, which is far below the precision at which labs report results.
_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
      1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
      6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
      -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
      3.754408661907416e00)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def standard_normal_ppf(u: np.ndarray | float) -> np.ndarray:
    """Phi^-1(u) for u strictly inside (0, 1)."""
    u = np.asarray(u, dtype=float)
    if np.any((u <= 0.0) | (u >= 1.0)):
        raise ValueError("standard_normal_ppf requires 0 < u < 1")

    out = np.empty_like(u)

    lower = u < _P_LOW
    upper = u > _P_HIGH
    central = ~(lower | upper)

    if np.any(central):
        q = u[central] - 0.5
        r = q * q
        num = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q
        den = ((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0
        out[central] = num / den

    for mask, sign, arg in ((lower, 1.0, u), (upper, -1.0, 1.0 - u)):
        if not np.any(mask):
            continue
        q = np.sqrt(-2.0 * np.log(arg[mask]))
        num = ((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]
        den = (((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0
        out[mask] = sign * num / den

    return out


def _standard_normal_pdf(z: float) -> float:
    """phi(z), needed for truncated-normal moments."""
    if not math.isfinite(z):
        return 0.0
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class Marginal:
    """A truncated-normal marginal for one analyte.

    Truncation bounds are physiological limits, not tuning knobs — they exist so a
    tail draw cannot emit a biologically impossible lab value. Keep them far enough
    out (>= ~3 SD) that they do not distort the moments the fidelity report checks.
    """

    name: str
    mean: float
    sd: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.sd <= 0:
            raise ValueError(f"{self.name}: sd must be positive, got {self.sd}")
        if self.low >= self.high:
            raise ValueError(f"{self.name}: low must be below high")
        if not self.low <= self.mean <= self.high:
            raise ValueError(f"{self.name}: mean {self.mean} outside [{self.low}, {self.high}]")

    def ppf(self, u: np.ndarray) -> np.ndarray:
        """Inverse CDF of the truncated normal, evaluated at uniforms `u`."""
        a = standard_normal_cdf((self.low - self.mean) / self.sd)
        b = standard_normal_cdf((self.high - self.mean) / self.sd)
        return self.mean + self.sd * standard_normal_ppf(a + np.asarray(u) * (b - a))

    def moments(self) -> tuple[float, float]:
        """Realized (mean, sd) *after* truncation.

        These differ from the nominal parameters whenever a bound sits near the mean,
        and the difference is not cosmetic: truncating HbA1c at the 6.5% diagnostic
        threshold pulls its SD from 0.90 down to 0.78, which inflates any regression
        slope calibrated against the nominal value by ~15%. Calibration must use these.
        """
        alpha = (self.low - self.mean) / self.sd
        beta = (self.high - self.mean) / self.sd
        phi_a, phi_b = _standard_normal_pdf(alpha), _standard_normal_pdf(beta)
        z = float(standard_normal_cdf(beta) - standard_normal_cdf(alpha))
        if z <= 0:
            raise ValueError(f"{self.name}: truncation bounds enclose no probability")

        lambda_ = (phi_a - phi_b) / z
        mean = self.mean + self.sd * lambda_
        variance = self.sd**2 * (
            1.0 + (alpha * phi_a - beta * phi_b) / z - lambda_**2
        )
        return mean, math.sqrt(max(variance, 0.0))


def correlation_from_r_squared(r_squared: float) -> float:
    """rho = sqrt(R^2) for a simple linear regression.

    Used to turn a published R^2 straight into a copula parameter, so the correlation
    is derived from the literature rather than hand-tuned to look plausible.
    """
    if not 0.0 <= r_squared <= 1.0:
        raise ValueError(f"r_squared must be in [0, 1], got {r_squared}")
    return math.sqrt(r_squared)


@lru_cache(maxsize=128)
def calibrate_latent_correlation(
    x: Marginal,
    y: Marginal,
    target_r_squared: float,
    *,
    samples: int = 50_000,
    seed: int = 0,
    tolerance: float = 1e-4,
) -> float:
    """Latent Gaussian correlation whose *realized* Pearson R^2 hits the target.

    Truncating a marginal attenuates the correlation that survives the copula
    transform: asking for rho = sqrt(0.84) yields a realized R^2 of about 0.827. The
    honest fix is to solve for the latent value rather than accept the gap or apply a
    hand-picked fudge factor.

    Deterministic by construction — fixed seed, fixed sample, bisection on a monotone
    function — so a profile's parameters do not drift between runs.
    """
    target_rho = math.sqrt(target_r_squared)
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(samples)
    independent = rng.standard_normal(samples)
    u_x = np.clip(standard_normal_cdf(base), 1e-12, 1.0 - 1e-12)
    x_values = x.ppf(u_x)

    def realized_r_squared(rho: float) -> float:
        partner = rho * base + math.sqrt(max(1.0 - rho * rho, 0.0)) * independent
        u_y = np.clip(standard_normal_cdf(partner), 1e-12, 1.0 - 1e-12)
        return float(np.corrcoef(x_values, y.ppf(u_y))[0, 1] ** 2)

    low, high = target_rho, min(0.99999, target_rho + 0.25)
    if realized_r_squared(high) < target_r_squared:
        return high  # attenuation too strong to correct; use the strongest available
    for _ in range(40):
        mid = 0.5 * (low + high)
        if realized_r_squared(mid) < target_r_squared:
            low = mid
        else:
            high = mid
        if high - low < tolerance:
            break
    return 0.5 * (low + high)


def sd_from_regression_slope(*, slope: float, predictor_sd: float, rho: float) -> float:
    """Response SD implied by an OLS slope: slope = rho * (sd_y / sd_x).

    Lets a profile fix the predictor's spread and have the response's spread follow
    from the published regression instead of being chosen independently.
    """
    if rho <= 0:
        raise ValueError(f"rho must be positive, got {rho}")
    return slope * predictor_sd / rho
