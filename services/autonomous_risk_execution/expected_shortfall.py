"""
Expected Shortfall (CVaR) Engine — conditional tail expectation.

Expected Shortfall = average loss in the worst (1-α)% of cases.

Unlike VaR (which only tells you the threshold), ES tells you the
expected loss when you exceed the threshold.

ES is a coherent risk measure:
    - Sub-additive: ES(A+B) ≤ ES(A) + ES(B) → diversification benefit
    - Monotonic, positively homogeneous, translation invariant
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Standard normal density at z_α
def normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


@dataclass
class ESResult:
    """Expected Shortfall computation result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    confidence: float = 0.95
    method: str = "HISTORICAL"
    es_value: float = 0.0
    es_pct: float = 0.0
    var_value: float = 0.0
    es_var_ratio: float = 0.0
    tail_observations: int = 0
    portfolio_value: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MultiESResult:
    """Multi-method ES comparison."""
    id: str = field(default_factory=lambda: str(uuid4()))
    historical_es: Optional[ESResult] = None
    parametric_es: Optional[ESResult] = None
    recommended_es: float = 0.0
    risk_level: str = "MODERATE"  # LOW, MODERATE, HIGH, CRITICAL
    timestamp: datetime = field(default_factory=datetime.now)


class ExpectedShortfallEngine:
    """
    Expected Shortfall computation engine.

    Methods:
        1. Historical ES — average of worst (1-α)% returns
        2. Parametric ES — σ * φ(z_α) / (1-α) - μ

    Risk classification:
        ES < 3%: LOW
        ES 3-6%: MODERATE
        ES 6-10%: HIGH
        ES > 10%: CRITICAL
    """

    def __init__(self, default_confidence: float = 0.95) -> None:
        self._default_confidence = default_confidence
        self._last_result: Optional[MultiESResult] = None

    async def historical_es(
        self,
        returns: list[float],
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
        var: float = 0.03,
    ) -> ESResult:
        """
        Compute historical Expected Shortfall.

        ES = average of returns worse than VaR threshold.
        """
        if not returns:
            return ESResult(confidence=confidence, method="HISTORICAL")

        sorted_returns = sorted(returns)
        cutoff = max(1, int(len(sorted_returns) * (1 - confidence)))
        tail = sorted_returns[:cutoff]

        if not tail:
            return ESResult(confidence=confidence, method="HISTORICAL")

        avg_tail = -sum(tail) / len(tail)
        var_threshold = -sorted_returns[cutoff - 1] if cutoff < len(sorted_returns) else -tail[-1]

        return ESResult(
            confidence=confidence,
            method="HISTORICAL",
            es_value=avg_tail * portfolio_value,
            es_pct=avg_tail,
            var_value=var_threshold,
            es_var_ratio=avg_tail / max(var_threshold, 0.0001),
            tail_observations=len(tail),
            portfolio_value=portfolio_value,
            timestamp=datetime.now(),
        )

    async def parametric_es(
        self,
        volatility: float,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
        mean_return: float = 0.0,
        z_value: float = 1.645,
    ) -> ESResult:
        """
        Compute parametric Expected Shortfall under normality.

        ES = σ * φ(z_α) / (1 - α) - μ

        Where φ(·) is the standard normal PDF.
        """
        phi = normal_pdf(z_value)
        es_pct = volatility * phi / (1 - confidence) - mean_return

        var_pct = -(mean_return - z_value * volatility)

        return ESResult(
            confidence=confidence,
            method="PARAMETRIC",
            es_value=es_pct * portfolio_value,
            es_pct=es_pct,
            var_value=var_pct,
            es_var_ratio=es_pct / max(var_pct, 0.0001),
            portfolio_value=portfolio_value,
            timestamp=datetime.now(),
        )

    async def compute(
        self,
        returns: Optional[list[float]] = None,
        volatility: float = 0.15,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
        var_value: Optional[float] = None,
    ) -> MultiESResult:
        """Compute ES using all available methods."""
        result = MultiESResult()

        # Historical ES
        if returns:
            result.historical_es = await self.historical_es(
                returns, confidence, portfolio_value, var_value or 0.03,
            )

        # Parametric ES
        result.parametric_es = await self.parametric_es(
            volatility, confidence, portfolio_value,
        )

        # Recommended: use historical if available, otherwise parametric
        es = result.historical_es.es_pct if result.historical_es else result.parametric_es.es_pct
        result.recommended_es = es

        # Risk level
        if es < 0.03:
            result.risk_level = "LOW"
        elif es < 0.06:
            result.risk_level = "MODERATE"
        elif es < 0.10:
            result.risk_level = "HIGH"
        else:
            result.risk_level = "CRITICAL"

        result.timestamp = datetime.now()
        self._last_result = result

        logger.info("ES: %.2f%% (%s risk)", es * 100, result.risk_level)
        return result

    def es_to_var_ratio(self, es: float, var: float) -> float:
        """Compute ES/VaR ratio — tail fatness indicator."""
        return es / max(var, 0.0001)

    @property
    def last_result(self) -> Optional[MultiESResult]:
        return self._last_result
