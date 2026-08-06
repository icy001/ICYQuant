"""Portfolio Attribution — decompose portfolio returns into sources.

Analyzes return attribution through:
* Allocation Effect — sector/asset class allocation decisions
* Selection Effect — within-sector security selection
* Interaction Effect — cross-term between allocation and selection
* Factor Attribution — factor-based return decomposition
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AttributionEffect:
    """A single attribution effect."""

    category: str  # sector, factor, or asset
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    total_effect: float = 0.0
    weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "allocation_effect": self.allocation_effect,
            "selection_effect": self.selection_effect,
            "interaction_effect": self.interaction_effect,
            "total_effect": self.total_effect,
            "weight": self.weight,
            "benchmark_weight": self.benchmark_weight,
            "portfolio_return": self.portfolio_return,
            "benchmark_return": self.benchmark_return,
        }


@dataclass
class AttributionReport:
    """Complete portfolio attribution report."""

    portfolio_id: str = ""
    total_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    total_allocation_effect: float = 0.0
    total_selection_effect: float = 0.0
    total_interaction_effect: float = 0.0
    effects: List[AttributionEffect] = field(default_factory=list)
    factor_attribution: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "total_return": self.total_return,
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
            "allocation_effect": self.total_allocation_effect,
            "selection_effect": self.total_selection_effect,
            "interaction_effect": self.total_interaction_effect,
            "effects": [e.to_dict() for e in self.effects[:20]],
            "factor_attribution": self.factor_attribution,
            "num_effects": len(self.effects),
            "metadata": self.metadata,
        }


class PortfolioAttribution:
    """Brinson-style portfolio attribution analysis.

    Decomposes portfolio excess returns into allocation,
    selection, and interaction effects across sectors.
    """

    def __init__(self) -> None:
        pass

    async def analyze(
        self,
        weights: Dict[str, float],
        benchmark: str = "CSI300",
        benchmark_weights: Optional[Dict[str, float]] = None,
        sector_returns: Optional[Dict[str, float]] = None,
        asset_returns: Optional[Dict[str, float]] = None,
        asset_sectors: Optional[Dict[str, str]] = None,
        factor_returns: Optional[Dict[str, float]] = None,
        asset_factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> AttributionReport:
        """Run Brinson attribution analysis.

        Brinson decomposition:
            R_p - R_b = Allocation + Selection + Interaction

        Allocation = Σ (w_pi - w_bi) * R_bi
        Selection  = Σ w_bi * (R_pi - R_bi)
        Interaction = Σ (w_pi - w_bi) * (R_pi - R_bi)
        """
        report = AttributionReport(portfolio_id=benchmark)

        # Generate synthetic data if not provided
        if benchmark_weights is None:
            benchmark_weights = self._synthetic_benchmark(list(weights.keys()))
        if asset_returns is None:
            asset_returns = self._synthetic_returns(list(weights.keys()))
        if asset_sectors is None:
            asset_sectors = self._synthetic_sectors(list(weights.keys()))
        if sector_returns is None:
            sector_returns = self._compute_sector_returns(
                asset_returns, benchmark_weights, asset_sectors
            )

        # Aggregate to sectors
        sectors = set(asset_sectors.values())
        portfolio_sector_weights: Dict[str, float] = {s: 0.0 for s in sectors}
        benchmark_sector_weights: Dict[str, float] = {s: 0.0 for s in sectors}
        portfolio_sector_returns: Dict[str, float] = {s: 0.0 for s in sectors}

        for asset, sector in asset_sectors.items():
            w = weights.get(asset, 0.0)
            bw = benchmark_weights.get(asset, 0.0)
            ret = asset_returns.get(asset, 0.0)

            portfolio_sector_weights[sector] += w
            benchmark_sector_weights[sector] += bw

            if portfolio_sector_weights[sector] > 0:
                portfolio_sector_returns[sector] += w * ret

        # Normalize sector returns
        for sector in sectors:
            pw = portfolio_sector_weights[sector]
            if pw > 0:
                portfolio_sector_returns[sector] /= pw

        # Compute effects per sector
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in sectors:
            pw = portfolio_sector_weights[sector]
            bw = benchmark_sector_weights[sector]
            pr = portfolio_sector_returns[sector]
            br = sector_returns.get(sector, 0.0)

            allocation = (pw - bw) * br
            selection = bw * (pr - br)
            interaction = (pw - bw) * (pr - br)

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

            report.effects.append(AttributionEffect(
                category=sector,
                allocation_effect=allocation,
                selection_effect=selection,
                interaction_effect=interaction,
                total_effect=allocation + selection + interaction,
                weight=pw,
                benchmark_weight=bw,
                portfolio_return=pr,
                benchmark_return=br,
            ))

        # Compute total returns
        report.total_return = sum(
            weights.get(a, 0.0) * asset_returns.get(a, 0.0)
            for a in weights
        )
        report.benchmark_return = sum(
            benchmark_weights.get(a, 0.0) * asset_returns.get(a, 0.0)
            for a in benchmark_weights
        )
        report.excess_return = report.total_return - report.benchmark_return

        report.total_allocation_effect = total_allocation
        report.total_selection_effect = total_selection
        report.total_interaction_effect = total_interaction

        # Factor attribution
        if factor_returns and asset_factor_exposures:
            report.factor_attribution = self._factor_attribution(
                weights, factor_returns, asset_factor_exposures,
            )

        # Sort effects by absolute total effect
        report.effects.sort(
            key=lambda e: abs(e.total_effect), reverse=True
        )

        return report

    def _factor_attribution(
        self,
        weights: Dict[str, float],
        factor_returns: Dict[str, float],
        asset_exposures: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """Compute factor-based return attribution."""
        attribution: Dict[str, float] = {}
        for factor, f_ret in factor_returns.items():
            exposure = 0.0
            for asset, w in weights.items():
                exp = asset_exposures.get(asset, {}).get(factor, 0.0)
                exposure += w * exp
            attribution[factor] = exposure * f_ret
        return attribution

    def _synthetic_benchmark(self, assets: List[str]) -> Dict[str, float]:
        import random
        random.seed(42)
        raw = {a: random.uniform(0.5, 1.5) for a in assets}
        total = sum(raw.values())
        return {a: raw[a] / total for a in assets}

    def _synthetic_returns(self, assets: List[str]) -> Dict[str, float]:
        import random
        random.seed(42)
        return {a: random.uniform(-0.15, 0.30) for a in assets}

    def _synthetic_sectors(self, assets: List[str]) -> Dict[str, str]:
        import random
        random.seed(42)
        sectors = [
            "energy", "materials", "industrials", "financials",
            "tech", "consumer", "health_care", "utilities",
        ]
        return {a: random.choice(sectors) for a in assets}

    def _compute_sector_returns(
        self,
        asset_returns: Dict[str, float],
        benchmark_weights: Dict[str, float],
        asset_sectors: Dict[str, str],
    ) -> Dict[str, float]:
        """Compute benchmark sector returns."""
        sector_returns: Dict[str, float] = {}
        sector_weights: Dict[str, float] = {}

        for asset, ret in asset_returns.items():
            sector = asset_sectors.get(asset, "unknown")
            w = benchmark_weights.get(asset, 0.0)
            sector_returns[sector] = (
                sector_returns.get(sector, 0.0) + w * ret
            )
            sector_weights[sector] = sector_weights.get(sector, 0.0) + w

        for sector in sector_returns:
            if sector_weights[sector] > 0:
                sector_returns[sector] /= sector_weights[sector]

        return sector_returns
