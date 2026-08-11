"""Backtest Adapter — Connect EMS algorithms to historical data for backtesting.

Provides an adapter that connects execution algorithms to historical
market data, enabling backtesting of execution strategies against
real market conditions.

Pipeline::

    Historical Data → BacktestAdapter → Algorithm → Simulated Fills → Analysis

Usage::

    adapter = BacktestAdapter(simulator=simulator)
    adapter.load_data(historical_bars)
    result = await adapter.run_backtest(strategy="TWAP", context=ctx)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.algorithm.strategy_registry import StrategyRegistry
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata
from services.ems.execution_quality import ExecutionQualityAnalyzer, QualityMetrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestBar:
    """A single bar of historical market data."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float = 0.0

    def __post_init__(self) -> None:
        if self.vwap <= 0:
            self.vwap = (self.high + self.low + self.close) / 3.0


@dataclass
class BacktestResult:
    """Results from an execution backtest."""

    strategy: str
    total_quantity: float = 0.0
    filled_quantity: float = 0.0
    fill_pct: float = 0.0
    average_price: float = 0.0
    benchmark_price: float = 0.0
    market_vwap: float = 0.0
    slippage_bps: float = 0.0
    total_commission: float = 0.0
    child_orders_created: int = 0
    child_orders_filled: int = 0
    duration_seconds: float = 0.0
    quality_metrics: Optional[QualityMetrics] = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "strategy": self.strategy,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "fill_pct": self.fill_pct,
            "average_price": self.average_price,
            "benchmark_price": self.benchmark_price,
            "market_vwap": self.market_vwap,
            "slippage_bps": self.slippage_bps,
            "total_commission": self.total_commission,
            "child_orders_created": self.child_orders_created,
            "child_orders_filled": self.child_orders_filled,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
        }
        if self.quality_metrics:
            result["quality"] = self.quality_metrics.to_dict()
        return result


