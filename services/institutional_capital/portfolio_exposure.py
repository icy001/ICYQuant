"""
Portfolio Exposure — Portfolio-Level Risk & Factor Exposure

Tracks exposure at the portfolio level, aggregating from position-level
exposures. Feeds into the overall ExposureMatrix for overlap analysis.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioExposureProfile:
    portfolio_id: str
    strategy_id: Optional[str] = None
    factor_exposure: Dict[str, float] = field(default_factory=dict)
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)


class PortfolioExposure:
    """Manages portfolio-level exposure tracking and aggregation."""

    def __init__(
        self,
        exposure_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.exposure_id = exposure_id or f"pexp-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._profiles: Dict[str, PortfolioExposureProfile] = {}

    def register(self, portfolio_id: str, strategy_id: Optional[str] = None) -> PortfolioExposureProfile:
        profile = PortfolioExposureProfile(
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
        )
        self._profiles[portfolio_id] = profile
        return profile

    def update_exposure(self, portfolio_id: str, **kwargs) -> None:
        profile = self._profiles.get(portfolio_id)
        if not profile:
            return
        for k, v in kwargs.items():
            if hasattr(profile, k):
                setattr(profile, k, v)
        profile.updated_at = datetime.utcnow()

    def get(self, portfolio_id: str) -> Optional[PortfolioExposureProfile]:
        return self._profiles.get(portfolio_id)

    def get_by_strategy(self, strategy_id: str) -> List[PortfolioExposureProfile]:
        return [p for p in self._profiles.values() if p.strategy_id == strategy_id]

    def get_aggregate_exposures(self) -> Dict[str, float]:
        """Aggregate factor exposures across all portfolios."""
        agg: Dict[str, float] = {}
        for p in self._profiles.values():
            for factor, exposure in p.factor_exposure.items():
                agg[factor] = agg.get(factor, 0.0) + exposure
        return agg

    def get_summary(self) -> Dict[str, Any]:
        return {
            "exposure_id": self.exposure_id,
            "portfolio_count": len(self._profiles),
            "total_gross_exposure": sum(p.gross_exposure for p in self._profiles.values()),
            "total_net_exposure": sum(p.net_exposure for p in self._profiles.values()),
        }
