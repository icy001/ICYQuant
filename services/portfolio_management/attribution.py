"""Performance Attribution — decomposing portfolio returns into factor and allocation components."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AttributionMethod(Enum):
    BRINSON = "brinson"  # Brinson model (allocation + selection + interaction)
    FACTOR_BASED = "factor_based"  # Multi-factor attribution
    SECTOR = "sector"  # Sector-level attribution
    ASSET_CLASS = "asset_class"  # Asset class level
    CUSTOM = "custom"


@dataclass
class AttributionConfig:
    """Configuration for attribution analysis."""

    method: AttributionMethod = AttributionMethod.BRINSON
    benchmark_id: str = ""
    factors: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)
    interaction_enabled: bool = True
    currency: str = "CNY"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorAttribution:
    """Factor-level attribution (e.g., value, momentum, size, quality)."""

    factor_name: str = ""
    factor_exposure: float = 0.0
    factor_return: float = 0.0
    contribution: float = 0.0  # exposure * return
    contribution_pct: float = 0.0
    benchmark_exposure: float = 0.0


@dataclass
class SectorAttribution:
    """Sector-level attribution."""

    sector_name: str = ""
    portfolio_weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    total_effect: float = 0.0


@dataclass
class BrinsonAttribution:
    """Brinson attribution decomposition."""

    allocation_effect: float = 0.0  # (wp - wb) * (rb - Rb)
    selection_effect: float = 0.0  # wb * (rp - rb)
    interaction_effect: float = 0.0  # (wp - wb) * (rp - rb)
    total_active_return: float = 0.0
    total_benchmark_return: float = 0.0
    sector_details: List[SectorAttribution] = field(default_factory=list)


@dataclass
class AttributionResult:
    """Complete attribution analysis result."""

    result_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    benchmark_id: str = ""
    method: AttributionMethod = AttributionMethod.BRINSON
    period: str = ""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    brinson: Optional[BrinsonAttribution] = None
    factor_attribution: List[FactorAttribution] = field(default_factory=list)
    sector_attribution: List[SectorAttribution] = field(default_factory=list)
    unexplained_return: float = 0.0
    confidence_score: float = 0.0
    calculated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def explained_pct(self) -> float:
        total_absolute = abs(self.portfolio_return) + abs(self.unexplained_return)
        return (
            (1 - abs(self.unexplained_return) / max(total_absolute, 0.0001)) * 100
        )

    def top_contributors(self, n: int = 5, by: str = "total") -> List[SectorAttribution]:
        """Get top N contributors by effect type."""
        attributions = self.sector_attribution
        if by == "allocation":
            attributions = sorted(attributions, key=lambda x: abs(x.allocation_effect), reverse=True)
        elif by == "selection":
            attributions = sorted(attributions, key=lambda x: abs(x.selection_effect), reverse=True)
        else:
            attributions = sorted(attributions, key=lambda x: abs(x.total_effect), reverse=True)
        return attributions[:n]


class AttributionEngine:
    """Performance attribution engine.

    Decomposes portfolio returns into:
    - Allocation Effect: over/underweight decisions
    - Selection Effect: security selection within sectors
    - Interaction Effect: combined allocation + selection
    - Factor Contributions: style factor exposures
    """

    def __init__(self, config: Optional[AttributionConfig] = None):
        self.config = config or AttributionConfig()
        self._results: List[AttributionResult] = []

    def attribute_brinson(
        self,
        portfolio_id: str,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        portfolio_returns: Dict[str, float],
        benchmark_returns: Dict[str, float],
        period: str = "",
    ) -> AttributionResult:
        """Brinson attribution analysis."""

        # Aggregate by sector/asset class
        all_sectors = set(
            list(portfolio_weights.keys()) + list(benchmark_weights.keys())
        )

        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0
        total_portfolio_return = 0.0
        total_benchmark_return = 0.0
        sector_details = []

        for sector in all_sectors:
            wp = portfolio_weights.get(sector, 0.0)
            wb = benchmark_weights.get(sector, 0.0)
            rp = portfolio_returns.get(sector, 0.0)
            rb = benchmark_returns.get(sector, 0.0)

            # Brinson decomposition
            # Allocation: (wp - wb) * (rb - R_benchmark)
            # Selection: wb * (rp - rb)
            # Interaction: (wp - wb) * (rp - rb)

            allocation = (wp - wb) * rb
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)
            total_effect = allocation + selection + interaction

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction
            total_portfolio_return += wp * rp
            total_benchmark_return += wb * rb

            sector_details.append(SectorAttribution(
                sector_name=sector,
                portfolio_weight=wp,
                benchmark_weight=wb,
                portfolio_return=rp,
                benchmark_return=rb,
                allocation_effect=allocation,
                selection_effect=selection,
                interaction_effect=interaction,
                total_effect=total_effect,
            ))

        active_return = total_portfolio_return - total_benchmark_return
        unexplained = active_return - (total_allocation + total_selection + total_interaction)

        brinson = BrinsonAttribution(
            allocation_effect=total_allocation,
            selection_effect=total_selection,
            interaction_effect=total_interaction,
            total_active_return=active_return,
            total_benchmark_return=total_benchmark_return,
            sector_details=sector_details,
        )

        result = AttributionResult(
            portfolio_id=portfolio_id,
            benchmark_id=self.config.benchmark_id,
            method=AttributionMethod.BRINSON,
            period=period,
            portfolio_return=total_portfolio_return,
            benchmark_return=total_benchmark_return,
            active_return=active_return,
            tracking_error=abs(active_return),
            information_ratio=(
                active_return / abs(active_return) if active_return != 0 else 0.0
            ),
            brinson=brinson,
            sector_attribution=sector_details,
            unexplained_return=unexplained,
            confidence_score=self._compute_confidence(sector_details),
        )

        self._results.append(result)
        logger.info(
            "Brinson attribution for %s: allocation=%.4f, selection=%.4f, interaction=%.4f",
            portfolio_id, total_allocation, total_selection, total_interaction,
        )
        return result

    def attribute_factors(
        self,
        portfolio_id: str,
        factor_exposures: Dict[str, float],
        factor_returns: Dict[str, float],
        benchmark_exposures: Optional[Dict[str, float]] = None,
        period: str = "",
    ) -> AttributionResult:
        """Factor-based attribution."""
        factor_attributions = []
        total_contribution = 0.0

        for factor_name in self.config.factors or factor_exposures.keys():
            exposure = factor_exposures.get(factor_name, 0.0)
            factor_return = factor_returns.get(factor_name, 0.0)
            contribution = exposure * factor_return
            bench_exp = (benchmark_exposures or {}).get(factor_name, 0.0)

            factor_attributions.append(FactorAttribution(
                factor_name=factor_name,
                factor_exposure=exposure,
                factor_return=factor_return,
                contribution=contribution,
                contribution_pct=0.0,  # computed after total
                benchmark_exposure=bench_exp,
            ))
            total_contribution += contribution

        # Calculate percentage contributions
        total_abs = sum(abs(f.contribution) for f in factor_attributions)
        for fa in factor_attributions:
            fa.contribution_pct = (fa.contribution / max(total_abs, 0.0001)) * 100

        result = AttributionResult(
            portfolio_id=portfolio_id,
            method=AttributionMethod.FACTOR_BASED,
            period=period,
            portfolio_return=total_contribution,
            factor_attribution=factor_attributions,
            unexplained_return=0.0,
            confidence_score=0.8,
        )

        self._results.append(result)
        return result

    def _compute_confidence(self, sector_details: List[SectorAttribution]) -> float:
        """Compute confidence score for attribution analysis."""
        if not sector_details:
            return 0.0
        # Higher confidence with more sectors and balanced contributions
        n = len(sector_details)
        total_contribution = sum(abs(s.total_effect) for s in sector_details)
        if total_contribution <= 0:
            return 0.5

        # Herfindahl-style concentration of contributions
        concentration = sum(
            (s.total_effect / total_contribution) ** 2 for s in sector_details
        )
        diversity_score = 1.0 / (concentration * n) if concentration > 0 else 1.0
        return min(1.0, diversity_score)

    def get_results(
        self,
        portfolio_id: Optional[str] = None,
        method: Optional[AttributionMethod] = None,
        limit: int = 50,
    ) -> List[AttributionResult]:
        results = self._results
        if portfolio_id:
            results = [r for r in results if r.portfolio_id == portfolio_id]
        if method:
            results = [r for r in results if r.method == method]
        return results[-limit:]

    def get_latest_result(self, portfolio_id: str) -> Optional[AttributionResult]:
        results = self.get_results(portfolio_id=portfolio_id, limit=1)
        return results[0] if results else None

    def get_summary(self) -> Dict[str, Any]:
        results = self._results
        if not results:
            return {"total_analyses": 0}

        avg_active = sum(r.active_return for r in results) / len(results)
        avg_explained = sum(r.explained_pct for r in results) / len(results)
        methods = {}
        for r in results:
            m = r.method.value
            methods[m] = methods.get(m, 0) + 1

        return {
            "total_analyses": len(results),
            "avg_active_return": avg_active,
            "avg_explained_pct": avg_explained,
            "methods_used": methods,
        }
