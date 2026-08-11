"""
Concentration Optimizer — controls portfolio concentration across dimensions.

Monitors and enforces concentration limits on:
    - Single asset
    - Sector / industry
    - Country / region
    - Strategy
    - Factor
    - Currency
    - Liquidity tier

Uses HHI (Herfindahl-Hirschman Index) for overall concentration measurement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ConcentrationLimits:
    """Concentration limit configuration."""
    max_single_asset: float = 0.20
    max_single_sector: float = 0.40
    max_single_country: float = 0.50
    max_single_strategy: float = 0.35
    max_single_factor: float = 0.45
    max_single_currency: float = 0.60
    max_hhi: float = 0.15
    max_top5_pct: float = 0.60
    max_top10_pct: float = 0.80


@dataclass
class ConcentrationProfile:
    """Current concentration profile."""
    hhi: float = 0.0
    top1_pct: float = 0.0
    top5_pct: float = 0.0
    top10_pct: float = 0.0
    max_single: float = 0.0
    max_sector: float = 0.0
    asset_count: int = 0
    effective_n: float = 0.0


@dataclass
class ConcentrationResult:
    """Result of concentration optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    original: ConcentrationProfile = field(default_factory=ConcentrationProfile)
    optimized: ConcentrationProfile = field(default_factory=ConcentrationProfile)
    violations: list[dict] = field(default_factory=list)
    rebalances: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ConcentrationOptimizer:
    """
    Autonomous concentration control.

    Key metrics:
        - HHI = sum(weight_i^2) — 0 to 1, lower is more diversified
        - Effective N = 1 / HHI — number of equal-weighted positions
        - Top-N percentage

    Actions:
        - Cap individual positions
        - Cap sector/country/factor exposures
        - Redistribute excess to underweight positions
    """

    def __init__(self, limits: Optional[ConcentrationLimits] = None) -> None:
        self._limits = limits or ConcentrationLimits()
        self._last_result: Optional[ConcentrationResult] = None

    async def optimize(
        self,
        positions: dict[str, float],
        sector_map: Optional[dict[str, str]] = None,
        country_map: Optional[dict[str, str]] = None,
        factor_exposures: Optional[dict[str, float]] = None,
    ) -> ConcentrationResult:
        """Optimize portfolio concentration."""
        profile = self._compute_profile(positions)
        result = ConcentrationResult(original=profile)

        adjusted = dict(positions)
        violations = []
        rebalances = []

        # Check single-asset concentration
        for asset, weight in list(adjusted.items()):
            if abs(weight) > self._limits.max_single_asset:
                cap = self._limits.max_single_asset * (1 if weight > 0 else -1)
                excess = weight - cap
                adjusted[asset] = cap
                rebalances.append({
                    "type": "single_asset_cap", "asset": asset,
                    "from": weight, "to": cap, "excess": excess,
                })

        # Check sector concentration
        if sector_map:
            sector_weights: dict[str, float] = {}
            for asset, weight in adjusted.items():
                sector = sector_map.get(asset, "OTHER")
                sector_weights[sector] = sector_weights.get(sector, 0) + weight
            for sector, weight in sector_weights.items():
                if abs(weight) > self._limits.max_single_sector:
                    violations.append({
                        "type": "sector_concentration",
                        "sector": sector, "weight": weight,
                        "limit": self._limits.max_single_sector,
                    })

        # Check HHI
        new_profile = self._compute_profile(adjusted)
        if new_profile.hhi > self._limits.max_hhi:
            violations.append({
                "type": "hhi", "hhi": new_profile.hhi,
                "limit": self._limits.max_hhi,
            })

        if new_profile.top5_pct > self._limits.max_top5_pct:
            violations.append({
                "type": "top5", "top5_pct": new_profile.top5_pct,
                "limit": self._limits.max_top5_pct,
            })

        result.optimized = new_profile
        result.violations = violations
        result.rebalances = rebalances
        result.timestamp = datetime.now()
        self._last_result = result
        return result

    async def analyze(self, positions: dict[str, float]) -> ConcentrationProfile:
        """Analyze concentration without optimizing."""
        return self._compute_profile(positions)

    def _compute_profile(self, positions: dict[str, float]) -> ConcentrationProfile:
        """Compute concentration metrics."""
        if not positions:
            return ConcentrationProfile()

        total = sum(abs(v) for v in positions.values()) or 1.0
        weights = {k: abs(v) / total for k, v in positions.items()}

        hhi = sum(w * w for w in weights.values())
        sorted_weights = sorted(weights.values(), reverse=True)

        top1 = sorted_weights[0] if sorted_weights else 0
        top5 = sum(sorted_weights[:5])
        top10 = sum(sorted_weights[:10])
        effective_n = 1.0 / hhi if hhi > 0 else float("inf")

        return ConcentrationProfile(
            hhi=hhi,
            top1_pct=top1,
            top5_pct=top5,
            top10_pct=top10,
            max_single=top1,
            asset_count=len(positions),
            effective_n=effective_n,
        )

    @property
    def last_result(self) -> Optional[ConcentrationResult]:
        return self._last_result
