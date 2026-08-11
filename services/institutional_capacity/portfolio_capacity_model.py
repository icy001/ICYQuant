"""
Portfolio Capacity Model — Models capacity constraints at the portfolio level.

Accounts for:
- Strategy-to-strategy competition for shared assets
- Factor concentration limits
- Total execution bandwidth
- Correlation-adjusted capacity
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .portfolio_capacity import PortfolioCapacity, AssetOverlap, FactorOverlap


@dataclass
class CapacityConstraint:
    """A single portfolio-level capacity constraint."""

    name: str = ""
    limit: float = float("inf")
    current: float = 0.0
    utilization: float = 0.0
    is_binding: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "limit": self.limit,
            "current": self.current,
            "utilization": round(self.utilization, 4),
            "is_binding": self.is_binding,
        }


@dataclass
class CapacityCorrelation:
    """Correlation between strategy capacity usage."""

    strategy_a: str = ""
    strategy_b: str = ""
    asset_correlation: float = 0.0
    factor_correlation: float = 0.0
    composite_correlation: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_a": self.strategy_a,
            "strategy_b": self.strategy_b,
            "asset_correlation": round(self.asset_correlation, 4),
            "factor_correlation": round(self.factor_correlation, 4),
            "composite_correlation": round(self.composite_correlation, 4),
        }


class PortfolioCapacityModel:
    """Models portfolio-wide capacity with asset/factor overlap adjustments."""

    def __init__(self):
        self._strategy_assets: Dict[str, Set[str]] = {}
        self._strategy_factors: Dict[str, Dict[str, float]] = {}
        self._market_capacities: Dict[str, float] = {}
        self._factor_limits: Dict[str, float] = {}
        self._capacity_constraints: List[CapacityConstraint] = []
        self._correlations: List[CapacityCorrelation] = []

    # ── Registration ──────────────────────────────────────────────

    def register_strategy_assets(self, strategy_id: str, assets: Set[str]) -> None:
        self._strategy_assets[strategy_id] = assets

    def register_strategy_factors(self, strategy_id: str, factors: Dict[str, float]) -> None:
        """Register factor exposures: {factor_name: net_exposure}."""
        self._strategy_factors[strategy_id] = factors

    def set_market_capacities(self, capacities: Dict[str, float]) -> None:
        self._market_capacities.update(capacities)

    def set_factor_limits(self, limits: Dict[str, float]) -> None:
        self._factor_limits.update(limits)

    # ── Model Computation ─────────────────────────────────────────

    def compute_asset_overlap_penalty(self) -> float:
        """Compute discount factor for portfolio capacity due to asset overlap.

        Returns a multiplier in (0, 1] where 1.0 = no overlap penalty.
        """
        asset_to_count: Dict[str, int] = {}

        for assets in self._strategy_assets.values():
            for asset in assets:
                asset_to_count[asset] = asset_to_count.get(asset, 0) + 1

        if not asset_to_count:
            return 1.0

        # Weighted average of overlap severity
        total_weight = 0.0
        weighted_penalty = 0.0

        for asset, count in asset_to_count.items():
            if count <= 1:
                continue
            capacity = self._market_capacities.get(asset, float("inf"))
            if capacity == float("inf"):
                continue

            # More strategies → more severe discount
            penalty = 1.0 - math.exp(-1.0 / count)
            weight = 1.0 / capacity  # larger capacity gets smaller weight
            weighted_penalty += penalty * weight
            total_weight += weight

        if total_weight == 0:
            return 1.0

        avg_penalty = weighted_penalty / total_weight
        return max(0.5, 1.0 - avg_penalty)

    def compute_factor_overlap_penalty(self) -> float:
        """Compute discount factor for factor concentration."""
        factor_total: Dict[str, float] = {}
        factor_strategy_count: Dict[str, int] = {}

        for sid, factors in self._strategy_factors.items():
            for factor, exposure in factors.items():
                factor_total[factor] = factor_total.get(factor, 0.0) + abs(exposure)
                factor_strategy_count[factor] = factor_strategy_count.get(factor, 0) + 1

        if not factor_total:
            return 1.0

        total_weight = 0.0
        weighted_penalty = 0.0

        for factor, total_exp in factor_total.items():
            limit = self._factor_limits.get(factor, float("inf"))
            if limit == float("inf"):
                continue
            count = factor_strategy_count[factor]
            utilization = total_exp / limit
            if utilization <= 0.5:
                continue

            penalty = min(0.3, (utilization - 0.5) * 0.6)
            weight = utilization
            weighted_penalty += penalty * weight
            total_weight += weight

        if total_weight == 0:
            return 1.0

        avg_penalty = weighted_penalty / total_weight
        return max(0.6, 1.0 - avg_penalty)

    def compute_composite_discount(self) -> float:
        """Combined asset + factor overlap discount."""
        asset_discount = self.compute_asset_overlap_penalty()
        factor_discount = self.compute_factor_overlap_penalty()
        return asset_discount * factor_discount

    def compute_capacity_constraints(self,
                                      strategies: Dict[str, float],
                                      asset_capacities: Dict[str, float]) -> List[CapacityConstraint]:
        """Build all portfolio-level capacity constraints."""
        constraints: List[CapacityConstraint] = []

        # Total dollar capacity
        total_deployed = sum(strategies.values())
        max_dollar = sum(asset_capacities.values()) if asset_capacities else float("inf")
        constraints.append(CapacityConstraint(
            name="total_dollar",
            limit=max_dollar,
            current=total_deployed,
            utilization=total_deployed / max_dollar if max_dollar > 0 else 0.0,
            is_binding=total_deployed >= max_dollar if max_dollar != float("inf") else False,
        ))

        # Per-asset capacity
        for asset, cap in asset_capacities.items():
            asset_total = sum(
                strategies.get(sid, 0.0)
                for sid, assets in self._strategy_assets.items()
                if asset in assets
            )
            if asset_total > cap * 0.3:  # Only track meaningful usage
                constraints.append(CapacityConstraint(
                    name=f"asset:{asset}",
                    limit=cap,
                    current=asset_total,
                    utilization=asset_total / cap if cap > 0 else 0.0,
                    is_binding=asset_total >= cap * 0.95,
                ))

        # Factor constraints
        for factor, limit in self._factor_limits.items():
            total_exp = sum(
                factors.get(factor, 0.0)
                for factors in self._strategy_factors.values()
            )
            constraints.append(CapacityConstraint(
                name=f"factor:{factor}",
                limit=limit,
                current=total_exp,
                utilization=total_exp / limit if limit > 0 else 0.0,
                is_binding=total_exp >= limit * 0.95,
            ))

        # Execution bandwidth
        strategy_count = len(strategies)
        if strategy_count > 0:
            max_concurrent = 10  # default max concurrent strategy orders
            constraints.append(CapacityConstraint(
                name="execution_bandwidth",
                limit=max_concurrent,
                current=strategy_count,
                utilization=strategy_count / max_concurrent,
                is_binding=strategy_count >= max_concurrent,
            ))

        self._capacity_constraints = constraints
        return constraints

    def compute_correlations(self) -> List[CapacityCorrelation]:
        """Compute capacity usage correlations between strategy pairs."""
        correlations: List[CapacityCorrelation] = []
        sids = list(self._strategy_assets.keys())

        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = sids[i], sids[j]

                # Asset overlap (Jaccard similarity)
                assets_a = self._strategy_assets.get(a, set())
                assets_b = self._strategy_assets.get(b, set())
                intersection = len(assets_a & assets_b)
                union = len(assets_a | assets_b)
                asset_corr = intersection / union if union > 0 else 0.0

                # Factor overlap (cosine similarity)
                factors_a = self._strategy_factors.get(a, {})
                factors_b = self._strategy_factors.get(b, {})
                factor_corr = self._cosine_similarity(factors_a, factors_b)

                composite = 0.5 * asset_corr + 0.5 * factor_corr
                correlations.append(CapacityCorrelation(
                    strategy_a=a, strategy_b=b,
                    asset_correlation=asset_corr,
                    factor_correlation=factor_corr,
                    composite_correlation=composite,
                ))

        self._correlations = correlations
        return correlations

    # ── Estimate ──────────────────────────────────────────────────

    def estimate_effective_portfolio_capacity(self,
                                                sum_strategy_capacities: float) -> float:
        """Estimate real executable capacity after portfolio-level adjustments."""
        discount = self.compute_composite_discount()
        return sum_strategy_capacities * discount

    def estimate_optimal_portfolio_size(self,
                                         strategy_count: int,
                                         avg_strategy_capacity: float,
                                         avg_correlation: float) -> float:
        """Estimate optimal # of strategies given capacity constraints.

        Optimal ~ N * avg_capacity / (1 + (N-1) * avg_correlation) → N at max slope.
        """
        if avg_correlation <= 0:
            return float(strategy_count * avg_strategy_capacity)
        effective_n = strategy_count / (1 + (strategy_count - 1) * avg_correlation)
        return effective_n * avg_strategy_capacity

    def bottleneck_analysis(self) -> Dict[str, Any]:
        """Identify the most binding portfolio capacity constraints."""
        if not self._capacity_constraints:
            return {"bottlenecks": []}

        sorted_constraints = sorted(
            self._capacity_constraints, key=lambda c: c.utilization, reverse=True
        )
        bottlenecks = [c.to_dict() for c in sorted_constraints if c.utilization > 0.7]
        return {
            "bottlenecks": bottlenecks,
            "worst": sorted_constraints[0].to_dict() if sorted_constraints else {},
            "binding_count": sum(1 for c in self._capacity_constraints if c.is_binding),
        }

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
        all_keys = set(a.keys()) | set(b.keys())
        if not all_keys:
            return 0.0
        dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in all_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def summary(self) -> Dict[str, Any]:
        return {
            "strategy_count": len(self._strategy_assets),
            "asset_overlap_discount": round(self.compute_asset_overlap_penalty(), 4),
            "factor_overlap_discount": round(self.compute_factor_overlap_penalty(), 4),
            "composite_discount": round(self.compute_composite_discount(), 4),
            "constraint_count": len(self._capacity_constraints),
            "correlation_count": len(self._correlations),
            "bottlenecks": self.bottleneck_analysis(),
        }
