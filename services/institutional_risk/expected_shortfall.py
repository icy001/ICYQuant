"""ExpectedShortfall — Expected Shortfall (CVaR) computation.

ES answers: "Beyond VaR, how bad is the average loss?"
This is critical because VaR alone doesn't describe tail severity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExpectedShortfallResult:
    """Expected Shortfall result at multiple confidence levels."""

    es_95: float = 0.0
    es_99: float = 0.0
    es_995: float = 0.0
    es_999: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    tail_ratio: float = 0.0  # ES_99 / VaR_99 — tail fatness measure
    method: str = "historical"
    sample_size: int = 0
    tail_count_95: int = 0
    tail_count_99: int = 0
    worst_loss: float = 0.0
    tail_losses_99: List[float] = field(default_factory=list)


class ExpectedShortfallEngine:
    """Expected Shortfall (CVaR) computation engine.

    ES = E[Loss | Loss > VaR_α]

    Usage::

        engine = ExpectedShortfallEngine()
        result = engine.compute(daily_returns)
        print(f"ES 99%: {result.es_99:.0f} vs VaR 99%: {result.var_99:.0f}")
        print(f"Tail Ratio: {result.tail_ratio:.2f}")  # >1 means fatter tails
    """

    def compute(
        self,
        returns: List[float],
        confidence_levels: Optional[List[float]] = None,
        method: str = "historical",
    ) -> ExpectedShortfallResult:
        """Compute Expected Shortfall for given confidence levels.

        Args:
            returns: list of returns (losses as positive, gains as negative)
            confidence_levels: e.g., [0.95, 0.99, 0.995, 0.999]
            method: "historical" or "parametric"
        """
        if not returns:
            return ExpectedShortfallResult()

        n = len(returns)
        sorted_returns = sorted(returns)

        # confidence levels
        levels = confidence_levels or [0.95, 0.99, 0.995, 0.999]

        def es_at(conf: float) -> tuple[float, int]:
            """Compute ES at given confidence level."""
            tail_size = int(n * (1 - conf))
            if tail_size == 0:
                return 0.0, 0
            tail = sorted_returns[:tail_size]
            return abs(sum(tail) / len(tail)), tail_size

        es_95, tc_95 = es_at(0.95)
        es_99, tc_99 = es_at(0.99)
        es_995, _ = es_at(0.995)
        es_999, _ = es_at(0.999)

        # VaR for comparison
        var_95 = abs(sorted_returns[max(0, int(n * 0.05))])
        var_99 = abs(sorted_returns[max(0, int(n * 0.01))])

        # tail ratio: ES / VaR — measures tail fatness
        tail_ratio = es_99 / var_99 if var_99 > 0 else 0.0

        # worst 1% losses
        tail_losses_99 = sorted_returns[:max(1, tc_99)]

        return ExpectedShortfallResult(
            es_95=es_95,
            es_99=es_99,
            es_995=es_995,
            es_999=es_999,
            var_95=var_95,
            var_99=var_99,
            tail_ratio=tail_ratio,
            method=method,
            sample_size=n,
            tail_count_95=tc_95,
            tail_count_99=tc_99,
            worst_loss=abs(sorted_returns[0]) if sorted_returns else 0.0,
            tail_losses_99=tail_losses_99,
        )

    def compute_parametric(
        self,
        mu: float,
        sigma: float,
        confidence_levels: Optional[List[float]] = None,
    ) -> ExpectedShortfallResult:
        """Compute ES under normal distribution assumption (parametric).

        For normal distribution:
            ES_α = μ + σ * φ(Φ⁻¹(α)) / (1-α)
        where φ is PDF and Φ⁻¹ is inverse CDF (quantile).
        """
        import math

        def normal_es(confidence: float) -> float:
            """ES for normal distribution at given confidence."""
            from services.institutional_risk.var_engine import VaREngine
            z = VaREngine.Z_SCORES.get(confidence, 2.3263)
            # φ(z) / (1-α)
            phi = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
            return mu + sigma * phi / (1 - confidence)

        levels = confidence_levels or [0.95, 0.99]
        result = ExpectedShortfallResult(method="parametric")

        if 0.95 in levels:
            result.es_95 = abs(normal_es(0.95))
        if 0.99 in levels:
            result.es_99 = abs(normal_es(0.99))
        if 0.995 in levels:
            result.es_995 = abs(normal_es(0.995))

        # VaR for comparison
        from services.institutional_risk.var_engine import VaREngine
        result.var_95 = abs(mu - VaREngine.Z_SCORES[0.95] * sigma)
        result.var_99 = abs(mu - VaREngine.Z_SCORES[0.99] * sigma)
        result.tail_ratio = result.es_99 / result.var_99 if result.var_99 > 0 else 0.0

        return result

    def compare_methods(
        self,
        returns: List[float],
    ) -> Dict[str, ExpectedShortfallResult]:
        """Compare historical vs parametric ES for same data."""
        return {
            "historical": self.compute(returns, method="historical"),
            "parametric": self.compute_parametric(
                mu=sum(returns) / len(returns) if returns else 0.0,
                sigma=(
                    (sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
                    if len(returns) > 1 else 0.0
                ),
            ),
        }
