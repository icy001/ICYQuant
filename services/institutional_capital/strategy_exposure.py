"""
Strategy Exposure — Factor & Market Exposure per Strategy

Tracks each strategy's exposure to risk factors, market regimes,
asset classes, sectors, and regions. This feeds the exposure matrix
for overlap detection and concentration analysis.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    factor_name: str
    exposure: float    # Beta / loading
    contribution: float  # % of total risk
    confidence: float = 0.5


@dataclass
class StrategyExposureProfile:
    strategy_id: str
    factor_exposures: Dict[str, FactorExposure] = field(default_factory=dict)
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    region_exposure: Dict[str, float] = field(default_factory=dict)
    asset_class_exposure: Dict[str, float] = field(default_factory=dict)
    total_risk_contribution: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)


class StrategyExposure:
    """
    Manages strategy exposure profiles across factors, sectors,
    regions, and asset classes.

    Feeds ExposureMatrix for overlap detection and concentration analysis.
    """

    def __init__(
        self,
        exposure_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.exposure_id = exposure_id or f"sexp-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._profiles: Dict[str, StrategyExposureProfile] = {}

    def register(self, strategy_id: str) -> StrategyExposureProfile:
        profile = StrategyExposureProfile(strategy_id=strategy_id)
        self._profiles[strategy_id] = profile
        return profile

    def set_factor_exposure(
        self,
        strategy_id: str,
        factor_name: str,
        exposure: float,
        contribution: float = 0.0,
    ) -> None:
        profile = self._profiles.get(strategy_id)
        if not profile:
            profile = self.register(strategy_id)
        profile.factor_exposures[factor_name] = FactorExposure(
            factor_name=factor_name,
            exposure=exposure,
            contribution=contribution,
        )
        profile.updated_at = datetime.utcnow()

    def set_sector_exposure(self, strategy_id: str, sector: str, weight: float) -> None:
        profile = self._profiles.get(strategy_id)
        if not profile:
            profile = self.register(strategy_id)
        profile.sector_exposure[sector] = weight
        profile.updated_at = datetime.utcnow()

    def set_region_exposure(self, strategy_id: str, region: str, weight: float) -> None:
        profile = self._profiles.get(strategy_id)
        if not profile:
            profile = self.register(strategy_id)
        profile.region_exposure[region] = weight
        profile.updated_at = datetime.utcnow()

    def get_profile(self, strategy_id: str) -> Optional[StrategyExposureProfile]:
        return self._profiles.get(strategy_id)

    def get_all_profiles(self) -> Dict[str, StrategyExposureProfile]:
        return dict(self._profiles)

    def get_factor_overlap(self, s1: str, s2: str) -> Dict[str, float]:
        """Compute factor overlap between two strategies."""
        p1 = self._profiles.get(s1)
        p2 = self._profiles.get(s2)
        if not p1 or not p2:
            return {}

        overlaps = {}
        all_factors = set(p1.factor_exposures.keys()) | set(p2.factor_exposures.keys())
        for f in all_factors:
            e1 = p1.factor_exposures.get(f)
            e2 = p2.factor_exposures.get(f)
            if e1 and e2 and e1.exposure != 0 and e2.exposure != 0:
                overlaps[f] = min(abs(e1.exposure), abs(e2.exposure)) / max(abs(e1.exposure), abs(e2.exposure))
        return overlaps
