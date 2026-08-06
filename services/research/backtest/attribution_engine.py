"""Attribution Engine — return decomposition and alpha source analysis.

Breaks down portfolio returns into allocation, selection, factor, and
timing components to identify alpha sources.

Components::

    Asset Allocation → Security Selection → Factor Exposure → Trading Timing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """Complete return attribution breakdown."""

    total_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0

    # Brinson-style attribution
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0

    # Factor-based attribution
    factor_attribution: Dict[str, float] = field(default_factory=dict)
    specific_return: float = 0.0

    # Timing
    timing_effect: float = 0.0
    execution_effect: float = 0.0

    # Unexplained
    residual: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": self.total_return,
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
            "allocation_effect": self.allocation_effect,
            "selection_effect": self.selection_effect,
            "interaction_effect": self.interaction_effect,
            "factor_attribution": self.factor_attribution,
            "specific_return": self.specific_return,
            "timing_effect": self.timing_effect,
            "execution_effect": self.execution_effect,
            "residual": self.residual,
        }


class AttributionEngine:
    """Portfolio return attribution engine.

    Decomposes returns into explainable components:
    * Brinson attribution (allocation, selection, interaction)
    * Factor-based attribution
    * Timing and execution effects

    Usage::

        engine = AttributionEngine()
        result = await engine.compute(trades, benchmark_returns, performance)
    """

    def __init__(self) -> None:
        self._sectors: Dict[str, str] = {}  # symbol → sector mapping
        self._factor_exposures: Dict[str, Dict[str, float]] = {}  # symbol → factor → exposure

    # ── computation ────────────────────────────────────────────────────────

    async def compute(
        self,
        trades: List[Dict[str, Any]],
        benchmark_returns: Optional[List[float]] = None,
        performance: Optional[Dict[str, Any]] = None,
        sector_weights: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> AttributionResult:
        """Compute return attribution.

        Args:
            trades: List of trade records.
            benchmark_returns: Benchmark return series.
            performance: Performance metrics dict.
            sector_weights: Optional sector weight data.

        Returns:
            Comprehensive AttributionResult.
        """
        result = AttributionResult()

        # Get total return from performance
        if performance:
            result.total_return = performance.get("total_return", 0.0)
            result.benchmark_return = performance.get("benchmark_return", 0.0)
            result.excess_return = performance.get("excess_return", 0.0)

        # Brinson attribution
        if sector_weights:
            await self._brinson_attribution(trades, sector_weights, result)

        # Factor attribution
        if self._factor_exposures:
            await self._factor_attribution(trades, result)

        # Timing & execution effects
        await self._timing_attribution(trades, result)

        # Compute residual
        explained = (
            result.allocation_effect
            + result.selection_effect
            + result.interaction_effect
            + result.specific_return
            + result.timing_effect
            + result.execution_effect
        )
        result.residual = result.excess_return - explained

        return result

    async def _brinson_attribution(
        self,
        trades: List[Dict[str, Any]],
        sector_weights: Dict[str, Dict[str, float]],
        result: AttributionResult,
    ) -> None:
        """Brinson-style attribution (allocation + selection + interaction).

        R = Σ (w_pi * r_pi) - Σ (w_bi * r_bi)

        Allocation = Σ (w_pi - w_bi) * r_bi
        Selection  = Σ w_bi * (r_pi - r_bi)
        Interaction = Σ (w_pi - w_bi) * (r_pi - r_bi)
        """
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector, data in sector_weights.items():
            w_p = data.get("portfolio_weight", 0.0)
            w_b = data.get("benchmark_weight", 0.0)
            r_p = data.get("portfolio_return", 0.0)
            r_b = data.get("benchmark_return", 0.0)

            total_allocation += (w_p - w_b) * r_b
            total_selection += w_b * (r_p - r_b)
            total_interaction += (w_p - w_b) * (r_p - r_b)

        result.allocation_effect = total_allocation
        result.selection_effect = total_selection
        result.interaction_effect = total_interaction

    async def _factor_attribution(
        self,
        trades: List[Dict[str, Any]],
        result: AttributionResult,
    ) -> None:
        """Factor-based return attribution."""
        # Extract symbols from trades
        symbols = set(t.get("symbol", "") for t in trades)
        factor_returns: Dict[str, float] = {}

        for symbol in symbols:
            exposures = self._factor_exposures.get(symbol, {})
            for factor, exposure in exposures.items():
                factor_returns[factor] = factor_returns.get(factor, 0.0) + exposure

        # Normalize
        total = sum(abs(v) for v in factor_returns.values()) or 1.0
        for factor in factor_returns:
            factor_returns[factor] /= total

        result.factor_attribution = factor_returns
        result.specific_return = result.excess_return - sum(factor_returns.values())

    async def _timing_attribution(
        self,
        trades: List[Dict[str, Any]],
        result: AttributionResult,
    ) -> None:
        """Estimate timing and execution effects from trade data."""
        if not trades:
            return

        # Timing: compare actual entry prices vs signal-generation prices
        timing_pnl = 0.0
        exec_pnl = 0.0

        for trade in trades:
            signal_price = trade.get("signal_price", trade.get("price", 0))
            exec_price = trade.get("price", 0)
            qty = trade.get("quantity", 0)
            side = 1 if trade.get("side") == "buy" else -1

            if signal_price > 0:
                timing_pnl += (exec_price - signal_price) * qty * (-side)
            # Execution effect (slippage from expected)
            expected_price = trade.get("expected_price", exec_price)
            exec_pnl += (exec_price - expected_price) * qty * (-side)

        total_value = sum(abs(t.get("quantity", 0) * t.get("price", 0)) for t in trades) or 1
        result.timing_effect = timing_pnl / total_value
        result.execution_effect = exec_pnl / total_value

    # ── factor exposure management ─────────────────────────────────────────

    def set_factor_exposure(
        self,
        symbol: str,
        factor: str,
        exposure: float,
    ) -> None:
        """Set a factor exposure for a symbol."""
        if symbol not in self._factor_exposures:
            self._factor_exposures[symbol] = {}
        self._factor_exposures[symbol][factor] = exposure

    def set_sector_mapping(self, symbol: str, sector: str) -> None:
        """Map a symbol to a sector."""
        self._sectors[symbol] = sector

    def get_exposures(self, symbol: str) -> Dict[str, float]:
        """Get factor exposures for a symbol."""
        return self._factor_exposures.get(symbol, {})

    def get_stats(self) -> Dict[str, Any]:
        """Return attribution engine statistics."""
        return {
            "symbols_with_exposures": len(self._factor_exposures),
            "sectors_mapped": len(self._sectors),
            "total_factors": len(
                set(
                    factor
                    for exposures in self._factor_exposures.values()
                    for factor in exposures
                )
            ),
        }
