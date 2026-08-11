"""
Factor Risk Engine — factor-level risk decomposition and exposure analysis.

Ensures strategy diversification actually translates to risk diversification:
    Strategy Diversification ≠ Factor Risk Diversification

Monitors:
    - Factor exposures (Momentum, Growth, Quality, Value, Volatility, etc.)
    - Factor covariance
    - Factor risk contribution
    - Overlapping factor bets across strategies
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    """Exposure to a single factor."""
    factor: str
    exposure: float = 0.0
    risk_contribution: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.5
    status: str = "NEUTRAL"  # LONG, SHORT, NEUTRAL, EXTREME


@dataclass
class FactorRiskProfile:
    """Complete factor risk profile."""
    id: str = field(default_factory=lambda: str(uuid4()))
    exposures: dict[str, FactorExposure] = field(default_factory=dict)
    total_factor_risk: float = 0.0
    idiosyncratic_risk: float = 0.0
    diversification_ratio: float = 0.0
    dominant_factor: str = ""
    factor_concentration: float = 0.0
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


# Standard factor taxonomy
STANDARD_FACTORS = [
    "MOMENTUM", "GROWTH", "QUALITY", "VALUE", "VOLATILITY",
    "SIZE", "LIQUIDITY", "LEVERAGE", "DIVIDEND_YIELD",
    "PROFITABILITY", "INVESTMENT", "EARNINGS_QUALITY",
]


class FactorRiskEngine:
    """
    Factor-level risk analysis and decomposition.

    Core question: Are multiple strategies all betting on the same factor?

    Example:
        Portfolio holds NVDA, AMD, AVGO → all MOMENTUM + GROWTH
        Even though they are different stocks, factor risk is concentrated.

    Key metrics:
        - Factor HHI (concentration across factors)
        - Factor risk contribution (% of total risk from each factor)
        - Dominant factor identification
    """

    def __init__(self, max_factor_exposure: float = 0.60) -> None:
        self._max_factor_exposure = max_factor_exposure
        self._last_profile: Optional[FactorRiskProfile] = None

    async def analyze(
        self,
        factor_exposures: dict[str, float],
        factor_cov: Optional[dict[str, dict[str, float]]] = None,
    ) -> FactorRiskProfile:
        """
        Analyze factor risk for a portfolio.

        Args:
            factor_exposures: {factor_name: exposure}
            factor_cov: Optional factor covariance matrix
        """
        profile = FactorRiskProfile()
        total_abs = sum(abs(v) for v in factor_exposures.values()) or 1.0

        for factor, exposure in factor_exposures.items():
            fe = FactorExposure(
                factor=factor,
                exposure=exposure,
                risk_contribution=abs(exposure) / total_abs,
                status=self._classify_exposure(exposure),
            )
            profile.exposures[factor] = fe

            if abs(exposure) > self._max_factor_exposure:
                profile.warnings.append(
                    f"Factor {factor} exposure {exposure:.2f} exceeds limit "
                    f"{self._max_factor_exposure:.2f}"
                )

        # Factor concentration (HHI)
        if factor_exposures:
            weights = [abs(v) / total_abs for v in factor_exposures.values()]
            hhi = sum(w * w for w in weights)
            profile.factor_concentration = hhi
            profile.diversification_ratio = 1.0 / max(hhi, 0.01) / len(factor_exposures)

        # Dominant factor
        if factor_exposures:
            profile.dominant_factor = max(
                factor_exposures, key=lambda k: abs(factor_exposures[k])
            )

        # Factor risk with covariance
        if factor_cov:
            factor_var = 0.0
            for f1, e1 in factor_exposures.items():
                for f2, e2 in factor_exposures.items():
                    cov = factor_cov.get(f1, {}).get(f2, 0)
                    factor_var += e1 * e2 * cov
            profile.total_factor_risk = max(0, factor_var) ** 0.5

        profile.timestamp = datetime.now()
        self._last_profile = profile

        if profile.warnings:
            logger.warning("Factor risk: %d warnings, dominant=%s",
                          len(profile.warnings), profile.dominant_factor)
        return profile

    def _classify_exposure(self, exposure: float) -> str:
        """Classify factor exposure level."""
        if exposure > 0.7:
            return "EXTREME_LONG"
        elif exposure > 0.3:
            return "LONG"
        elif exposure < -0.7:
            return "EXTREME_SHORT"
        elif exposure < -0.3:
            return "SHORT"
        return "NEUTRAL"

    def compute_factor_var(
        self,
        exposures: dict[str, float],
        factor_cov: dict[str, dict[str, float]],
    ) -> float:
        """Compute factor-level VaR."""
        factor_var = 0.0
        for f1, e1 in exposures.items():
            for f2, e2 in exposures.items():
                cov = factor_cov.get(f1, {}).get(f2, 0)
                factor_var += e1 * e2 * cov
        return max(0, factor_var) ** 0.5 * 1.645

    @property
    def last_profile(self) -> Optional[FactorRiskProfile]:
        return self._last_profile
