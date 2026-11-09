"""Statistical Significance & Hypothesis Testing Engine (Layer 11: Evaluation & Quality, Feature 11.21)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SignificanceResult:
    """Outcome of statistical hypothesis test between variant A and variant B."""
    mean_a: float
    mean_b: float
    difference: float
    p_value: float
    is_significant: bool
    confidence_level: float
    sample_size_a: int
    sample_size_b: int
    recommendation: str


def _approx_erf(x: float) -> float:
    """Approximation of the error function (Abramowitz and Stegun)."""
    # constants
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return sign * y


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + _approx_erf(z / math.sqrt(2.0)))


def calculate_significance(
    samples_a: List[float],
    samples_b: List[float],
    confidence_level: float = 0.95,
) -> SignificanceResult:
    """Computes two-sample z-test / Welch's test for difference between treatment B and control A."""
    na = len(samples_a)
    nb = len(samples_b)

    if na < 2 or nb < 2:
        return SignificanceResult(
            mean_a=samples_a[0] if na else 0.0,
            mean_b=samples_b[0] if nb else 0.0,
            difference=0.0,
            p_value=1.0,
            is_significant=False,
            confidence_level=confidence_level,
            sample_size_a=na,
            sample_size_b=nb,
            recommendation="Insufficient samples for statistical significance.",
        )

    ma = sum(samples_a) / na
    mb = sum(samples_b) / nb
    diff = mb - ma

    var_a = sum((x - ma) ** 2 for x in samples_a) / (na - 1)
    var_b = sum((x - mb) ** 2 for x in samples_b) / (nb - 1)

    se = math.sqrt((var_a / na) + (var_b / nb))
    if se == 0:
        p_val = 1.0 if diff == 0 else 0.0
    else:
        z = abs(diff) / se
        # Two-tailed p-value
        p_val = 2.0 * (1.0 - _normal_cdf(z))

    alpha = 1.0 - confidence_level
    is_sig = p_val < alpha

    rec = (
        f"Statistically significant change detected (p={p_val:.4f} < {alpha:.2f})."
        if is_sig
        else f"No statistically significant difference (p={p_val:.4f} >= {alpha:.2f})."
    )

    return SignificanceResult(
        mean_a=round(ma, 4),
        mean_b=round(mb, 4),
        difference=round(diff, 4),
        p_value=round(p_val, 4),
        is_significant=is_sig,
        confidence_level=confidence_level,
        sample_size_a=na,
        sample_size_b=nb,
        recommendation=rec,
    )

