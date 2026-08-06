"""Unified Research Engine — top-level entry point for the research platform.

The :class:`ResearchEngine` is the single entry point that coordinates:

* Experiment lifecycle (create → configure → run → publish)
* Dataset management (register → version → snapshot → cache)
* Research execution (runtime → scheduler → workflow → artifact)

Architecture::

    ResearchEngine
          │
    ResearchManager
          │
    ┌──────┼──────────┐
    Experiment  Dataset  Runtime
    └──────┼──────────┘
    ResearchRuntime → Workflow Engine → Distributed Scheduler
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .research_manager import ResearchManager, ResearchManagerState

logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    """Research engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class ResearchEngine:
    """Unified research engine coordinating all research platform capabilities.

    The engine orchestrates experiment management, dataset operations,
    and runtime execution through a single entry point. It delegates to
    specialized managers for each domain concern.

    Usage::

        engine = ResearchEngine()
        await engine.initialize()

        experiment = await engine.create_experiment(
            name="alpha_v2",
            dataset="market_data_v3",
            config={"factor": "momentum"}
        )
        result = await engine.execute(experiment.id)
        await engine.publish(result.id)

        await engine.shutdown()
    """

    def __init__(
        self,
        manager: Optional[ResearchManager] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._engine_id = str(uuid4())
        self._state = EngineState.UNINITIALIZED
        self._manager = manager
        self._config = config or {}
        self._initialized_at: Optional[datetime] = None
        self._experiment_count: int = 0
        self._dataset_count: int = 0
        self._lock = asyncio.Lock()

    # ── properties ────────────────────────────────────────────────────────

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def manager(self) -> Optional[ResearchManager]:
        return self._manager

    @property
    def experiment_count(self) -> int:
        return self._experiment_count

    @property
    def dataset_count(self) -> int:
        return self._dataset_count

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the research engine and all subsystems."""
        async with self._lock:
            if self._state in (EngineState.READY, EngineState.RUNNING):
                return

            self._state = EngineState.INITIALIZING
            logger.info("ResearchEngine %s initializing", self._engine_id)

            if self._manager is None:
                self._manager = ResearchManager()
            await self._manager.initialize()

            self._initialized_at = datetime.now(timezone.utc)
            self._state = EngineState.READY
            logger.info("ResearchEngine %s initialized", self._engine_id)

    async def shutdown(self) -> None:
        """Gracefully shut down the research engine."""
        async with self._lock:
            self._state = EngineState.SHUTTING_DOWN
            logger.info("ResearchEngine %s shutting down", self._engine_id)

            if self._manager is not None:
                await self._manager.shutdown()

            self._state = EngineState.TERMINATED
            logger.info("ResearchEngine %s terminated", self._engine_id)

    # ── experiment operations ─────────────────────────────────────────────

    async def create_experiment(
        self,
        name: str,
        dataset: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create a new research experiment.

        Args:
            name: Human-readable experiment name.
            dataset: Reference dataset identifier.
            config: Experiment configuration parameters.
            tags: Optional tags for categorization.
            metadata: Optional metadata key-value pairs.

        Returns:
            The created Experiment object.
        """
        await self._ensure_ready()
        result = await self._manager.create_experiment(
            name=name, dataset=dataset, config=config,
            tags=tags, metadata=metadata,
        )
        self._experiment_count += 1
        logger.info("Experiment '%s' created (total: %d)", name, self._experiment_count)
        return result

    async def get_experiment(self, experiment_id: str) -> Optional[Any]:
        """Retrieve an experiment by its identifier."""
        await self._ensure_ready()
        return await self._manager.get_experiment(experiment_id)

    async def list_experiments(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]:
        """List experiments with optional filtering."""
        await self._ensure_ready()
        return await self._manager.list_experiments(
            status=status, tags=tags, limit=limit, offset=offset,
        )

    async def execute(self, experiment_id: str) -> Any:
        """Execute a research experiment.

        This triggers the full research pipeline: dataset loading,
        experiment execution, result collection, and artifact generation.
        """
        await self._ensure_ready()
        logger.info("Executing experiment %s", experiment_id)
        result = await self._manager.execute_experiment(experiment_id)
        return result

    async def publish(self, result_id: str) -> Any:
        """Publish a research result as a shareable artifact."""
        await self._ensure_ready()
        logger.info("Publishing result %s", result_id)
        return await self._manager.publish_result(result_id)

    # ── dataset operations ────────────────────────────────────────────────

    async def register_dataset(
        self,
        name: str,
        source: str,
        schema: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Register a new dataset in the catalog."""
        await self._ensure_ready()
        result = await self._manager.register_dataset(
            name=name, source=source, schema=schema,
            tags=tags, metadata=metadata,
        )
        self._dataset_count += 1
        logger.info("Dataset '%s' registered (total: %d)", name, self._dataset_count)
        return result

    async def get_dataset(self, dataset_id: str) -> Optional[Any]:
        """Retrieve dataset metadata by identifier."""
        await self._ensure_ready()
        return await self._manager.get_dataset(dataset_id)

    async def list_datasets(
        self,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]:
        """List registered datasets with optional filtering."""
        await self._ensure_ready()
        return await self._manager.list_datasets(
            source=source, tags=tags, limit=limit, offset=offset,
        )

    async def create_dataset_snapshot(
        self,
        dataset_id: str,
        description: Optional[str] = None,
    ) -> Any:
        """Create an immutable snapshot of a dataset version."""
        await self._ensure_ready()
        return await self._manager.create_dataset_snapshot(
            dataset_id=dataset_id, description=description,
        )

    # ── runtime operations ────────────────────────────────────────────────

    async def get_runtime_status(self) -> Dict[str, Any]:
        """Return current runtime status summary."""
        await self._ensure_ready()
        return await self._manager.get_runtime_status()

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        await self._ensure_ready()
        return await self._manager.cancel_execution(execution_id)

    # ── internal ──────────────────────────────────────────────────────────

    async def _ensure_ready(self) -> None:
        if self._state not in (EngineState.READY, EngineState.RUNNING):
            raise RuntimeError(
                f"ResearchEngine not ready (state={self._state.value})"
            )

    def __repr__(self) -> str:
        return (
            f"ResearchEngine(id={self._engine_id[:8]}, "
            f"state={self._state.value})"
        )
