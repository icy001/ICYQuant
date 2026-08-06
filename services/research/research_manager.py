"""Research Manager — lifecycle coordinator for all research subsystems.

The :class:`ResearchManager` coordinates the initialization, operation,
and shutdown of the three primary research domains:

* Experiment Management
* Dataset Management
* Runtime Management
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .research_context import ResearchContext

logger = logging.getLogger(__name__)


class ResearchManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class ResearchManager:
    """Lifecycle coordinator for research platform subsystems.

    Responsibilities:

    * Bootstrap experiment, dataset, and runtime managers
    * Propagate lifecycle events to all subsystems
    * Provide unified delegation interface for the engine
    * Maintain global research context

    Architecture::

        ResearchManager
              │
        ┌─────┼─────┐
        Experiment  Dataset  Runtime
    """

    def __init__(self) -> None:
        self._manager_id = str(uuid4())
        self._state = ResearchManagerState.UNINITIALIZED
        self._context: Optional[ResearchContext] = None
        self._experiment_manager = None
        self._dataset_manager = None
        self._runtime_manager = None
        self._initialized_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ResearchManagerState:
        return self._state

    @property
    def context(self) -> Optional[ResearchContext]:
        return self._context

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all research subsystems."""
        async with self._lock:
            if self._state == ResearchManagerState.READY:
                return

            self._state = ResearchManagerState.INITIALIZING
            logger.info("ResearchManager %s initializing", self._manager_id)

            self._context = ResearchContext(manager_id=self._manager_id)

            # Lazy-init subsystem managers
            from .experiment.experiment_manager import ExperimentManager
            from .dataset.dataset_manager import DatasetManager
            from .runtime.runtime_manager import ResearchRuntimeManager

            self._experiment_manager = ExperimentManager(context=self._context)
            self._dataset_manager = DatasetManager(context=self._context)
            self._runtime_manager = ResearchRuntimeManager(context=self._context)

            await self._experiment_manager.initialize()
            await self._dataset_manager.initialize()
            await self._runtime_manager.initialize()

            self._initialized_at = datetime.now(timezone.utc)
            self._state = ResearchManagerState.READY
            logger.info("ResearchManager %s initialized", self._manager_id)

    async def shutdown(self) -> None:
        """Shut down all subsystems gracefully."""
        async with self._lock:
            self._state = ResearchManagerState.SHUTTING_DOWN
            logger.info("ResearchManager %s shutting down", self._manager_id)

            if self._runtime_manager:
                await self._runtime_manager.shutdown()
            if self._dataset_manager:
                await self._dataset_manager.shutdown()
            if self._experiment_manager:
                await self._experiment_manager.shutdown()

            self._state = ResearchManagerState.TERMINATED
            logger.info("ResearchManager %s terminated", self._manager_id)

    # ── experiment delegation ─────────────────────────────────────────────

    async def create_experiment(self, **kwargs) -> Any:
        self._ensure_ready()
        return await self._experiment_manager.create(**kwargs)

    async def get_experiment(self, experiment_id: str) -> Optional[Any]:
        self._ensure_ready()
        return await self._experiment_manager.get(experiment_id)

    async def list_experiments(self, **kwargs) -> List[Any]:
        self._ensure_ready()
        return await self._experiment_manager.list(**kwargs)

    async def execute_experiment(self, experiment_id: str) -> Any:
        self._ensure_ready()
        return await self._experiment_manager.execute(experiment_id)

    async def publish_result(self, result_id: str) -> Any:
        self._ensure_ready()
        return await self._experiment_manager.publish(result_id)

    # ── dataset delegation ────────────────────────────────────────────────

    async def register_dataset(self, **kwargs) -> Any:
        self._ensure_ready()
        return await self._dataset_manager.register(**kwargs)

    async def get_dataset(self, dataset_id: str) -> Optional[Any]:
        self._ensure_ready()
        return await self._dataset_manager.get(dataset_id)

    async def list_datasets(self, **kwargs) -> List[Any]:
        self._ensure_ready()
        return await self._dataset_manager.list(**kwargs)

    async def create_dataset_snapshot(self, dataset_id: str, description: Optional[str] = None) -> Any:
        self._ensure_ready()
        return await self._dataset_manager.create_snapshot(
            dataset_id=dataset_id, description=description,
        )

    # ── runtime delegation ────────────────────────────────────────────────

    async def get_runtime_status(self) -> Dict[str, Any]:
        self._ensure_ready()
        return await self._runtime_manager.get_status()

    async def cancel_execution(self, execution_id: str) -> bool:
        self._ensure_ready()
        return await self._runtime_manager.cancel(execution_id)

    # ── internal ──────────────────────────────────────────────────────────

    def _ensure_ready(self) -> None:
        if self._state != ResearchManagerState.READY:
            raise RuntimeError(
                f"ResearchManager not ready (state={self._state.value})"
            )

    def __repr__(self) -> str:
        return f"ResearchManager(id={self._manager_id[:8]}, state={self._state.value})"