class BacktestAdapter:
    """Adapter for backtesting execution algorithms.

    Connects execution strategies to historical market data,
    simulating fills using historical bars and evaluating
    execution quality.

    Attributes:
        registry: Strategy registry
        quality_analyzer: Execution quality analyzer
        _bars: Loaded historical bars
        _bar_index: Current position in bars
    """

    def __init__(self) -> None:
        self.registry = StrategyRegistry()
        self.quality_analyzer = ExecutionQualityAnalyzer()
        self._bars: list[BacktestBar] = []
        self._bar_index: int = 0

    # ── Data Loading ───────────────────────────────────────────────

    def load_data(self, bars: list[dict[str, Any] | BacktestBar]) -> None:
        """Load historical market data for backtesting.

        Args:
            bars: List of bar dicts or BacktestBar objects
        """
        self._bars = []
        for bar in bars:
            if isinstance(bar, BacktestBar):
                self._bars.append(bar)
            else:
                self._bars.append(BacktestBar(
                    timestamp=datetime.fromisoformat(bar["timestamp"]) if isinstance(bar["timestamp"], str) else bar["timestamp"],
                    open=bar["open"],
                    high=bar["high"],
                    low=bar["low"],
                    close=bar["close"],
                    volume=bar["volume"],
                    vwap=bar.get("vwap", 0.0),
                ))

        # Sort by timestamp
        self._bars.sort(key=lambda b: b.timestamp)
        self._bar_index = 0

        logger.info("Loaded %d bars for backtesting", len(self._bars))

    # ── Backtest Execution ─────────────────────────────────────────

    async def run_backtest(
        self,
        context: ExecutionContext,
        strategy_name: str = "TWAP",
    ) -> BacktestResult:
        """Run a backtest of an execution strategy.

        Simulates the full execution lifecycle against historical data.

        Args:
            context: Execution context
            strategy_name: Strategy to test

        Returns:
            BacktestResult with performance metrics
        """
        strategy = self.registry.get(strategy_name)
        if not strategy:
            return BacktestResult(
                strategy=strategy_name,
                errors=[f"Unknown strategy: {strategy_name}"],
            )

        # Reset state
        self._bar_index = 0

        # Initialize strategy
        await strategy.initialize(context)

        # Initialize metadata
        metadata = ExecutionMetadata(
            algorithm=strategy_name,
            target_quantity=context.total_quantity,
            remaining_quantity=context.total_quantity,
            benchmark_price=self._get_current_price(),
        )
        metadata.start()

        child_orders: list[ChildOrder] = []
        filled_children = 0
        start_time = datetime.now(timezone.utc)

        # Main backtest loop
        while not strategy.is_complete and self._bar_index < len(self._bars):
            bar = self._bars[self._bar_index]

            # Update strategy with market data
            self._update_context_market_data(context, bar)
            await strategy.update(metadata)

            # Get next child order
            child = await strategy.next_child_order(metadata)
            if child:
                child_orders.append(child)
                metadata.record_child_order(child.order_id)

                # Simulate fill using historical data
                fill_result = self._simulate_fill_from_bar(child, bar)
                if fill_result:
                    fill_qty, fill_price = fill_result
                    child.apply_fill(fill_qty, fill_price)
                    metadata.apply_fill(fill_qty, fill_price)

                    if child.is_filled:
                        filled_children += 1
                        metadata.record_child_filled(child.order_id)
                        await strategy.on_fill(child, metadata)

            self._bar_index += 1

        # Complete strategy
        await strategy.complete()
        metadata.complete()

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Calculate market VWAP over the period
        market_vwap = self._compute_market_vwap()

        # Compute quality metrics
        quality = self.quality_analyzer.compute_metrics(
            average_price=metadata.average_price,
            benchmark_price=metadata.benchmark_price,
            market_vwap=market_vwap,
            quantity=metadata.filled_quantity,
            market_volume=sum(b.volume for b in self._bars[:self._bar_index]),
            duration_seconds=duration,
        )

        # Compute slippage
        slippage_bps = 0.0
        if metadata.benchmark_price > 0 and metadata.average_price > 0:
            slippage_bps = (metadata.average_price - metadata.benchmark_price) / metadata.benchmark_price * 10000

        logger.info(
            "Backtest complete: strategy=%s fill=%.1f%% avg_price=%.4f slip=%.1fbps quality=%.0f",
            strategy_name,
            metadata.fill_pct * 100,
            metadata.average_price,
            slippage_bps,
            quality.overall,
        )

        return BacktestResult(
            strategy=strategy_name,
            total_quantity=metadata.target_quantity,
            filled_quantity=metadata.filled_quantity,
            fill_pct=metadata.fill_pct,
            average_price=metadata.average_price,
            benchmark_price=metadata.benchmark_price,
            market_vwap=market_vwap,
            slippage_bps=slippage_bps,
            total_commission=metadata.total_commission,
            child_orders_created=len(child_orders),
            child_orders_filled=filled_children,
            duration_seconds=duration,
            quality_metrics=quality,
        )

    async def compare_strategies(
        self,
        context: ExecutionContext,
        strategies: list[str] | None = None,
    ) -> list[BacktestResult]:
        """Compare multiple strategies on the same data.

        Args:
            context: Execution context
            strategies: List of strategies to compare (default: all registered)

        Returns:
            List of BacktestResult sorted by quality score
        """
        if strategies is None:
            strategies = self.registry.list_strategies()

        results = []
        for name in strategies:
            result = await self.run_backtest(context, name)
            results.append(result)

        # Sort by quality score
        results.sort(
            key=lambda r: r.quality_metrics.overall if r.quality_metrics else 0,
            reverse=True,
        )

        return results

    # ── Helpers ────────────────────────────────────────────────────

    def _get_current_price(self) -> float:
        """Get current market price from bars."""
        if self._bar_index < len(self._bars):
            return self._bars[self._bar_index].close
        return 0.0

    def _get_current_volume(self) -> float:
        """Get current volume from bars."""
        if self._bar_index < len(self._bars):
            return self._bars[self._bar_index].volume
        return 0.0

    @staticmethod
    def _update_context_market_data(context: ExecutionContext, bar: BacktestBar) -> None:
        """Update context with market data from a bar.

        Args:
            context: Execution context to update
            bar: Historical bar data
        """
        # Feed market signals to the context
        context.strategy_params.setdefault("current_price", bar.close)
        context.strategy_params["current_price"] = bar.close
        context.strategy_params.setdefault("current_volume", bar.volume)
        context.strategy_params["current_volume"] = bar.volume
        context.strategy_params.setdefault("market_vwap", bar.vwap)
        context.strategy_params["market_vwap"] = bar.vwap

    def _simulate_fill_from_bar(
        self, child: ChildOrder, bar: BacktestBar
    ) -> Optional[tuple[float, float]]:
        """Simulate a fill using historical bar data.

        Args:
            child: Child order
            bar: Historical bar

        Returns:
            Tuple of (fill_qty, fill_price) or None
        """
        # Determine fill price based on bar OHLC and order side
        if str(child.side).upper() == "BUY":
            # Buy at somewhere between open and high
            fill_price = bar.open + (bar.high - bar.open) * 0.5
        else:
            # Sell at somewhere between open and low
            fill_price = bar.open - (bar.open - bar.low) * 0.5

        # Fill quantity proportional to bar volume
        max_fill = min(child.remaining_quantity, bar.volume * 0.05)  # Max 5% of bar volume
        if max_fill <= 0:
            return None

        # 80% chance of getting a fill
        import random
        if random.random() > 0.80:
            return None

        fill_qty = max_fill * random.uniform(0.5, 1.0)
        fill_qty = round(fill_qty, 2)

        if fill_qty <= 0:
            return None

        return fill_qty, fill_price

    def _compute_market_vwap(self) -> float:
        """Compute market VWAP over the backtest period.

        Returns:
            Volume-weighted average price
        """
        bars = self._bars[:self._bar_index]
        if not bars:
            return 0.0

        total_notional = sum(b.vwap * b.volume for b in bars)
        total_volume = sum(b.volume for b in bars)

        return total_notional / total_volume if total_volume > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize adapter state."""
        return {
            "bars_loaded": len(self._bars),
            "bar_index": self._bar_index,
            "strategies": self.registry.list_strategies(),
        }
