"""Backtest Manager — lifecycle coordinator for all backtesting subsystems.

Coordinates market replay, event engine, strategy runner, execution
simulation, and performance analysis through a unified interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .backtest_context import BacktestContext
from .backtest_registry import BacktestRegistry
from .backtest_repository import BacktestRepository
from .event_engine import EventEngine, BacktestEventType
from .market_replay import MarketReplay, ReplayMode
from .event_queue import BacktestEvent
from .strategy_runner import StrategyRunner
from .order_simulator import OrderSimulator
from .execution_simulator import ExecutionSimulator
from .slippage_model import SlippageModel, SlippageMethod
from .transaction_cost import TransactionCost
from .liquidity_model import LiquidityModel
from .performance_engine import PerformanceEngine
from .attribution_engine import AttributionEngine
from .benchmark_engine import BenchmarkEngine
from .corporate_action import CorporateActionProcessor
from .dividend_processor import DividendProcessor

logger = logging.getLogger(__name__)


class BacktestManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class BacktestManager:
    """Lifecycle coordinator for all backtesting subsystems.

    Responsibilities:
    * Bootstrap event engine, market replay, strategy runner
    * Orchestrate order and execution simulation
    * Coordinate performance analysis and attribution
    * Manage portfolio state during backtest
    * Generate comprehensive reports
    """

    def __init__(
        self,
        ctx: BacktestContext,
        registry: BacktestRegistry,
        repository: BacktestRepository,
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._repository = repository
        self._state = BacktestManagerState.UNINITIALIZED

        # Subsystems (initialized during initialize())
        self._event_engine: Optional[EventEngine] = None
        self._market_replay: Optional[MarketReplay] = None
        self._strategy_runner: Optional[StrategyRunner] = None
        self._order_simulator: Optional[OrderSimulator] = None
        self._execution_simulator: Optional[ExecutionSimulator] = None
        self._slippage_model: Optional[SlippageModel] = None
        self._transaction_cost: Optional[TransactionCost] = None
        self._liquidity_model: Optional[LiquidityModel] = None
        self._performance_engine: Optional[PerformanceEngine] = None
        self._attribution_engine: Optional[AttributionEngine] = None
        self._benchmark_engine: Optional[BenchmarkEngine] = None
        self._corporate_action: Optional[CorporateActionProcessor] = None
        self._dividend_processor: Optional[DividendProcessor] = None

        # Runtime state
        self._portfolio: Dict[str, Dict[str, Any]] = {}
        self._cash: float = 0.0
        self._equity_curve: List[Dict[str, Any]] = []
        self._paused = False

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        if self._state != BacktestManagerState.UNINITIALIZED:
            return

        self._state = BacktestManagerState.INITIALIZING
        logger.info("Initializing Backtest Manager subsystems...")

        # Core event-driven components
        mode = ReplayMode.DAILY if self._ctx.frequency == "daily" else ReplayMode.MINUTE
        self._event_engine = EventEngine()
        self._market_replay = MarketReplay(mode=mode)

        # Strategy
        self._strategy_runner = StrategyRunner(
            ctx=self._ctx,
            registry=self._registry,
        )

        # Order & execution
        self._order_simulator = OrderSimulator()
        self._slippage_model = SlippageModel(method=SlippageMethod.PERCENTAGE)
        self._liquidity_model = LiquidityModel()
        self._execution_simulator = ExecutionSimulator(
            slippage_model=self._slippage_model,
            liquidity_model=self._liquidity_model,
        )
        self._transaction_cost = TransactionCost()

        # Performance & attribution
        self._benchmark_engine = BenchmarkEngine()
        self._performance_engine = PerformanceEngine()
        self._attribution_engine = AttributionEngine()

        # Corporate actions
        self._corporate_action = CorporateActionProcessor()
        self._dividend_processor = DividendProcessor()

        # Wire event handlers
        self._wire_event_handlers()

        # Initialize portfolio
        self._cash = self._ctx.initial_capital
        self._portfolio = {}

        self._state = BacktestManagerState.READY
        logger.info("Backtest Manager initialized (state=ready)")

    async def execute_backtest(self, backtest_id: str) -> Dict[str, Any]:
        """Execute the event-driven backtest loop.

        Args:
            backtest_id: Unique identifier for this backtest run.

        Returns:
            Dictionary with execution results.
        """
        if self._state != BacktestManagerState.READY:
            raise RuntimeError(f"Manager not ready: {self._state.value}")
        if not self._market_replay or not self._event_engine:
            raise RuntimeError("Subsystems not initialized")

        self._state = BacktestManagerState.RUNNING
        logger.info("Starting event-driven backtest loop...")

        total_orders = 0
        total_trades = 0

        # Set up replay data source
        await self._market_replay.initialize(self._ctx)

        try:
            async for event in self._market_replay.replay():
                if self._paused:
                    await self._wait_for_resume()

                # Process corporate actions & dividends
                if self._corporate_action:
                    ca_events = await self._corporate_action.process(event)
                    for ca in ca_events:
                        self._event_engine.push(BacktestEvent(
                            event_type=BacktestEventType.CORPORATE_ACTION,
                            timestamp=event.get("timestamp", ""),
                            data=ca,
                        ))

                if self._dividend_processor:
                    div_events = await self._dividend_processor.process(event)
                    for div in div_events:
                        self._event_engine.push(BacktestEvent(
                            event_type=BacktestEventType.DIVIDEND,
                            timestamp=event.get("timestamp", ""),
                            data=div,
                        ))

                # Push market data event
                self._event_engine.push(BacktestEvent(
                    event_type=BacktestEventType.MARKET,
                    timestamp=event.get("timestamp", ""),
                    data=event.get("data", {}),
                    metadata=event.get("metadata", {}),
                ))

                # Dispatch all pending events
                await self._event_engine.dispatch(self._handle_event)

                # Record equity
                self._equity_curve.append({
                    "timestamp": event.get("timestamp", ""),
                    "equity": self._cash + self._compute_holdings_value(event),
                    "cash": self._cash,
                })

            # Final performance computation
            if self._performance_engine and self._equity_curve:
                performance = await self._performance_engine.compute(
                    equity_curve=self._equity_curve,
                    trades=self._repository.get_trades(backtest_id),
                    ctx=self._ctx,
                )
                await self._repository.save_performance(backtest_id, performance)

            if self._attribution_engine:
                attribution = await self._attribution_engine.compute(
                    trades=await self._repository.get_trades(backtest_id),
                    benchmark_returns=await self._get_benchmark_returns(),
                    performance=await self._repository.get_performance(backtest_id) or {},
                )
                await self._repository.save_report(backtest_id, {
                    "attribution": attribution,
                })

        finally:
            self._state = BacktestManagerState.READY

        return {
            "backtest_id": backtest_id,
            "total_orders": total_orders,
            "total_trades": total_trades,
            "final_equity": self._equity_curve[-1]["equity"] if self._equity_curve else self._ctx.initial_capital,
            "equity_curve_length": len(self._equity_curve),
            "summary": {
                "state": self._state.value,
            },
        }

    async def generate_report(
        self,
        backtest_id: str,
        format_type: str = "json",
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive backtest report."""
        performance = await self._repository.get_performance(backtest_id) or {}
        trades = await self._repository.get_trades(backtest_id) or []
        backtest = await self._repository.get_backtest(backtest_id) or {}

        report = {
            "backtest_id": backtest_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "format": format_type,
            "sections": {},
        }

        if not sections or "performance" in sections:
            report["sections"]["performance"] = performance

        if not sections or "trade_summary" in sections:
            report["sections"]["trade_summary"] = {
                "total_trades": len(trades),
                "buy_trades": sum(1 for t in trades if t.get("side") == "buy"),
                "sell_trades": sum(1 for t in trades if t.get("side") == "sell"),
                "avg_trade_size": (
                    sum(t.get("quantity", 0) * t.get("price", 0) for t in trades) / max(len(trades), 1)
                ),
            }

        if not sections or "equity_curve" in sections:
            report["sections"]["equity_curve"] = self._equity_curve

        if not sections or "config" in sections:
            report["sections"]["config"] = {
                "initial_capital": backtest.get("initial_capital"),
                "benchmark": backtest.get("benchmark"),
                "frequency": backtest.get("frequency"),
                "start_date": backtest.get("start_date"),
                "end_date": backtest.get("end_date"),
            }

        report["sections"]["summary"] = {
            **performance.get("summary", {}),
            "total_trades": len(trades),
            "backtest_duration_days": len(self._equity_curve),
        }

        return report

    async def pause(self) -> None:
        self._paused = True
        logger.info("Backtest Manager paused")

    async def resume(self) -> None:
        self._paused = False
        logger.info("Backtest Manager resumed")

    async def shutdown(self) -> None:
        self._state = BacktestManagerState.SHUTTING_DOWN
        logger.info("Shutting down Backtest Manager...")
        self._portfolio.clear()
        self._equity_curve.clear()
        self._state = BacktestManagerState.TERMINATED

    # ── event handling ─────────────────────────────────────────────────────

    def _wire_event_handlers(self) -> None:
        """Wire event handlers into the event engine."""
        if not self._event_engine:
            return
        self._event_engine.register_handler(
            BacktestEventType.MARKET, self._handle_market_event
        )
        self._event_engine.register_handler(
            BacktestEventType.SIGNAL, self._handle_signal_event
        )
        self._event_engine.register_handler(
            BacktestEventType.ORDER, self._handle_order_event
        )
        self._event_engine.register_handler(
            BacktestEventType.CORPORATE_ACTION, self._handle_corporate_action
        )
        self._event_engine.register_handler(
            BacktestEventType.DIVIDEND, self._handle_dividend_event
        )

    async def _handle_event(self, event: BacktestEvent) -> None:
        """Central event dispatcher callback."""
        await self._strategy_runner.handle_event(event)

    async def _handle_market_event(self, event: BacktestEvent) -> None:
        """Handle incoming market data events."""
        if self._strategy_runner:
            signals = await self._strategy_runner.on_market_data(event.data)
            for signal in signals:
                self._event_engine.push(BacktestEvent(
                    event_type=BacktestEventType.SIGNAL,
                    timestamp=event.timestamp,
                    data=signal,
                ))

    async def _handle_signal_event(self, event: BacktestEvent) -> None:
        """Handle trading signal events — generate orders."""
        if self._strategy_runner:
            orders = await self._strategy_runner.generate_orders(
                signal=event.data,
                portfolio=self._portfolio,
                cash=self._cash,
            )
            for order in orders:
                self._event_engine.push(BacktestEvent(
                    event_type=BacktestEventType.ORDER,
                    timestamp=event.timestamp,
                    data=order,
                ))

    async def _handle_order_event(self, event: BacktestEvent) -> None:
        """Handle order events — simulate execution."""
        if self._order_simulator and self._execution_simulator:
            # Validate order
            if not self._order_simulator.validate(event.data):
                logger.warning("Order rejected: %s", event.data.get("order_id"))
                return

            # Simulate execution
            result = await self._execution_simulator.execute(
                order=event.data,
                market_data=event.data.get("market_data", {}),
                cash=self._cash,
                portfolio=self._portfolio,
            )

            if result.get("status") == "filled":
                # Update portfolio
                trade = result["trade"]
                symbol = trade["symbol"]
                self._cash += trade.get("cash_flow", 0)
                current = self._portfolio.get(symbol, {"quantity": 0, "cost_basis": 0.0})
                new_qty = current["quantity"] + trade["quantity"]
                if abs(new_qty) < 1e-8:
                    self._portfolio.pop(symbol, None)
                else:
                    self._portfolio[symbol] = {
                        "quantity": new_qty,
                        "cost_basis": (current["cost_basis"] + trade.get("cost", 0))
                        / max(abs(new_qty), 1e-8),
                        "market_value": trade.get("price", 0) * new_qty,
                    }

    async def _handle_corporate_action(self, event: BacktestEvent) -> None:
        """Handle corporate action events — adjust positions."""
        if self._corporate_action:
            self._portfolio = await self._corporate_action.adjust_portfolio(
                event.data, self._portfolio
            )

    async def _handle_dividend_event(self, event: BacktestEvent) -> None:
        """Handle dividend events — credit cash."""
        if self._dividend_processor:
            result = await self._dividend_processor.apply(
                event.data, self._portfolio, self._cash
            )
            self._cash = result.get("cash", self._cash)

    # ── helpers ────────────────────────────────────────────────────────────

    async def _wait_for_resume(self, interval: float = 0.1) -> None:
        """Wait until the manager is resumed."""
        while self._paused:
            await asyncio.sleep(interval)

    def _compute_holdings_value(self, market_data: Dict[str, Any]) -> float:
        """Compute current portfolio holdings value."""
        value = 0.0
        prices = market_data.get("prices", {})
        for symbol, pos in self._portfolio.items():
            price = prices.get(symbol, pos.get("cost_basis", 0))
            value += pos.get("quantity", 0) * price
        return value

    async def _get_benchmark_returns(self) -> List[float]:
        """Get benchmark returns for attribution."""
        if self._benchmark_engine:
            return await self._benchmark_engine.get_returns(
                symbol=self._ctx.benchmark,
                start_date=self._ctx.start_date,
                end_date=self._ctx.end_date,
            )
        return []
