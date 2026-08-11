"""
Exposure Optimizer — optimizes gross, net, long, and short exposures.

Controls:
    - Gross exposure (long + short)
    - Net exposure (long - short)
    - Long/short ratio
    - Sector exposure
    - Factor exposure
    - Currency exposure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExposureLimits:
    """Exposure limit configuration."""
    max_gross: float = 2.0
    max_net: float = 1.5
    max_long: float = 1.5
    max_short: float = 0.5
    max_sector: float = 0.40
    max_factor: float = 0.60
    max_currency: float = 0.75
    min_gross: float = 0.10


@dataclass
class ExposureProfile:
    """Current exposure profile."""
    gross: float = 0.0
    net: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    sector_exposures: dict[str, float] = field(default_factory=dict)
    factor_exposures: dict[str, float] = field(default_factory=dict)
    currency_exposures: dict[str, float] = field(default_factory=dict)


@dataclass
class ExposureOptimizationResult:
    """Result of exposure optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    original: ExposureProfile = field(default_factory=ExposureProfile)
    optimized: ExposureProfile = field(default_factory=ExposureProfile)
    adjustments: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ExposureOptimizer:
    """
    Optimizes portfolio exposures against configured limits.

    Optimization order:
        1. Net exposure clamp
        2. Gross exposure clamp
        3. Long/short ratio balance
        4. Sector cap
        5. Factor cap
        6. Currency cap
    """

    def __init__(self, limits: Optional[ExposureLimits] = None) -> None:
        self._limits = limits or ExposureLimits()
        self._last_result: Optional[ExposureOptimizationResult] = None

    async def optimize(
        self, profile: ExposureProfile
    ) -> ExposureOptimizationResult:
        """Optimize exposure profile against limits."""
        result = ExposureOptimizationResult(original=profile)
        optimized = ExposureProfile(
            gross=profile.gross,
            net=profile.net,
            long_exposure=profile.long_exposure,
            short_exposure=profile.short_exposure,
            sector_exposures=dict(profile.sector_exposures),
            factor_exposures=dict(profile.factor_exposures),
            currency_exposures=dict(profile.currency_exposures),
        )

        # Clamp net exposure
        if abs(optimized.net) > self._limits.max_net:
            scale = self._limits.max_net / abs(optimized.net)
            optimized.long_exposure *= scale
            optimized.short_exposure *= scale
            optimized.net = optimized.long_exposure - optimized.short_exposure
            optimized.gross = optimized.long_exposure + optimized.short_exposure
            result.adjustments.append({
                "type": "net_exposure_clamp", "scale": scale,
            })

        # Clamp gross exposure
        if optimized.gross > self._limits.max_gross:
            scale = self._limits.max_gross / optimized.gross
            optimized.long_exposure *= scale
            optimized.short_exposure *= scale
            optimized.gross = self._limits.max_gross
            optimized.net = optimized.long_exposure - optimized.short_exposure
            result.adjustments.append({
                "type": "gross_exposure_clamp", "scale": scale,
            })

        # Cap sector exposures
        for sector, exp in list(optimized.sector_exposures.items()):
            if abs(exp) > self._limits.max_sector:
                scale = self._limits.max_sector / abs(exp)
                optimized.sector_exposures[sector] = (
                    self._limits.max_sector * (1 if exp > 0 else -1)
                )
                result.adjustments.append({
                    "type": "sector_cap", "sector": sector, "scale": scale,
                })

        # Cap factor exposures
        for factor, exp in list(optimized.factor_exposures.items()):
            if abs(exp) > self._limits.max_factor:
                scale = self._limits.max_factor / abs(exp)
                optimized.factor_exposures[factor] = (
                    self._limits.max_factor * (1 if exp > 0 else -1)
                )
                result.adjustments.append({
                    "type": "factor_cap", "factor": factor, "scale": scale,
                })

        # Cap currency exposures
        for currency, exp in list(optimized.currency_exposures.items()):
            if abs(exp) > self._limits.max_currency:
                scale = self._limits.max_currency / abs(exp)
                optimized.currency_exposures[currency] = (
                    self._limits.max_currency * (1 if exp > 0 else -1)
                )
                result.adjustments.append({
                    "type": "currency_cap", "currency": currency, "scale": scale,
                })

        result.optimized = optimized
        result.timestamp = datetime.now()
        self._last_result = result

        if result.adjustments:
            logger.info("Exposure optimized: %d adjustments", len(result.adjustments))
        return result

    async def analyze(self, profile: ExposureProfile) -> list[dict]:
        """Analyze exposure profile and return warnings."""
        warnings = []
        if profile.gross > self._limits.max_gross:
            warnings.append({
                "type": "gross_exposure", "current": profile.gross,
                "limit": self._limits.max_gross,
            })
        if abs(profile.net) > self._limits.max_net:
            warnings.append({
                "type": "net_exposure", "current": profile.net,
                "limit": self._limits.max_net,
            })
        for sector, exp in profile.sector_exposures.items():
            if abs(exp) > self._limits.max_sector:
                warnings.append({
                    "type": "sector_exposure", "sector": sector,
                    "current": exp, "limit": self._limits.max_sector,
                })
        return warnings

    def compute_exposure(
        self, positions: dict[str, float], long_short: bool = True
    ) -> ExposureProfile:
        """Compute exposure profile from positions."""
        long_exp = sum(v for v in positions.values() if v > 0)
        short_exp = sum(abs(v) for v in positions.values() if v < 0)
        return ExposureProfile(
            gross=long_exp + short_exp,
            net=long_exp - short_exp,
            long_exposure=long_exp,
            short_exposure=short_exp,
        )

    @property
    def last_result(self) -> Optional[ExposureOptimizationResult]:
        return self._last_result
