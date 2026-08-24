"""Marginal distributions and the normal transforms the copula needs.

scipy is deliberately not a dependency. It would pull ~30 MB into every install to
provide two functions, and "fast, dependency-light install" is one of the project's
stated differentiators (build doc Section 3). Both transforms are implemented from
published approximations and accuracy-tested in `tests/test_correlation.py`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
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


@dataclass(frozen=True)
class LogNormalMarginal:
    """A truncated log-normal marginal, for right-skewed analytes.

    Diabetic HbA1c and triglycerides have a mode near their lower bound and a long
    upper tail. `fit_truncated_normal` refuses them outright rather than returning a
    poor fit, which is the correct behaviour and also the reason this type exists.

    Parameterised by the median (exp(mu), a natural centre for a skewed quantity) and
    the log-scale sigma, which is recovered from the quartile ratio:
    sigma = ln(Q3/Q1) / 1.349.

    The Gaussian copula in `engine.py` only needs `ppf`, so mixing marginal families
    inside one joint model costs nothing — which is why a copula was chosen over
    ad-hoc conditional rules in the first place.
    """

    name: str
    median: float
    sigma: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.median <= 0 or self.low <= 0:
            raise ValueError(f"{self.name}: log-normal requires positive support")
        if self.sigma <= 0:
            raise ValueError(f"{self.name}: sigma must be positive")
        if not self.low < self.high:
            raise ValueError(f"{self.name}: low must be below high")

    @property
    def mu(self) -> float:
        return math.log(self.median)

    def _bounds(self) -> tuple[float, float]:
        return (
            (math.log(self.low) - self.mu) / self.sigma,
            (math.log(self.high) - self.mu) / self.sigma,
        )

    def ppf(self, u: np.ndarray) -> np.ndarray:
        alpha, beta = self._bounds()
        a = standard_normal_cdf(alpha)
        b = standard_normal_cdf(beta)
        return np.exp(self.mu + self.sigma * standard_normal_ppf(a + np.asarray(u) * (b - a)))

    def moments(self) -> tuple[float, float]:
        """Analytic mean and SD of the truncated log-normal."""
        alpha, beta = self._bounds()
        z = float(standard_normal_cdf(beta) - standard_normal_cdf(alpha))
        if z <= 0:
            raise ValueError(f"{self.name}: truncation bounds enclose no probability")

        def shifted(k: int) -> float:
            return float(
                standard_normal_cdf(beta - k * self.sigma)
                - standard_normal_cdf(alpha - k * self.sigma)
            )

        first = math.exp(self.mu + self.sigma**2 / 2) * shifted(1) / z
        second = math.exp(2 * self.mu + 2 * self.sigma**2) * shifted(2) / z
        return first, math.sqrt(max(second - first**2, 0.0))


_NORMAL_QUARTILE = 0.6744897501960817


def lognormal_from_quartiles(
    name: str,
    *,
    median: float,
    q1: float,
    q3: float,
    low: float,
    high: float,
    iterations: int = 200,
    tolerance: float = 1e-9,
) -> LogNormalMarginal:
    """Fit a log-normal whose *truncated* median matches the empirical one.

    Sigma comes from the quartile ratio, which is robust as long as both quartiles
    sit inside the bounds. The location then has to be solved rather than set to the
    empirical median: truncating diabetic HbA1c at 6.5 removes about a quarter of the
    fitted distribution's lower tail, which dragged the realized median from 7.4 up
    to 7.8. Anywhere the bound is a population definition rather than a rare-value
    guard, this correction matters.
    """
    if not 0 < q1 < q3:
        raise ValueError(f"{name}: quartiles must be positive and ordered")
    if not low < median < high:
        raise ValueError(f"{name}: median {median} must lie inside ({low}, {high})")

    sigma = math.log(q3 / q1) / (2 * _NORMAL_QUARTILE)
    location = median
    for _ in range(iterations):
        candidate = LogNormalMarginal(
            name=name, median=location, sigma=sigma, low=low, high=high
        )
        realized = float(candidate.ppf(np.array([0.5]))[0])
        if abs(realized - median) < tolerance:
            return candidate
        # Both the location and the realized median are log-scale quantities, so
        # correcting multiplicatively converges far faster than an additive step.
        location *= median / realized
        if not low < location < high:
            break
    raise ValueError(
        f"{name}: could not fit a log-normal with truncated median {median} inside "
        f"[{low}, {high}] at sigma {sigma:.4g}"
    )


@dataclass(frozen=True)
class EmpiricalMarginal:
    """A marginal defined by measured quantiles, with no distributional family.

    Why this exists
    ---------------
    `Marginal` and `LogNormalMarginal` are both fitted from the median and the IQR, so
    both reproduce the middle of the distribution and both miss the same tail. Measured
    on NHANES nondiabetic glucose, the shipped normal put 18.9% of women above
    100 mg/dL against a true 22.7%, and the log-normal fitted from the same quartiles
    gave 18.6% — the wrong direction. For ALT the normal gave 0.1% above 40 U/L against
    a true 5.5%. A right-skewed analyte's 97.5th percentile can sit 2.6 IQRs above its
    median where a normal puts it at 1.45, and no two-parameter family fitted to
    quartiles spans that.

    So this one assumes nothing and interpolates the measured quantile function. Errors
    against the true exceedance rate across ten analyte/sex cells, mean absolute:

        shipped normal 4.44 points     5-knot 4.50     **9-knot 0.83**     13-knot 0.93

    Five knots is *worse* than the normal on heavy skew — linear interpolation across a
    wide q3-to-p97.5 gap spreads mass uniformly where the real density is falling, which
    overshot ALT to 12.1% against a true 5.5%. The knot grid is part of the method, not
    an implementation detail.

    Semantics
    ---------
    `probs` are the quantile levels the values were measured at, and the support is
    exactly [values[0], values[-1]] — the same truncation `Marginal` applies at
    p2.5/p97.5. Probabilities are rescaled onto [0, 1] so the endpoints carry no point
    mass, which a naive `np.interp` against un-normalised levels would create.
    """

    name: str
    probs: tuple[float, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.probs) != len(self.values):
            raise ValueError(f"{self.name}: probs and values differ in length")
        if len(self.probs) < 3:
            raise ValueError(f"{self.name}: need at least 3 quantiles, got {len(self.probs)}")
        if any(b <= a for a, b in zip(self.probs, self.probs[1:], strict=False)):
            raise ValueError(f"{self.name}: probs must be strictly increasing")
        if any(b < a for a, b in zip(self.values, self.values[1:], strict=False)):
            raise ValueError(f"{self.name}: values must be non-decreasing")
        if not 0.0 < self.probs[0] < self.probs[-1] < 1.0:
            raise ValueError(f"{self.name}: probs must lie strictly inside (0, 1)")

    @property
    def _unit_probs(self) -> np.ndarray:
        p = np.asarray(self.probs, dtype=float)
        return (p - p[0]) / (p[-1] - p[0])

    def ppf(self, u: np.ndarray) -> np.ndarray:
        return np.interp(np.asarray(u), self._unit_probs, np.asarray(self.values, dtype=float))

    def moments(self) -> tuple[float, float]:
        """Realized (mean, sd) of the piecewise-linear quantile function.

        Integrated in closed form rather than sampled, so the fidelity suite compares
        against an exact figure. On a segment where Q rises linearly from x to y over a
        probability width d, the contributions are d(x+y)/2 and d(x^2+xy+y^2)/3.
        """
        p, x = self._unit_probs, np.asarray(self.values, dtype=float)
        width = np.diff(p)
        lo, hi = x[:-1], x[1:]
        mean = float(np.sum(width * (lo + hi) / 2.0))
        second = float(np.sum(width * (lo**2 + lo * hi + hi**2) / 3.0))
        variance = max(second - mean**2, 0.0)
        return mean, float(np.sqrt(variance))


def empirical_from_quantiles(
    name: str, quantiles: dict[float, float] | Sequence[tuple[float, float]]
) -> EmpiricalMarginal:
    """Build an `EmpiricalMarginal` from measured (level, value) pairs."""
    pairs = sorted(quantiles.items() if isinstance(quantiles, dict) else quantiles)
    return EmpiricalMarginal(
        name=name,
        probs=tuple(float(p) for p, _ in pairs),
        values=tuple(float(v) for _, v in pairs),
    )


# A joint model may mix families: the copula only ever calls `ppf`, so a skewed
# analyte can use a log-normal or a measured quantile grid while its neighbours stay
# normal.
AnyMarginal = Marginal | LogNormalMarginal | EmpiricalMarginal


def fit_truncated_normal(
    name: str,
    *,
    target_mean: float,
    target_sd: float,
    low: float,
    high: float,
    iterations: int = 200,
    tolerance: float = 1e-6,
) -> Marginal:
    """Solve for the Marginal whose *truncated* moments match the targets.

    Passing an empirical mean and SD straight into `Marginal` sets the parameters of
    the untruncated normal, not of the distribution that actually gets sampled. When
    a bound sits near the centre the two diverge badly: NHANES puts diabetic HbA1c at
    a median of 7.4 with the 2.5th centile at 6.5, and using those directly produced
    a realized median of 7.85 with two-thirds of the intended spread.

    Fixed-point iteration on (mean, sd) — the map is a contraction here, and the
    result is deterministic, so calibrated marginals do not drift between runs.
    """
    if not low < target_mean < high:
        raise ValueError(
            f"{name}: target mean {target_mean} must lie inside ({low}, {high})"
        )
    mean, sd = target_mean, target_sd
    for _ in range(iterations):
        candidate = Marginal(name, mean=min(max(mean, low + 1e-9), high - 1e-9),
                             sd=max(sd, 1e-9), low=low, high=high)
        realized_mean, realized_sd = candidate.moments()
        mean_error = target_mean - realized_mean
        sd_ratio = target_sd / realized_sd if realized_sd > 0 else 1.0
        if abs(mean_error) < tolerance and abs(sd_ratio - 1.0) < tolerance:
            return candidate
        mean += mean_error
        sd *= sd_ratio
    raise ValueError(
        f"{name}: could not fit a truncated normal with mean {target_mean} and sd "
        f"{target_sd} inside [{low}, {high}]. The targets are probably not "
        "attainable for this shape — check for strong skew."
    )


def correlation_from_r_squared(r_squared: float) -> float:
    """rho = sqrt(R^2) for a simple linear regression.

    Used to turn a published R^2 straight into a copula parameter, so the correlation
    is derived from the literature rather than hand-tuned to look plausible.
    """
    if not 0.0 <= r_squared <= 1.0:
        raise ValueError(f"r_squared must be in [0, 1], got {r_squared}")
    return math.sqrt(r_squared)


@lru_cache(maxsize=128)
def sd_from_regression_slope(*, slope: float, predictor_sd: float, rho: float) -> float:
    """Response SD implied by an OLS slope: slope = rho * (sd_y / sd_x).

    Lets a profile fix the predictor's spread and have the response's spread follow
    from the published regression instead of being chosen independently.
    """
    if rho <= 0:
        raise ValueError(f"rho must be positive, got {rho}")
    return slope * predictor_sd / rho


# Gauss-Hermite nodes for the bivariate integral below. 64 is comfortably past the
# point where adding nodes stops moving the answer for these marginals, and the whole
# grid is 4096 evaluations — cheaper than one Monte Carlo estimate and, unlike one,
# exactly reproducible.
_GH_NODES = 64


@lru_cache(maxsize=4)
def _hermite(nodes: int) -> tuple[np.ndarray, np.ndarray]:
    x, w = np.polynomial.hermite.hermgauss(nodes)
    return x, w


def realized_pearson(x: AnyMarginal, y: AnyMarginal, rho: float, *, nodes: int = _GH_NODES) -> float:
    """Pearson correlation that a Gaussian copula with latent `rho` actually produces.

    Computed by two-dimensional Gauss-Hermite quadrature rather than by sampling. A
    Monte Carlo estimate over 30,000 draws carries a standard error near 0.006, which is
    the same size as the attenuation being corrected — the estimator would have been the
    dominant error term. Quadrature has no such floor and returns the same number every
    time.
    """
    u, w = _hermite(nodes)
    root2 = math.sqrt(2.0)
    z1 = root2 * u
    fx = x.ppf(np.clip(standard_normal_cdf(z1), 1e-12, 1.0 - 1e-12))

    # z2 | z1 for a standard bivariate normal with correlation rho.
    z2 = rho * z1[:, None] + math.sqrt(max(1.0 - rho * rho, 0.0)) * (root2 * u)[None, :]
    fy = y.ppf(np.clip(standard_normal_cdf(z2), 1e-12, 1.0 - 1e-12))

    weights = np.outer(w, w) / math.pi
    marginal_w = w / math.sqrt(math.pi)

    mean_x = float(fx @ marginal_w)
    mean_y = float((weights * fy).sum())
    second_x = float((fx**2) @ marginal_w)
    second_y = float((weights * fy**2).sum())
    cross = float((weights * fx[:, None] * fy).sum())

    var_x = max(second_x - mean_x**2, 0.0)
    var_y = max(second_y - mean_y**2, 0.0)
    if var_x <= 0.0 or var_y <= 0.0:
        return 0.0
    return (cross - mean_x * mean_y) / math.sqrt(var_x * var_y)


def latent_for_pearson(
    x: AnyMarginal,
    y: AnyMarginal,
    target: float,
    *,
    tolerance: float = 1e-4,
    iterations: int = 60,
) -> float:
    """Latent Gaussian correlation whose *realized* Pearson correlation hits `target`.

    This replaced `calibrate_latent_correlation`, which solved the same problem for a
    positive R^2 by searching upward from sqrt(R^2). That could not serve a signed
    target: half the dependence in this package is negative — weight against HDL at
    -0.26, triglycerides against HDL at -0.43 — and an upward-only search has no meaning
    there. The old function is gone rather than deprecated, because leaving two solvers
    in place is how the ADAG pair came to be corrected twice.

    Why it is needed: a Gaussian copula's latent correlation is attenuated by the
    marginal transform, always toward zero, and the more skewed or truncated the
    marginals the larger the gap. Measured across the 32 configured pairs before this
    existed, realized values sat a mean 0.0086 below their targets and 0.0298 at worst,
    every one toward zero — systematic under-correlation rather than noise.
    """
    if not -1.0 < target < 1.0:
        raise ValueError(f"target correlation {target} must lie in (-1, 1)")
    if target == 0.0:
        return 0.0

    limit = 0.99999
    lo, hi = (target, limit) if target > 0 else (-limit, target)
    extreme = hi if target > 0 else lo
    if abs(realized_pearson(x, y, extreme)) < abs(target):
        # Attenuation too strong to correct even at the extreme. Return the strongest
        # available rather than silently pretending the target was met.
        return extreme

    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        value = realized_pearson(x, y, mid)
        if abs(value - target) <= tolerance:
            return mid
        if value < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
