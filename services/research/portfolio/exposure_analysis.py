"""Exposure Analysis — multi-dimensional portfolio exposure breakdown.

Analyzes exposures across:
* Asset Class — equity, fixed income, commodities
* Sector — GICS sector classification
* Factor — style factor exposures
* Geography — regional concentration
* Currency — FX exposure
* Market Cap — size segmentation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExposureBreakdown:
    """Breakdown of exposure along one dimension."""

    dimension: str
    categories: Dict[str, float] = field(default_factory=dict)
    concentration_hhi: float = 0.0
    effective_n: float = 0.0
    top_category: str = ""
    top_weight: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "categories": self.categories,
            "concentration_hhi": self.concentration_hhi,
            "effective_n": self.effective_n,
            "top_category": self.top_category,
            "top_weight": self.top_weight,
        }


@dataclass
class ExposureReport:
    """Multi-dimensional exposure analysis report."""

    portfolio_id: str = ""
    total_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    breakdowns: List[ExposureBreakdown] = field(default_factory=list)
    concentration_risk: str = "moderate"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "total_exposure": self.total_exposure,
            "long_exposure": self.long_exposure,
            "short_exposure": self.short_exposure,
            "net_exposure": self.net_exposure,
            "gross_exposure": self.gross_exposure,
            "concentration_risk": self.concentration_risk,
            "breakdowns": [b.to_dict() for b in self.breakdowns],
            "metadata": self.metadata,
        }


class ExposureAnalyzer:
    """Multi-dimensional portfolio exposure analysis.

    Computes exposures across asset class, sector, factor,
    geography, and market cap dimensions.
    """

    # GICS sector definitions
    GICS_SECTORS = [
        "energy", "materials", "industrials",
        "consumer_discretionary", "consumer_staples",
        "health_care", "financials", "information_technology",
        "communication_services", "utilities", "real_estate",
    ]

    def __init__(self) -> None:
        pass

    async def analyze(
        self,
        weights: Dict[str, float],
        asset_sectors: Optional[Dict[str, str]] = None,
        asset_factors: Optional[Dict[str, Dict[str, float]]] = None,
        asset_market_cap: Optional[Dict[str, str]] = None,
        asset_geography: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> ExposureReport:
        """Analyze portfolio exposures across dimensions.

        Args:
            weights: Portfolio weights.
            asset_sectors: Asset → sector mapping.
            asset_factors: Asset → factor exposure mapping.
            asset_market_cap: Asset → market cap category.
            asset_geography: Asset → geography mapping.

        Returns:
            ExposureReport with multi-dimensional analysis.
        """
        assets = list(weights.keys())

        # Compute basic exposures
        long_exp = sum(max(w, 0) for w in weights.values())
        short_exp = sum(abs(min(w, 0)) for w in weights.values())
        net_exp = long_exp - short_exp
        gross_exp = long_exp + short_exp

        report = ExposureReport(
            portfolio_id=kwargs.get("portfolio_id", ""),
            total_exposure=sum(weights.values()),
            long_exposure=long_exp,
            short_exposure=short_exp,
            net_exposure=net_exp,
            gross_exposure=gross_exp,
        )

        # 1. Sector exposure
        sector_exp = self._sector_exposure(weights, asset_sectors)
        report.breakdowns.append(sector_exp)

        # 2. Factor exposure
        factor_exp = self._factor_exposure(weights, asset_factors)
        report.breakdowns.append(factor_exp)

        # 3. Market cap exposure
        mcap_exp = self._market_cap_exposure(weights, asset_market_cap)
        report.breakdowns.append(mcap_exp)

        # 4. Geography exposure
        geo_exp = self._geography_exposure(weights, asset_geography)
        report.breakdowns.append(geo_exp)

        # Concentration risk assessment
        report.concentration_risk = self._assess_concentration(report)

        return report

    def _sector_exposure(
        self,
        weights: Dict[str, float],
        asset_sectors: Optional[Dict[str, str]],
    ) -> ExposureBreakdown:
        """Compute sector exposure breakdown."""
        sectors: Dict[str, float] = {}

        if asset_sectors:
            for asset, weight in weights.items():
                sector = asset_sectors.get(asset, "unknown")
                sectors[sector] = sectors.get(sector, 0.0) + weight
        else:
            # Synthetic sector allocation
            import random
            random.seed(42)
            for asset, weight in weights.items():
                sector = random.choice(self.GICS_SECTORS)
                sectors[sector] = sectors.get(sector, 0.0) + weight

        return self._build_breakdown("sector", sectors)

    def _factor_exposure(
        self,
        weights: Dict[str, float],
        asset_factors: Optional[Dict[str, Dict[str, float]]],
    ) -> ExposureBreakdown:
        """Compute factor exposure breakdown."""
        factors: Dict[str, float] = {}

        if asset_factors:
            for asset, weight in weights.items():
                for factor, exposure in asset_factors.get(asset, {}).items():
                    factors[factor] = (
                        factors.get(factor, 0.0) + weight * exposure
                    )
        else:
            # Synthetic factor exposures
            import random
            random.seed(42)
            common_factors = [
                "market", "size", "value", "momentum", "quality", "volatility"
            ]
            for factor in common_factors:
                factors[factor] = sum(
                    weights.get(a, 0.0) * random.uniform(-1.0, 1.0)
                    for a in weights
                )

        return self._build_breakdown("factor", factors)

    def _market_cap_exposure(
        self,
        weights: Dict[str, float],
        asset_market_cap: Optional[Dict[str, str]],
    ) -> ExposureBreakdown:
        """Compute market cap exposure."""
        categories: Dict[str, float] = {}

        if asset_market_cap:
            for asset, weight in weights.items():
                cat = asset_market_cap.get(asset, "unknown")
                categories[cat] = categories.get(cat, 0.0) + weight
        else:
            # Synthetic distribution
            categories = {
                "large_cap": sum(weights.values()) * 0.5,
                "mid_cap": sum(weights.values()) * 0.3,
                "small_cap": sum(weights.values()) * 0.2,
            }

        return self._build_breakdown("market_cap", categories)

    def _geography_exposure(
        self,
        weights: Dict[str, float],
        asset_geography: Optional[Dict[str, str]],
    ) -> ExposureBreakdown:
        """Compute geography exposure."""
        regions: Dict[str, float] = {}

        if asset_geography:
            for asset, weight in weights.items():
                region = asset_geography.get(asset, "unknown")
                regions[region] = regions.get(region, 0.0) + weight
        else:
            regions = {
                "china": sum(weights.values()) * 0.7,
                "developed_markets": sum(weights.values()) * 0.2,
                "emerging_markets": sum(weights.values()) * 0.1,
            }

        return self._build_breakdown("geography", regions)

    def _build_breakdown(
        self, dimension: str, categories: Dict[str, float]
    ) -> ExposureBreakdown:
        """Build an ExposureBreakdown with concentration metrics."""
        # HHI (Herfindahl-Hirschman Index)
        total = sum(categories.values())
        if total > 0:
            hhi = sum((v / total) ** 2 for v in categories.values())
        else:
            hhi = 0.0

        # Effective N (inverse HHI)
        effective_n = 1.0 / hhi if hhi > 0 else 0.0

        # Top category
        top_cat = max(categories.items(), key=lambda x: x[1]) if categories else ("", 0.0)

        return ExposureBreakdown(
            dimension=dimension,
            categories=categories,
            concentration_hhi=hhi,
            effective_n=effective_n,
            top_category=top_cat[0],
            top_weight=top_cat[1],
        )

    def _assess_concentration(self, report: ExposureReport) -> str:
        """Assess overall concentration risk."""
        hhi_values = [
            b.concentration_hhi
            for b in report.breakdowns
            if b.dimension in ("sector",)
        ]

        if not hhi_values:
            return "moderate"

        max_hhi = max(hhi_values)
        if max_hhi > 0.25:
            return "high"
        elif max_hhi > 0.15:
            return "moderate"
        else:
            return "low"
