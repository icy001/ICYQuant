"""Experiment Manager — lifecycle management for research experiments.

Coordinates experiment creation, execution, versioning, lineage tracking,
and artifact management through a unified interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.research.research_context import ResearchContext
from services.research.research_factory import ResearchFactory
from services.research.research_repository import ResearchRepository
from services.research.research_validator import ResearchValidator

from .experiment import Experiment, ExperimentStatus

logger = logging.getLogger(__name__)


class ExperimentManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class ExperimentManager:
    """Unified experiment lifecycle manager.

    Responsibilities:
    * Create/retrieve/list experiments
    * Execute experiment runs
    * Manage experiment versions and snapshots
    * Track experiment lineage
    * Publish results as artifacts

    Lifecycle::

        create → configure → queue → run → complete → publish → archive
    """

    def __init__(
        self,
        context: Optional[ResearchContext] = None,
        repository: Optional[ResearchRepository] = None,
    ) -> None:
        self._state = ExperimentManagerState.UNINITIALIZED
        self._context = context or ResearchContext()
        self._repository = repository or ResearchRepository()
        self._factory = ResearchFactory()
        self._active_runs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ExperimentManagerState:
        return self._state

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        if self._state == ExperimentManagerState.READY:
            return
        self._state = ExperimentManagerState.INITIALIZING
        logger.info("ExperimentManager initializing")
        self._state = ExperimentManagerState.READY

    async def shutdown(self) -> None:
        self._state = ExperimentManagerState.SHUTTING_DOWN
        logger.info("ExperimentManager shutting down")
        self._state = ExperimentManagerState.TERMINATED

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def create(self, **kwargs) -> Dict[str, Any]:
        data = self._factory.create_experiment(**kwargs)
        ResearchValidator.validate_experiment_create(data)
        return await self._repository.create_experiment(data)

    async def get(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_experiment(experiment_id)

    async def list(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._repository.list_experiments(**kwargs)

    async def update(self, experiment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self._repository.update_experiment(experiment_id, updates)

    async def delete(self, experiment_id: str) -> bool:
        return await self._repository.delete_experiment(experiment_id)

    # ── execution ─────────────────────────────────────────────────────────

    async def execute(self, experiment_id: str) -> Dict[str, Any]:
        """Queue an experiment for execution."""
        experiment = await self._repository.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        run_data = self._factory.create_run(experiment_id=experiment_id)
        run = await self._repository.create_run(run_data)
        logger.info("Experiment %s queued as run %s", experiment_id, run["id"])

        # Update experiment status
        await self._repository.update_experiment(experiment_id, {"status": "running"})
        return run

    async def publish(self, result_id: str) -> Dict[str, Any]:
        """Publish a result as an artifact."""
        artifact = self._factory.create_artifact(
            experiment_id=result_id,
            name=f"result_{result_id[:8]}",
            artifact_type="result",
        )
        return await self._repository.create_artifact(artifact)

    # ── version management ────────────────────────────────────────────────

    async def create_version(
        self,
        experiment_id: str,
        config: Dict[str, Any],
        parent_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new version of an experiment."""
        experiment = await self._repository.get_experiment(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        new_version = (experiment.get("version", 1) or 1) + 1
        version_data = self._factory.create_experiment_version(
            experiment_id=experiment_id,
            version=new_version,
            config=config,
            parent_version=parent_version,
        )
        await self._repository.update_experiment(
            experiment_id,
            {"version": new_version, "config": config, "updated_at": datetime.now(timezone.utc)},
        )
        return version_data

    def __repr__(self) -> str:
        return f"ExperimentManager(state={self._state.value})"
