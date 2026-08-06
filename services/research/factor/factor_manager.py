"""Factor Manager — lifecycle coordinator for factor research subsystems.

Coordinates factor creation, pipeline execution, evaluation, and alpha
pool management through a unified interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .factor_context import FactorContext
from .factor_factory import FactorFactory
from .factor_registry import FactorRegistry
from .factor_repository import FactorRepository

logger = logging.getLogger(__name__)


class FactorManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class FactorManager:
    """Lifecycle coordinator for factor research subsystems.

    Responsibilities:
    * Bootstrap factor, feature, and evaluation subsystems
    * Orchestrate factor creation and pipeline execution
    * Coordinate evaluation runs
    * Manage alpha pool lifecycle
    * Generate factor research reports
    """

    def __init__(
        self,
        context: Optional[FactorContext] = None,
        registry: Optional[FactorRegistry] = None,
        repository: Optional[FactorRepository] = None,
    ) -> None:
        self._manager_id = str(id(self))
        self._state = FactorManagerState.UNINITIALIZED
        self._context = context or FactorContext()
        self._registry = registry or FactorRegistry()
        self._repository = repository or FactorRepository()
        self._factory = FactorFactory()
        self._lock = asyncio.Lock()
        self._initialized_at: Optional[datetime] = None

        # Lazy-init subsystems
        self._pipeline = None
        self._feature_engine = None
        self._feature_store = None
        self._alpha_pool = None
        self._report_generator = None

    @property
    def state(self) -> FactorManagerState:
        return self._state

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        async with self._lock:
            if self._state == FactorManagerState.READY:
                return
            self._state = FactorManagerState.INITIALIZING
            logger.info("FactorManager initializing")

            from .factor_pipeline import FactorPipeline
            from .feature_engineering import FeatureEngine
            from .feature_store import FeatureStore
            from .alpha_pool import AlphaPool
            from .factor_report import FactorReport

            self._pipeline = FactorPipeline(context=self._context, registry=self._registry)
            self._feature_engine = FeatureEngine(context=self._context)
            self._feature_store = FeatureStore()
            self._alpha_pool = AlphaPool(repository=self._repository)
            self._report_generator = FactorReport()

            self._state = FactorManagerState.READY
            self._initialized_at = datetime.now(timezone.utc)
            logger.info("FactorManager ready")

    async def shutdown(self) -> None:
        async with self._lock:
            self._state = FactorManagerState.SHUTTING_DOWN
            self._pipeline = None
            self._feature_engine = None
            self._feature_store = None
            self._alpha_pool = None
            self._report_generator = None
            self._state = FactorManagerState.TERMINATED

    # ── factor CRUD ───────────────────────────────────────────────────────

    async def create_factor(
        self,
        name: str,
        factor_type: str = "custom",
        expression: Optional[str] = None,
        universe: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        data = self._factory.create_factor(
            name=name,
            factor_type=factor_type,
            expression=expression,
            universe=universe or self._context.universe,
            params=params,
            tags=tags,
        )
        return await self._repository.create_factor(data)

    async def get_factor(self, factor_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_factor(factor_id)

    async def list_factors(
        self,
        factor_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._repository.list_factors(
            factor_type=factor_type, status=status, tags=tags, limit=limit
        )

    async def update_factor(
        self, factor_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return await self._repository.update_factor(factor_id, updates)

    # ── pipeline execution ────────────────────────────────────────────────

    async def run_pipeline(
        self,
        factor_id: str,
        dataset: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the full factor pipeline: Dataset → Feature → Transform → Factor."""
        if self._pipeline is None:
            raise RuntimeError("FactorManager not initialized")

        logger.info("Running pipeline for factor %s on dataset %s", factor_id, dataset)

        result = await self._pipeline.execute(
            factor_id=factor_id,
            dataset=dataset,
            params=params or {},
        )
        return result

    # ── evaluation ────────────────────────────────────────────────────────

    async def evaluate_factor(
        self,
        factor_id: str,
        dataset: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        evaluators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run comprehensive factor evaluation."""
        factor = await self._repository.get_factor(factor_id)
        if factor is None:
            raise ValueError(f"Factor not found: {factor_id}")

        logger.info("Evaluating factor %s", factor_id)

        eval_result: Dict[str, Any] = {
            "factor_id": factor_id,
            "factor_name": factor.get("name"),
            "evaluations": {},
            "summary": {},
        }

        all_evaluators = evaluators or [
            "ic", "rankic", "icir", "decay", "turnover",
            "exposure", "correlation",
        ]

        for eval_name in all_evaluators:
            try:
                evaluator_fn = self._registry.get_evaluator(eval_name)
                if evaluator_fn:
                    eval_result["evaluations"][eval_name] = await evaluator_fn(
                        factor=factor, dataset=dataset,
                        start_date=start_date, end_date=end_date,
                    )
            except Exception as exc:
                logger.warning("Evaluator '%s' failed: %s", eval_name, exc)
                eval_result["evaluations"][eval_name] = {"error": str(exc)}

        # Store evaluation record
        await self._repository.create_evaluation({
            "factor_id": factor_id,
            "eval_type": "comprehensive",
            "metrics": eval_result,
        })

        # Update factor status
        await self._repository.update_factor(factor_id, {"status": "evaluated"})

        return eval_result

    # ── alpha pool ────────────────────────────────────────────────────────

    async def publish_to_alpha_pool(
        self,
        factor_id: str,
        min_ic_threshold: float = 0.02,
        min_icir_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """Publish factor to Alpha Pool if it meets quality thresholds."""
        if self._alpha_pool is None:
            raise RuntimeError("FactorManager not initialized")

        factor = await self._repository.get_factor(factor_id)
        if factor is None:
            raise ValueError(f"Factor not found: {factor_id}")

        return await self._alpha_pool.submit(
            factor=factor,
            min_ic_threshold=min_ic_threshold,
            min_icir_threshold=min_icir_threshold,
        )

    async def list_alpha_pool(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List alpha pool entries."""
        return await self._repository.list_alpha_entries(status=status)

    # ── report ────────────────────────────────────────────────────────────

    async def generate_report(self, factor_id: str) -> Dict[str, Any]:
        """Generate comprehensive factor research report."""
        if self._report_generator is None:
            raise RuntimeError("FactorManager not initialized")

        factor = await self._repository.get_factor(factor_id)
        if factor is None:
            raise ValueError(f"Factor not found: {factor_id}")

        evaluations = await self._repository.get_evaluations_for_factor(factor_id)

        return await self._report_generator.generate(
            factor=factor, evaluations=evaluations
        )
