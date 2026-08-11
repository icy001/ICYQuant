"""
Attribution Engine
=================
Analyzes sources of strategy returns through multi-level attribution.

Decomposition:
    Alpha → Beta → Sector → Factor → Contribution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AttributionLevel(str, Enum):
    ALPHA = "alpha"
    BETA = "beta"
    SECTOR = "sector"
    FACTOR = "factor"
    STOCK = "stock"


@dataclass
class AttributionFactor:
    """A single attribution factor."""
    name: str = ""
    exposure: float = 0.0
    factor_return: float = 0.0
    contribution: float = 0.0
    contribution_pct: float = 0.0


@dataclass
class AttributionComponent:
    """A single attribution component (sector, factor, etc.)."""
    name: str = ""
    weight: float = 0.0
    return_: float = 0.0
    contribution: float = 0.0
    contribution_pct: float = 0.0


@dataclass
class AttributionReport:
    """Full attribution analysis report."""
    report_id: str = ""
    strategy_id: str = ""
    total_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    alpha: float = 0.0
    beta_contribution: float = 0.0
    sector_contributions: List[AttributionComponent] = field(default_factory=list)
    factor_contributions: List[AttributionFactor] = field(default_factory=list)
    stock_contributions: List[AttributionComponent] = field(default_factory=list)
    residual: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "strategy_id": self.strategy_id,
            "total_return": round(self.total_return, 6),
            "benchmark_return": round(self.benchmark_return, 6),
            "excess_return": round(self.excess_return, 6),
            "alpha": round(self.alpha, 6),
            "beta_contribution": round(self.beta_contribution, 6),
            "residual": round(self.residual, 6),
            "sector_contributions": [
                {"name": s.name, "contribution": round(s.contribution, 6),
                 "contribution_pct": round(s.contribution_pct, 2)}
                for s in self.sector_contributions
            ],
            "factor_contributions": [
                {"name": f.name, "exposure": round(f.exposure, 4),
                 "contribution": round(f.contribution, 6)}
                for f in self.factor_contributions
            ],
            "generated_at": self.generated_at.isoformat(),
        }


class AttributionEngine:
    """Multi-level return attribution analysis.

    Pipeline:
        Alpha → Beta → Sector → Factor → Contribution
    """

    def __init__(self):
        self._factor_exposures: Dict[str, Dict[str, float]] = {}
        self._factor_returns: Dict[str, float] = {}
        self._sector_mappings: Dict[str, str] = {}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("AttributionEngine initialized")

    # ------------------------------------------------------------------
    # Attribution
    # ------------------------------------------------------------------

    async def attribute(self, portfolio_return: float,
                        benchmark_return: float,
                        sector_weights: Optional[Dict[str, float]] = None,
                        sector_returns: Optional[Dict[str, float]] = None,
                        portfolio_beta: float = 1.0) -> AttributionReport:
        """Perform multi-level attribution analysis."""
        excess = portfolio_return - benchmark_return

        # Beta contribution
        beta_contrib = portfolio_beta * benchmark_return

        # Alpha (residual after beta)
        alpha = portfolio_return - beta_contrib

        # Sector attribution
        sector_components = []
        if sector_weights and sector_returns:
            for sector, weight in sector_weights.items():
                sector_ret = sector_returns.get(sector, 0.0)
                contrib = weight * sector_ret
                sector_components.append(AttributionComponent(
                    name=sector,
                    weight=weight,
                    return_=sector_ret,
                    contribution=contrib,
                    contribution_pct=(contrib / portfolio_return * 100) if portfolio_return != 0 else 0,
                ))

        # Factor attribution
        factor_components = []
        for factor_name, exposures in self._factor_exposures.items():
            factor_ret = self._factor_returns.get(factor_name, 0.0)
            total_exposure = sum(exposures.values())
            contribution = total_exposure * factor_ret
            factor_components.append(AttributionFactor(
                name=factor_name,
                exposure=total_exposure,
                factor_return=factor_ret,
                contribution=contribution,
                contribution_pct=(contribution / portfolio_return * 100) if portfolio_return != 0 else 0,
            ))

        # Residual
        attributed = sum(c.contribution for c in sector_components)
        residual = portfolio_return - attributed

        return AttributionReport(
            report_id=f"attr_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            total_return=portfolio_return,
            benchmark_return=benchmark_return,
            excess_return=excess,
            alpha=alpha,
            beta_contribution=beta_contrib,
            sector_contributions=sector_components,
            factor_contributions=factor_components,
            residual=residual,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_factor_exposures(self, instrument: str, exposures: Dict[str, float]) -> None:
        self._factor_exposures[instrument] = exposures

    def set_factor_returns(self, factor_returns: Dict[str, float]) -> None:
        self._factor_returns.update(factor_returns)

    def set_sector_mapping(self, instrument: str, sector: str) -> None:
        self._sector_mappings[instrument] = sector

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "instruments_with_exposures": len(self._factor_exposures),
            "factors_tracked": len(self._factor_returns),
            "sector_mappings": len(self._sector_mappings),
        }
