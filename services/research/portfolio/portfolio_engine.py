"""Portfolio Engine — unified entry point for institutional portfolio research.

Architecture::

    Alpha Pool → Portfolio Builder → Optimizer → Constraint Engine
    → Risk Model → Scenario Analysis → Portfolio Report

The :class:`PortfolioEngine` coordinates all portfolio research through
a unified construct/optimize/analyze interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .portfolio_context import PortfolioContext
from .portfolio_manager import PortfolioManager, PortfolioManagerState
from .portfolio_registry import PortfolioRegistry
from .portfolio_repository import PortfolioRepository

logger = logging.getLogger(__name__)


class PortfolioEngineState(str, Enum):
    """Portfolio engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class PortfolioEngine:
    """Unified institutional portfolio research engine.

    Orchestrates the complete portfolio research lifecycle:
    1. Construct — build portfolio from alpha pool or strategy output
    2. Optimize — apply optimization (MV, RP, BL, HRP) with constraints
    3. Analyze — risk analysis, stress testing, attribution, reporting

    Usage::

        engine = PortfolioEngine()
        await engine.initialize(ctx)
        portfolio = await engine.construct(alpha_pool="momentum")
        optimized = await engine.optimize(portfolio)
        report = await engine.analyze(optimized)
        await engine.shutdown()
    """

    def __init__(self) -> None:
        self._state = PortfolioEngineState.UNINITIALIZED
        self._ctx: Optional[PortfolioContext] = None
        self._registry = PortfolioRegistry()
        self._repository = PortfolioRepository()
        self._manager: Optional[PortfolioManager] = None
        self._initialized_at: Optional[datetime] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self, ctx: PortfolioContext) -> None:
        self._state = PortfolioEngineState.INITIALIZING
        self._ctx = ctx
        self._initialized_at = datetime.now(timezone.utc)
        self._manager = PortfolioManager(ctx, self._registry, self._repository)
        await self._manager.initialize()
        self._state = PortfolioEngineState.READY
        logger.info("PortfolioEngine initialized (session=%s)", ctx.session_id)

    async def shutdown(self) -> None:
        self._state = PortfolioEngineState.SHUTTING_DOWN
        if self._manager:
            await self._manager.shutdown()
        self._state = PortfolioEngineState.TERMINATED
        logger.info("PortfolioEngine shutdown complete")

    # ── construction ───────────────────────────────────────────────────────

    async def construct(
        self,
        alpha_pool: Optional[str] = None,
        universe: Optional[List[str]] = None,
        method: str = "equal_weight",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Construct a portfolio from alpha pool or universe."""
        self._ensure_state(PortfolioEngineState.READY)
        self._state = PortfolioEngineState.RUNNING
        try:
            assert self._manager is not None
            result = await self._manager.construct_portfolio(
                alpha_pool=alpha_pool or (self._ctx.alpha_pool if self._ctx else []),
                universe=universe or (self._ctx.universe if self._ctx else []),
                method=method,
                **kwargs,
            )
            return result
        finally:
            self._state = PortfolioEngineState.READY

    # ── optimization ───────────────────────────────────────────────────────

    async def optimize(
        self,
        portfolio: Dict[str, Any],
        optimizer_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Optimize portfolio weights with specified optimizer and constraints."""
        self._ensure_state(PortfolioEngineState.READY)
        self._state = PortfolioEngineState.RUNNING
        try:
            assert self._manager is not None
            result = await self._manager.optimize_portfolio(
                portfolio=portfolio,
                optimizer_type=optimizer_type or (
                    self._ctx.optimizer_type if self._ctx else "mean_variance"
                ),
                constraints=constraints,
                **kwargs,
            )
            return result
        finally:
            self._state = PortfolioEngineState.READY

    # ── analysis ───────────────────────────────────────────────────────────

    async def analyze(
        self,
        portfolio: Dict[str, Any],
        include_risk: bool = True,
        include_attribution: bool = True,
        include_stress: bool = True,
        include_scenario: bool = True,
    ) -> Dict[str, Any]:
        """Perform comprehensive portfolio analysis."""
        self._ensure_state(PortfolioEngineState.READY)
        self._state = PortfolioEngineState.RUNNING
        try:
            assert self._manager is not None
            result = await self._manager.analyze_portfolio(
                portfolio=portfolio,
                include_risk=include_risk,
                include_attribution=include_attribution,
                include_stress=include_stress,
                include_scenario=include_scenario,
            )
            return result
        finally:
            self._state = PortfolioEngineState.READY

    # ── helpers ────────────────────────────────────────────────────────────

    def _ensure_state(self, *allowed: PortfolioEngineState) -> None:
        if self._state not in allowed:
            raise RuntimeError(
                f"PortfolioEngine is {self._state.value}, expected one of "
                f"{[s.value for s in allowed]}"
            )

    @property
    def state(self) -> PortfolioEngineState:
        return self._state

    @property
    def registry(self) -> PortfolioRegistry:
        return self._registry

    @property
    def repository(self) -> PortfolioRepository:
        return self._repository

    def status(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "initialized_at": self._initialized_at.isoformat()
            if self._initialized_at
            else None,
            "session_id": self._ctx.session_id if self._ctx else None,
            "registry": self._registry.summary(),
        }
