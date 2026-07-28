"""AI Performance Attribution Engine — decompose portfolio returns.

Supports Brinson, factor-based, and multi-level performance attribution.
Breaks down returns into allocation effects, selection effects, interaction
effects, and risk factor contributions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AttributionMethod(str, Enum):
    """Attribution methodologies."""

    BRINSON = "brinson"  # Brinson-Hood-Beebower
    FACTOR_BASED = "factor_based"  # Risk factor decomposition
    MULTI_LEVEL = "multi_level"  # Hierarchical attribution
    TRANSACTION = "transaction"  # Trade-level attribution


class AttributionLevel(str, Enum):
    """Attribution granularity levels."""

    TOTAL = "total"
    ASSET_CLASS = "asset_class"
    SECTOR = "sector"
    STRATEGY = "strategy"
    SECURITY = "security"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AttributionComponent:
    """Single attribution component.

    Attributes:
        name: Component name (e.g., "allocation_effect", "selection_effect").
        contribution: Return contribution in %.
        weight: Relative weight of this component.
        description: Human-readable description.
    """

    name: str
    contribution: float
    weight: float = 0.0
    description: str = ""

    @property
    def contribution_bps(self) -> float:
        """Contribution in basis points."""
        return self.contribution * 10000


@dataclass
class AttributionResult:
    """Performance attribution result.

    Attributes:
        method: Attribution methodology used.
        level: Attribution granularity level.
        total_return: Total portfolio return for the period.
        benchmark_return: Benchmark return for the period.
        excess_return: Portfolio return - benchmark return.
        components: List of attribution components.
        top_contributors: Top positive contributors.
        top_detractors: Top negative contributors.
        timestamp: Attribution time.
        metadata: Additional context.
    """

    method: AttributionMethod
    level: AttributionLevel = AttributionLevel.TOTAL
    total_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    components: list[AttributionComponent] = field(default_factory=list)
    top_contributors: list[AttributionComponent] = field(default_factory=list)
    top_detractors: list[AttributionComponent] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def excess_return_bps(self) -> float:
        """Excess return in basis points."""
        return self.excess_return * 10000

    @property
    def tracking_error(self) -> float:
        """Approximate tracking error from component dispersion."""
        contribs = [c.contribution for c in self.components]
        if len(contribs) < 2:
            return 0.0
        mean = sum(contribs) / len(contribs)
        variance = sum((c - mean) ** 2 for c in contribs) / (len(contribs) - 1)
        return variance**0.5

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "method": self.method.value,
            "level": self.level.value,
            "total_return": round(self.total_return, 6),
            "benchmark_return": round(self.benchmark_return, 6),
            "excess_return_bps": round(self.excess_return_bps, 2),
            "components": [
                {
                    "name": c.name,
                    "contribution_bps": round(c.contribution_bps, 2),
                    "weight": round(c.weight, 4),
                }
                for c in self.components
            ],
            "top_contributors": [c.name for c in self.top_contributors[:5]],
            "top_detractors": [c.name for c in self.top_detractors[:5]],
        }


# ---------------------------------------------------------------------------
# AttributionEngine
# ---------------------------------------------------------------------------


class AttributionEngine:
    """AI performance attribution engine.

    Decomposes portfolio returns into allocation effect, selection effect,
    interaction effect, and factor contributions. Supports multiple
    attribution methodologies at various granularity levels.

    Attributes:
        method: Default attribution method.
        level: Default attribution level.
        history: Past attribution results.
    """

    FACTOR_NAMES: dict[str, str] = {
        "market": "Market (Beta)",
        "size": "Size (SMB)",
        "value": "Value (HML)",
        "momentum": "Momentum",
        "quality": "Quality",
        "low_vol": "Low Volatility",
    }

    def __init__(
        self,
        method: AttributionMethod = AttributionMethod.BRINSON,
        level: AttributionLevel = AttributionLevel.TOTAL,
    ) -> None:
        """Initialize the attribution engine.

        Args:
            method: Default attribution method.
            level: Default attribution level.
        """
        self.method = method
        self.level = level
        self.history: list[AttributionResult] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def attribute(
        self,
        portfolio_data: dict[str, Any],
        benchmark_data: dict[str, Any],
        method: Optional[AttributionMethod] = None,
        level: Optional[AttributionLevel] = None,
    ) -> AttributionResult:
        """Attribute portfolio returns to sources.

        Args:
            portfolio_data: Dict with keys: total_return, weights (per-asset dict),
                            returns (per-asset dict), factor_exposures (optional).
            benchmark_data: Same structure for benchmark.
            method: Override default method.
            level: Override default level.

        Returns:
            AttributionResult with return decomposition.
        """
        method = method or self.method
        level = level or self.level

        if method == AttributionMethod.BRINSON:
            components, top_c, top_d = self._attribute_brinson(portfolio_data, benchmark_data)
        elif method == AttributionMethod.FACTOR_BASED:
            components, top_c, top_d = self._attribute_factor(portfolio_data, benchmark_data)
        elif method == AttributionMethod.MULTI_LEVEL:
            components, top_c, top_d = self._attribute_multi_level(portfolio_data, benchmark_data)
        elif method == AttributionMethod.TRANSACTION:
            components, top_c, top_d = self._attribute_transaction(portfolio_data, benchmark_data)
        else:
            components, top_c, top_d = self._attribute_brinson(portfolio_data, benchmark_data)

        total_ret = portfolio_data.get("total_return", 0.0)
        bench_ret = benchmark_data.get("total_return", 0.0)
        excess = total_ret - bench_ret

        result = AttributionResult(
            method=method,
            level=level,
            total_return=total_ret,
            benchmark_return=bench_ret,
            excess_return=excess,
            components=components,
            top_contributors=top_c[:5],
            top_detractors=top_d[:5],
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Brinson Attribution
    # ------------------------------------------------------------------

    def _attribute_brinson(
        self,
        portfolio_data: dict[str, Any],
        benchmark_data: dict[str, Any],
    ) -> tuple[list[AttributionComponent], list[AttributionComponent], list[AttributionComponent]]:
        """Brinson-Hood-Beebower attribution: allocation, selection, interaction."""
        p_weights = portfolio_data.get("weights", {})
        b_weights = benchmark_data.get("weights", {})
        p_returns = portfolio_data.get("returns", {})
        b_returns = benchmark_data.get("returns", {})

        all_categories = sorted(set(list(p_weights.keys()) + list(b_weights.keys())))

        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0

        details = []

        for cat in all_categories:
            pw = p_weights.get(cat, 0.0)
            bw = b_weights.get(cat, 0.0)
            pr = p_returns.get(cat, 0.0)
            br = b_returns.get(cat, 0.0)

            # Allocation effect: (pw - bw) * (br - bench_total)
            alloc = (pw - bw) * br
            allocation_effect += alloc

            # Selection effect: bw * (pr - br)
            select = bw * (pr - br)
            selection_effect += select

            # Interaction effect: (pw - bw) * (pr - br)
            inter = (pw - bw) * (pr - br)
            interaction_effect += inter

            total_contrib = alloc + select + inter
            details.append(
                (cat, total_contrib, alloc, select, inter)
            )

        components = [
            AttributionComponent(
                name="Allocation Effect",
                contribution=allocation_effect,
                weight=abs(allocation_effect) / max(abs(allocation_effect) + abs(selection_effect) + abs(interaction_effect), 0.0001),
                description="Return from overweighting outperforming categories",
            ),
            AttributionComponent(
                name="Selection Effect",
                contribution=selection_effect,
                weight=abs(selection_effect) / max(abs(allocation_effect) + abs(selection_effect) + abs(interaction_effect), 0.0001),
                description="Return from selecting superior securities within categories",
            ),
            AttributionComponent(
                name="Interaction Effect",
                contribution=interaction_effect,
                weight=abs(interaction_effect) / max(abs(allocation_effect) + abs(selection_effect) + abs(interaction_effect), 0.0001),
                description="Cross-term from simultaneous active weight and return differences",
            ),
        ]

        # Per-category detail components
        for cat, total_c, alloc, sel, inter in details:
            if abs(total_c) > 0.0001:
                components.append(
                    AttributionComponent(
                        name=f"{cat} (Total)",
                        contribution=total_c,
                        description=f"Alloc={alloc:.4%}, Sel={sel:.4%}, Inter={inter:.4%}",
                    )
                )

        # Sort top contributors and detractors
        all_contribs = sorted(components, key=lambda c: c.contribution, reverse=True)
        top_c = [c for c in all_contribs if c.contribution > 0]
        top_d = [c for c in all_contribs if c.contribution < 0]
        top_d.reverse()

        return components, top_c, top_d

    # ------------------------------------------------------------------
    # Factor-Based Attribution
    # ------------------------------------------------------------------

    def _attribute_factor(
        self,
        portfolio_data: dict[str, Any],
        benchmark_data: dict[str, Any],
    ) -> tuple[list[AttributionComponent], list[AttributionComponent], list[AttributionComponent]]:
        """Factor-based return decomposition."""
        p_factors = portfolio_data.get("factor_exposures", {})
        b_factors = benchmark_data.get("factor_exposures", {})
        factor_returns = portfolio_data.get("factor_returns", {})

        all_factors = sorted(set(list(p_factors.keys()) + list(b_factors.keys())))

        components = []
        for factor in all_factors:
            p_exp = p_factors.get(factor, 0.0)
            b_exp = b_factors.get(factor, 0.0)
            f_ret = factor_returns.get(factor, 0.0)

            # Active factor exposure * factor return
            active_exposure = p_exp - b_exp
            contrib = active_exposure * f_ret

            components.append(
                AttributionComponent(
                    name=self.FACTOR_NAMES.get(factor, factor),
                    contribution=contrib,
                    weight=abs(active_exposure),
                    description=f"Active exposure: {active_exposure:+.3f}, Factor return: {f_ret:.4%}",
                )
            )

        # Residual (alpha) - unexplained portion
        total_factor = sum(c.contribution for c in components)
        total_excess = portfolio_data.get("total_return", 0.0) - benchmark_data.get("total_return", 0.0)
        residual = total_excess - total_factor
        components.append(
            AttributionComponent(
                name="Alpha (Residual)",
                contribution=residual,
                description=f"Unexplained excess return (actual {total_excess:.4%} - factor {total_factor:.4%})",
            )
        )

        all_contribs = sorted(components, key=lambda c: c.contribution, reverse=True)
        top_c = [c for c in all_contribs if c.contribution > 0]
        top_d = [c for c in all_contribs if c.contribution < 0]
        top_d.reverse()

        return components, top_c, top_d

    # ------------------------------------------------------------------
    # Multi-Level Attribution
    # ------------------------------------------------------------------

    def _attribute_multi_level(
        self,
        portfolio_data: dict[str, Any],
        benchmark_data: dict[str, Any],
    ) -> tuple[list[AttributionComponent], list[AttributionComponent], list[AttributionComponent]]:
        """Multi-level attribution: Brinson at multiple hierarchy levels."""
        # Run Brinson at each level
        components = []

        levels = [
            (AttributionLevel.ASSET_CLASS, "asset_weights", "asset_returns"),
            (AttributionLevel.SECTOR, "sector_weights", "sector_returns"),
        ]

        for level, w_key, r_key in levels:
            sub_portfolio = {
                "weights": portfolio_data.get(w_key, {}),
                "returns": portfolio_data.get(r_key, {}),
            }
            sub_benchmark = {
                "weights": benchmark_data.get(w_key, {}),
                "returns": benchmark_data.get(r_key, {}),
            }
            subs, _, _ = self._attribute_brinson(sub_portfolio, sub_benchmark)
            for c in subs:
                c.name = f"[{level.value}] {c.name}"
                components.append(c)

        # Security-level attribution via Brinson
        sec_comps, tc, td = self._attribute_brinson(portfolio_data, benchmark_data)
        for c in sec_comps:
            c.name = f"[{AttributionLevel.SECURITY.value}] {c.name}"
            components.append(c)

        all_contribs = sorted(components, key=lambda c: c.contribution, reverse=True)
        top_c = [c for c in all_contribs if c.contribution > 0]
        top_d = [c for c in all_contribs if c.contribution < 0]
        top_d.reverse()

        return components, top_c, top_d

    # ------------------------------------------------------------------
    # Transaction Attribution
    # ------------------------------------------------------------------

    def _attribute_transaction(
        self,
        portfolio_data: dict[str, Any],
        benchmark_data: dict[str, Any],
    ) -> tuple[list[AttributionComponent], list[AttributionComponent], list[AttributionComponent]]:
        """Trade-level attribution: decompose returns from realized P&L."""
        trades = portfolio_data.get("trades", [])
        components = []

        for i, trade in enumerate(trades[:20]):  # top 20 trades
            symbol = trade.get("symbol", f"trade_{i}")
            pnl = trade.get("pnl", 0.0)
            side = trade.get("side", "unknown")

            components.append(
                AttributionComponent(
                    name=f"{symbol} ({side})",
                    contribution=pnl,
                    weight=abs(pnl),
                    description=trade.get("note", ""),
                )
            )

        # Aggregate the rest
        if len(trades) > 20:
            rest_pnl = sum(t.get("pnl", 0.0) for t in trades[20:])
            if abs(rest_pnl) > 0.0001:
                components.append(
                    AttributionComponent(
                        name=f"Other ({len(trades) - 20} trades)",
                        contribution=rest_pnl,
                        weight=abs(rest_pnl),
                        description="Aggregated remaining trades",
                    )
                )

        # Costs
        total_cost = portfolio_data.get("total_cost", 0.0)
        if total_cost != 0:
            components.append(
                AttributionComponent(
                    name="Transaction Costs",
                    contribution=-total_cost,
                    weight=abs(total_cost),
                    description="Slippage, commissions, and fees",
                )
            )

        all_contribs = sorted(components, key=lambda c: c.contribution, reverse=True)
        top_c = [c for c in all_contribs if c.contribution > 0]
        top_d = [c for c in all_contribs if c.contribution < 0]
        top_d.reverse()

        return components, top_c, top_d

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_attribute(
        self,
        portfolio_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_weights: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> dict[str, Any]:
        """Quick Brinson attribution with weights and returns.

        Args:
            portfolio_weights: Portfolio weights by category.
            portfolio_returns: Portfolio returns by category.
            benchmark_weights: Benchmark weights by category.
            benchmark_returns: Benchmark returns by category.

        Returns:
            Dict with attribution summary.
        """
        total_p = sum(portfolio_weights.get(c, 0) * portfolio_returns.get(c, 0)
                      for c in portfolio_weights)
        total_b = sum(benchmark_weights.get(c, 0) * benchmark_returns.get(c, 0)
                      for c in benchmark_weights)

        result = self.attribute(
            portfolio_data={
                "total_return": total_p,
                "weights": portfolio_weights,
                "returns": portfolio_returns,
            },
            benchmark_data={
                "total_return": total_b,
                "weights": benchmark_weights,
                "returns": benchmark_returns,
            },
        )
        return {
            "method": result.method.value,
            "total_return_bps": round(result.total_return * 10000, 2),
            "benchmark_return_bps": round(result.benchmark_return * 10000, 2),
            "excess_return_bps": round(result.excess_return_bps, 2),
            "components": {
                c.name: round(c.contribution_bps, 2)
                for c in result.components
                if c.name in ("Allocation Effect", "Selection Effect", "Interaction Effect")
            },
        }

    def last_result(self) -> Optional[AttributionResult]:
        """Return the most recent attribution result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset attribution history."""
        self.history.clear()
