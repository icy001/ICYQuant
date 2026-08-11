"""
Factor Exposure Engine — Multi-factor risk exposure monitoring.

Monitors portfolio exposure to common risk factors (Momentum, Value,
Growth, Size, Quality, Volatility) and detects concentrated factor
bets that could lead to systematic risk.

Architecture::

    Positions → Factor Loadings → Portfolio Factor Exposure → Risk Limits
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Standard risk factor definitions
STANDARD_FACTORS = [
    "momentum",
    "value",
    "growth",
    "size",
    "quality",
    "volatility",
    "liquidity",
    "leverage",
    "dividend_yield",
    "beta",
]


@dataclass
class FactorExposure:
    """Exposure to a single risk factor."""
    factor_name: str
    exposure: float
    contribution_pct: float = 0.0
    risk_contribution: float = 0.0
    z_score: float = 0.0
    status: str = "NORMAL"  # NORMAL, ELEVATED, EXTREME


@dataclass
class FactorExposureReport:
    """Complete factor exposure report for a portfolio."""
    account_id: str
    total_equity: float = 0.0
    exposures: dict[str, FactorExposure] = field(default_factory=dict)
    factor_risk_score: float = 0.0
    risk_level: str = "LOW"
    dominant_factors: list[str] = field(default_factory=list)
    diversification_score: float = 100.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "total_equity": self.total_equity,
            "exposures": {
                name: {
                    "exposure": e.exposure,
                    "contribution_pct": e.contribution_pct,
                    "risk_contribution": e.risk_contribution,
                    "z_score": e.z_score,
                    "status": e.status,
                }
                for name, e in self.exposures.items()
            },
            "factor_risk_score": self.factor_risk_score,
            "risk_level": self.risk_level,
            "dominant_factors": self.dominant_factors,
            "diversification_score": self.diversification_score,
        }


class FactorExposureEngine:
    """
    Multi-factor risk exposure monitoring engine.

    Computes portfolio exposure to common risk factors, detects
    concentrated factor bets, and provides diversification scoring.

    Usage::

        engine = FactorExposureEngine()
        await engine.initialize()

        report = await engine.compute("ACC-01", positions, factor_loadings)
    """

    def __init__(
        self,
        max_exposure_per_factor: float = 2.0,
        max_abs_z_score: float = 2.5,
    ) -> None:
        self._max_exposure = max_exposure_per_factor
        self._max_z_score = max_abs_z_score
        self._lock = asyncio.Lock()
        self._initialized = False

        # Default factor benchmarks (mean, std for z-score)
        self._factor_benchmarks: dict[str, tuple[float, float]] = {
            "momentum": (0.0, 0.5),
            "value": (0.0, 0.5),
            "growth": (0.0, 0.5),
            "size": (0.0, 0.5),
            "quality": (0.0, 0.5),
            "volatility": (0.0, 0.5),
            "liquidity": (0.0, 0.5),
            "leverage": (0.0, 0.5),
            "dividend_yield": (0.0, 0.5),
            "beta": (1.0, 0.3),
        }

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the factor exposure engine."""
        self._initialized = True
        logger.info("FactorExposureEngine initialized.")

    async def stop(self) -> None:
        """Stop the factor exposure engine."""
        self._initialized = False
        logger.info("FactorExposureEngine stopped.")

    # ---- Core API ----

    async def compute(
        self,
        account_id: str,
        positions: dict[str, dict[str, Any]],
        total_equity: float,
        factor_loadings: Optional[dict[str, dict[str, float]]] = None,
    ) -> FactorExposureReport:
        """
        Compute portfolio factor exposures.

        Args:
            account_id: Account identifier.
            positions: Dict of symbol → {weight, market_value, ...}
            total_equity: Total portfolio equity.
            factor_loadings: Optional dict of symbol → {factor: loading}.

        Returns FactorExposureReport with full analysis.
        """
        if total_equity <= 0:
            return FactorExposureReport(account_id=account_id)

        # Compute position weights
        weights: dict[str, float] = {}
        for symbol, pos in positions.items():
            mv = pos.get("market_value", 0)
            weights[symbol] = mv / total_equity if total_equity > 0 else 0.0

        # Aggregate factor exposures
        raw_exposures: dict[str, float] = {f: 0.0 for f in STANDARD_FACTORS}

        if factor_loadings:
            for symbol, weight in weights.items():
                symbol_factors = factor_loadings.get(symbol, {})
                for factor, loading in symbol_factors.items():
                    if factor in raw_exposures:
                        raw_exposures[factor] += weight * loading

        exposures: dict[str, FactorExposure] = {}
        risk_score = 0.0
        max_exposure = max(abs(v) for v in raw_exposures.values()) if raw_exposures else 1.0

        for factor_name, exposure in raw_exposures.items():
            benchmarks = self._factor_benchmarks.get(factor_name, (0.0, 1.0))
            mean, std = benchmarks
            z_score = (exposure - mean) / std if std > 0 else 0.0

            # Status
            if abs(z_score) > self._max_z_score:
                status = "EXTREME"
            elif abs(z_score) > self._max_z_score * 0.7:
                status = "ELEVATED"
            else:
                status = "NORMAL"

            # Contribution
            contribution = (abs(exposure) / max_exposure * 100) if max_exposure > 0 else 0.0

            exposures[factor_name] = FactorExposure(
                factor_name=factor_name,
                exposure=exposure,
                contribution_pct=contribution,
                risk_contribution=abs(exposure) * 10,
                z_score=z_score,
                status=status,
            )

            # Accumulate risk score
            if abs(z_score) > 2.0:
                risk_score += 25
            elif abs(z_score) > 1.5:
                risk_score += 15
            elif abs(z_score) > 1.0:
                risk_score += 8

        risk_score = min(risk_score, 100.0)

        # Dominant factors (top 3 by absolute exposure)
        sorted_factors = sorted(
            exposures.items(),
            key=lambda x: abs(x[1].exposure),
            reverse=True,
        )
        dominant = [name for name, _ in sorted_factors[:3] if abs(exposures[name].exposure) > 0.3]

        # Diversification score (0-100, higher = more diversified)
        diversification = 100.0 - min(risk_score * 0.8, 100.0)

        risk_level = "LOW"
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"

        return FactorExposureReport(
            account_id=account_id,
            total_equity=total_equity,
            exposures=exposures,
            factor_risk_score=risk_score,
            risk_level=risk_level,
            dominant_factors=dominant,
            diversification_score=diversification,
        )

    async def check_factor_limit(
        self,
        factor_name: str,
        exposure: float,
    ) -> dict[str, Any]:
        """Check if a factor exposure exceeds limits."""
        benchmarks = self._factor_benchmarks.get(factor_name, (0.0, 1.0))
        z_score = (exposure - benchmarks[0]) / benchmarks[1] if benchmarks[1] > 0 else 0.0

        if abs(z_score) > self._max_z_score:
            return {
                "passed": False,
                "factor": factor_name,
                "exposure": exposure,
                "z_score": z_score,
                "limit": self._max_z_score,
                "message": f"Factor {factor_name} z-score {z_score:.2f} exceeds limit",
            }
        return {
            "passed": True,
            "factor": factor_name,
            "exposure": exposure,
            "z_score": z_score,
            "message": f"Factor {factor_name} exposure within limits",
        }

    # ---- Configuration ----

    def set_benchmarks(self, benchmarks: dict[str, tuple[float, float]]) -> None:
        """Update factor benchmarks for z-score computation."""
        self._factor_benchmarks.update(benchmarks)
        logger.info(f"Factor benchmarks updated: {list(benchmarks.keys())}")

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "tracked_factors": len(STANDARD_FACTORS),
            "max_exposure_per_factor": self._max_exposure,
            "max_z_score": self._max_z_score,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
        }
