"""Gaussian copula joint sampling.

This is the stochastic half of the correlation engine (build doc Section 8). Analytes
are drawn *jointly* from a correlation structure rather than independently per field,
which is what stops a bundle from pairing a diabetic Condition with a healthy HbA1c.

A copula rather than ad-hoc if-then rules: each analyte's marginal is specified on its
own (where reference-interval knowledge lives) and the dependence is specified
separately as a correlation matrix. That scales to N analytes without writing N^2
special cases, and the correlations can be taken straight from published regressions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from carebundle.correlation.distributions import AnyMarginal, standard_normal_cdf

# Below this, a correlation matrix is treated as non-positive-definite. Cholesky on a
# matrix that is merely near-singular yields silently wrong dependence.
_MIN_EIGENVALUE = 1e-10


@dataclass(frozen=True)
class JointModel:
    """Marginals plus the correlation structure linking them."""

    marginals: tuple[AnyMarginal, ...]
    correlations: tuple[tuple[str, str, float], ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(m.name for m in self.marginals)

    def correlation_matrix(self) -> np.ndarray:
        index = {name: i for i, name in enumerate(self.names)}
        size = len(self.marginals)
        matrix = np.eye(size)
        for left, right, rho in self.correlations:
            if left not in index or right not in index:
                raise KeyError(
                    f"correlation ({left}, {right}) names an analyte not in this model: "
                    f"{self.names}"
                )
            if not -1.0 <= rho <= 1.0:
                raise ValueError(f"correlation ({left}, {right}) = {rho} is out of range")
            i, j = index[left], index[right]
            matrix[i, j] = matrix[j, i] = rho

        smallest = float(np.linalg.eigvalsh(matrix).min())
        if smallest < _MIN_EIGENVALUE:
            raise ValueError(
                "correlation matrix is not positive definite "
                f"(smallest eigenvalue {smallest:.3g}). The requested correlations are "
                "mutually inconsistent — no joint distribution satisfies all of them."
            )
        return matrix

    def sample(self, rng: np.random.Generator, size: int = 1) -> dict[str, np.ndarray]:
        """Draw `size` jointly-distributed observations.

        Gaussian copula: correlated standard normals -> uniforms via Phi -> each
        analyte's own inverse CDF. The uniform step is what lets marginals and
        dependence be specified independently.
        """
        matrix = self.correlation_matrix()
        cholesky = np.linalg.cholesky(matrix)
        latent = rng.standard_normal((size, len(self.marginals))) @ cholesky.T
        uniforms = standard_normal_cdf(latent)

        # Phi can round to exactly 0 or 1 in the far tails; the inverse CDF is
        # undefined there, so nudge inside the open interval.
        uniforms = np.clip(uniforms, 1e-12, 1.0 - 1e-12)

        return {
            marginal.name: marginal.ppf(uniforms[:, i])
            for i, marginal in enumerate(self.marginals)
        }

    def sample_one(self, rng: np.random.Generator) -> dict[str, float]:
        drawn = self.sample(rng, size=1)
        return {name: float(values[0]) for name, values in drawn.items()}
