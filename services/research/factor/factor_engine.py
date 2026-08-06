"""Factor Engine — unified entry point for institutional alpha factor research.

Architecture::

    Dataset → Feature → Factor Pipeline → Evaluation → Alpha Pool → Report

The :class:`FactorEngine` coordinates all factor research capabilities:
calculation, evaluation, and publication of alpha factors through a
unified interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .factor_context import FactorContext
from .factor_manager import FactorManager, FactorManagerState
from .factor_registry import FactorRegistry

logger = logging.getLogger(__name__)


class FactorEngineState(str, Enum):
    """Factor engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class FactorEngine:
    """Unified institutional factor research engine.

    Orchestrates the complete factor lifecycle:
    1. Calculate — derive factor values from datasets
    2. Evaluate — measure predictive power (IC, RankIC, ICIR, decay, turnover)
    3. Publish — register validated factors in the Alpha Pool

    Usage::

        engine = FactorEngine()
        await engine.initialize()

        result = await engine.calculate(
            factor_name="momentum_21d",
            dataset="market_data_v3",
            universe=["000300"],
        )
        eval_result = await engine.evaluate(result["factor_id"])
        await engine.publish(result["factor_id"])
    """

    def __init__(
        self,
        manager: Optional[FactorManager] = None,
        registry: Optional[FactorRegistry] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._engine_id = str(uuid4())
        self._state = FactorEngineState.UNINITIALIZED
        self._manager = manager
        self._registry = registry or FactorRegistry()
        self._config = config or {}
        self._initialized_at: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._stats: Dict[str, int] = {
            "factors_calculated": 0,
            "factors_evaluated": 0,
            "factors_published": 0,
            "errors": 0,
        }

    @property
    def state(self) -> FactorEngineState:
        return self._state

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        async with self._lock:
            if self._state == FactorEngineState.READY:
                return
            self._state = FactorEngineState.INITIALIZING
            logger.info("FactorEngine %s initializing", self._engine_id)

            if self._manager is None:
                self._manager = FactorManager(
                    context=FactorContext(), registry=self._registry
                )
                await self._manager.initialize()

            self._state = FactorEngineState.READY
            self._initialized_at = datetime.now(timezone.utc)
            logger.info("FactorEngine %s ready", self._engine_id)

    async def shutdown(self) -> None:
        async with self._lock:
            self._state = FactorEngineState.SHUTTING_DOWN
            if self._manager:
                await self._manager.shutdown()
            self._state = FactorEngineState.TERMINATED
            logger.info("FactorEngine %s terminated", self._engine_id)

    # ── core operations ───────────────────────────────────────────────────

    async def calculate(
        self,
        factor_name: str,
        dataset: str,
        universe: Optional[List[str]] = None,
        factor_type: str = "custom",
        params: Optional[Dict[str, Any]] = None,
        expression: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate factor values from a dataset.

        Pipeline: Dataset → Feature Engineering → Factor Pipeline → Factor
        """
        if self._state not in (FactorEngineState.READY, FactorEngineState.RUNNING):
            raise RuntimeError(f"Engine not ready: {self._state.value}")

        self._state = FactorEngineState.RUNNING
        job_id = str(uuid4())

        try:
            logger.info("Calculating factor '%s' from dataset '%s'", factor_name, dataset)

            # 1. Create factor record
            factor = await self._manager.create_factor(
                name=factor_name,
                factor_type=factor_type,
                expression=expression,
                universe=universe,
                params=params,
            )

            # 2. Run factor pipeline (feature → transform → factor)
            pipeline_result = await self._manager.run_pipeline(
                factor_id=factor["id"],
                dataset=dataset,
                params=params or {},
            )

            # 3. Merge pipeline results
            factor["pipeline_result"] = pipeline_result
            factor["status"] = "calculated"

            self._stats["factors_calculated"] += 1
            logger.info("Factor %s calculated successfully", factor["id"])
            return factor

        except Exception as exc:
            self._stats["errors"] += 1
            logger.error("Factor calculation failed: %s", exc)
            raise
        finally:
            if self._state == FactorEngineState.RUNNING:
                self._state = FactorEngineState.READY

    async def evaluate(
        self,
        factor_id: str,
        dataset: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        evaluators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Evaluate factor predictive power with comprehensive metrics.

        Runs: IC, RankIC, ICIR, Decay, Turnover, Exposure, Correlation analysis.
        """
        if self._state not in (FactorEngineState.READY, FactorEngineState.RUNNING):
            raise RuntimeError(f"Engine not ready: {self._state.value}")

        self._state = FactorEngineState.RUNNING
        try:
            logger.info("Evaluating factor %s", factor_id)

            eval_result = await self._manager.evaluate_factor(
                factor_id=factor_id,
                dataset=dataset,
                start_date=start_date,
                end_date=end_date,
                evaluators=evaluators,
            )

            self._stats["factors_evaluated"] += 1
            return eval_result

        except Exception as exc:
            self._stats["errors"] += 1
            logger.error("Factor evaluation failed: %s", exc)
            raise
        finally:
            if self._state == FactorEngineState.RUNNING:
                self._state = FactorEngineState.READY

    async def publish(
        self,
        factor_id: str,
        min_ic_threshold: float = 0.02,
        min_icir_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """Publish a validated factor to the Alpha Pool.

        Factors must meet minimum IC/ICIR thresholds to be promoted from
        candidate → validated → production.
        """
        if self._state not in (FactorEngineState.READY, FactorEngineState.RUNNING):
            raise RuntimeError(f"Engine not ready: {self._state.value}")

        logger.info("Publishing factor %s to Alpha Pool", factor_id)

        result = await self._manager.publish_to_alpha_pool(
            factor_id=factor_id,
            min_ic_threshold=min_ic_threshold,
            min_icir_threshold=min_icir_threshold,
        )

        self._stats["factors_published"] += 1
        return result

    async def get_factor(self, factor_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a factor by ID."""
        if self._manager is None:
            return None
        return await self._manager.get_factor(factor_id)

    async def list_factors(
        self,
        factor_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List factors with optional filters."""
        if self._manager is None:
            return []
        return await self._manager.list_factors(
            factor_type=factor_type, status=status, tags=tags, limit=limit
        )

    async def list_alpha_pool(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List alpha pool entries."""
        if self._manager is None:
            return []
        return await self._manager.list_alpha_pool(status=status)

    async def generate_report(self, factor_id: str) -> Dict[str, Any]:
        """Generate comprehensive factor research report."""
        if self._manager is None:
            raise RuntimeError("Engine not initialized")
        return await self._manager.generate_report(factor_id)

    # ── registry helpers ──────────────────────────────────────────────────

    def register_factor_type(self, name: str, cls: type, factory: Any = None) -> None:
        self._registry.register_factor_type(name, cls, factory)

    def register_normalizer(self, name: str, fn: Any) -> None:
        self._registry.register_normalizer(name, fn)

    def register_neutralizer(self, name: str, fn: Any) -> None:
        self._registry.register_neutralizer(name, fn)

    def register_evaluator(self, name: str, fn: Any) -> None:
        self._registry.register_evaluator(name, fn)
