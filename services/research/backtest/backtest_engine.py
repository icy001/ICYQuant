"""Backtest Engine — unified entry point for institutional event-driven backtesting.

Architecture::

    Historical Dataset → Market Replay → Event Engine → Strategy Runner
    → Order Simulator → Execution Simulator → Portfolio Update
    → Performance Analysis → Backtest Report

The :class:`BacktestEngine` coordinates all backtesting capabilities through
a unified initialize/execute/generate_report interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .backtest_context import BacktestContext
from .backtest_manager import BacktestManager, BacktestManagerState
from .backtest_registry import BacktestRegistry
from .backtest_repository import BacktestRepository

logger = logging.getLogger(__name__)


class BacktestEngineState(str, Enum):
    """Backtest engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class BacktestEngine:
    """Unified institutional backtesting engine.

    Orchestrates the complete backtest lifecycle:
    1. Initialize — set up market replay, event engine, strategy, cost models
    2. Execute — run event-driven simulation over historical data
    3. Generate Report — produce comprehensive backtest report

    Usage::

        engine = BacktestEngine()
        await engine.initialize(ctx)
        result = await engine.execute()
        report = await engine.generate_report()
        await engine.shutdown()
    """

    def __init__(self) -> None:
        self._state = BacktestEngineState.UNINITIALIZED
        self._ctx: Optional[BacktestContext] = None
        self._manager: Optional[BacktestManager] = None
        self._registry = BacktestRegistry()
        self._repository = BacktestRepository()
        self._backtest_id: Optional[str] = None
        self._result: Dict[str, Any] = {}
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None

    @property
    def state(self) -> BacktestEngineState:
        return self._state

    @property
    def context(self) -> Optional[BacktestContext]:
        return self._ctx

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(
        self,
        ctx: Optional[BacktestContext] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> BacktestContext:
        """Initialize the backtest engine with context and configuration.

        Args:
            ctx: BacktestContext with strategy, universe, capital settings.
            config: Optional override configuration.

        Returns:
            The initialized BacktestContext.
        """
        if self._state not in (BacktestEngineState.UNINITIALIZED, BacktestEngineState.TERMINATED):
            raise RuntimeError(f"Cannot initialize from state: {self._state.value}")

        self._state = BacktestEngineState.INITIALIZING
        logger.info("Initializing Backtest Engine...")

        self._ctx = ctx or BacktestContext()
        if config:
            self._ctx = self._ctx.with_overrides(**config)

        self._manager = BacktestManager(
            ctx=self._ctx,
            registry=self._registry,
            repository=self._repository,
        )
        await self._manager.initialize()

        self._state = BacktestEngineState.READY
        logger.info("Backtest Engine initialized (state=ready)")

        # Unset the trace id since we reuse it and assign a specific id for this engine cycle
        self._ctx.trace_id = str(uuid4())
        return self._ctx

    async def execute(self) -> Dict[str, Any]:
        """Execute the backtest simulation.

        Returns:
            Dictionary with execution summary (backtest_id, status, runtime, trades).
        """
        if self._state != BacktestEngineState.READY:
            raise RuntimeError(f"Cannot execute from state: {self._state.value}")

        self._state = BacktestEngineState.RUNNING
        self._started_at = datetime.now(timezone.utc)
        logger.info("Starting backtest execution...")

        try:
            self._backtest_id = str(uuid4())

            # Register backtest record
            await self._repository.create_backtest({
                "id": self._backtest_id,
                "name": self._ctx.config.get("name", f"backtest_{self._backtest_id[:8]}"),
                "strategy_id": self._ctx.strategy_id,
                "universe": self._ctx.universe,
                "benchmark": self._ctx.benchmark,
                "frequency": self._ctx.frequency,
                "start_date": self._ctx.start_date,
                "end_date": self._ctx.end_date,
                "initial_capital": self._ctx.initial_capital,
                "status": "running",
                "config": self._ctx.config,
                "tags": list(self._ctx.tags.values()),
            })

            # Execute via manager
            self._result = await self._manager.execute_backtest(self._backtest_id)

            # Update backtest record
            self._completed_at = datetime.now(timezone.utc)
            runtime = (self._completed_at - self._started_at).total_seconds()
            await self._repository.update_backtest(self._backtest_id, {
                "status": "completed",
                "completed_at": self._completed_at.isoformat(),
                "runtime_seconds": runtime,
            })

            self._state = BacktestEngineState.READY
            logger.info(
                "Backtest completed: %s (trades=%d, runtime=%.1fs)",
                self._backtest_id[:8],
                self._result.get("total_trades", 0),
                runtime,
            )

            return {
                "backtest_id": self._backtest_id,
                "status": "completed",
                "runtime_seconds": runtime,
                "total_trades": self._result.get("total_trades", 0),
                "total_orders": self._result.get("total_orders", 0),
                "summary": self._result.get("summary", {}),
            }

        except Exception:
            logger.exception("Backtest execution failed")
            if self._backtest_id:
                await self._repository.update_backtest(self._backtest_id, {
                    "status": "failed",
                })
            self._state = BacktestEngineState.DEGRADED
            raise

    async def generate_report(
        self,
        format: str = "json",
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a comprehensive backtest report.

        Args:
            format: Output format (json, html).
            sections: Specific report sections to include.

        Returns:
            Dictionary with report data.
        """
        if self._state not in (BacktestEngineState.READY, BacktestEngineState.DEGRADED):
            raise RuntimeError(f"Cannot generate report from state: {self._state.value}")

        if not self._backtest_id:
            raise RuntimeError("No backtest has been executed")

        logger.info("Generating backtest report for %s...", self._backtest_id[:8])

        report = await self._manager.generate_report(
            backtest_id=self._backtest_id,
            format_type=format,
            sections=sections,
        )

        return report

    async def pause(self) -> None:
        """Pause the running backtest."""
        if self._state == BacktestEngineState.RUNNING:
            self._state = BacktestEngineState.PAUSED
            if self._manager:
                await self._manager.pause()
            logger.info("Backtest engine paused")

    async def resume(self) -> None:
        """Resume a paused backtest."""
        if self._state == BacktestEngineState.PAUSED:
            self._state = BacktestEngineState.RUNNING
            if self._manager:
                await self._manager.resume()
            logger.info("Backtest engine resumed")

    async def shutdown(self) -> None:
        """Gracefully shut down the backtest engine."""
        self._state = BacktestEngineState.SHUTTING_DOWN
        logger.info("Shutting down Backtest Engine...")
        if self._manager:
            await self._manager.shutdown()
        self._state = BacktestEngineState.TERMINATED
        logger.info("Backtest Engine terminated")

    # ── helpers ────────────────────────────────────────────────────────────

    async def get_status(self) -> Dict[str, Any]:
        """Return current engine status."""
        return {
            "state": self._state.value,
            "backtest_id": self._backtest_id,
            "initialized": self._state not in (
                BacktestEngineState.UNINITIALIZED,
                BacktestEngineState.TERMINATED,
            ),
            "initialized_at": self._started_at.isoformat() if self._started_at else None,
            "repository_stats": await self._repository.get_stats(),
            "registry_summary": self._registry.summary() if self._registry else {},
        }

    async def get_registry(self) -> BacktestRegistry:
        """Return the component registry for external registration."""
        return self._registry

    async def get_repository(self) -> BacktestRepository:
        """Return the data repository for querying results."""
        return self._repository
