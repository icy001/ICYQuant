"""Experiment API — RESTful API for experiment management.

Commit 11 Part 1.5: Provides HTTP endpoints for creating, listing,
updating, and running research experiments.

Endpoints:
    GET    /research/experiments          — List experiments
    POST   /research/experiments          — Create experiment
    GET    /research/experiments/{id}     — Get experiment details
    PUT    /research/experiments/{id}     — Update experiment
    DELETE /research/experiments/{id}     — Delete experiment
    POST   /research/experiments/{id}/run — Run experiment
    GET    /research/experiments/{id}/results — Get results
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    """Experiment status values."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentAPI:
    """RESTful API for experiment management.

    Provides CRUD operations and execution control for research experiments.

    Usage::

        api = ExperimentAPI(config={"base_url": "/research"})
        await api.initialize()
        exp_id = await api.create_experiment(
            name="Alpha 101 Replication",
            dataset_id="us_equity_daily",
        )
        result = await api.run_experiment(exp_id)
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        api_id: Optional[str] = None,
    ) -> None:
        self._id: str = api_id or f"expapi-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._created_at: datetime = datetime.now(timezone.utc)

        # Experiment store
        self._experiments: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the experiment API."""
        logger.info("Initializing ExperimentAPI [%s]", self._id)

    async def shutdown(self) -> None:
        """Clean up."""
        self._experiments.clear()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_experiment(
        self,
        name: str,
        dataset_id: str,
        *,
        description: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment.

        Args:
            name: Experiment name.
            dataset_id: Target dataset ID.
            description: Optional description.
            params: Experiment parameters.
            tags: Searchable tags.

        Returns:
            Created experiment details.
        """
        exp_id = f"exp-{uuid4().hex[:12]}"
        experiment = {
            "id": exp_id,
            "name": name,
            "description": description or "",
            "dataset_id": dataset_id,
            "params": params or {},
            "tags": tags or [],
            "status": ExperimentStatus.DRAFT.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._experiments[exp_id] = experiment
        logger.info("Experiment created: %s [%s]", exp_id, name)
        return dict(experiment)

    async def get_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment details."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return dict(experiment)

    async def update_experiment(
        self,
        experiment_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update experiment metadata."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")

        if name is not None:
            experiment["name"] = name
        if description is not None:
            experiment["description"] = description
        if params is not None:
            experiment["params"] = params
        if tags is not None:
            experiment["tags"] = tags
        experiment["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(experiment)

    async def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment."""
        if experiment_id not in self._experiments:
            raise KeyError(f"Experiment not found: {experiment_id}")
        del self._experiments[experiment_id]
        logger.info("Experiment deleted: %s", experiment_id)

    async def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List experiments with optional filtering."""
        experiments = list(self._experiments.values())
        if status is not None:
            experiments = [e for e in experiments if e["status"] == status.value]
        if tags:
            experiments = [e for e in experiments if any(t in e["tags"] for t in tags)]
        return [
            {"id": e["id"], "name": e["name"], "status": e["status"], "dataset_id": e["dataset_id"]}
            for e in experiments
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Execute an experiment.

        Args:
            experiment_id: Experiment to run.

        Returns:
            Execution result.
        """
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")

        experiment["status"] = ExperimentStatus.RUNNING.value
        experiment["started_at"] = datetime.now(timezone.utc).isoformat()

        # Simulate execution
        import asyncio
        await asyncio.sleep(0.01)

        experiment["status"] = ExperimentStatus.COMPLETED.value
        experiment["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Experiment completed: %s", experiment_id)

        return {"experiment_id": experiment_id, "status": "completed"}

    async def cancel_experiment(self, experiment_id: str) -> None:
        """Cancel a running experiment."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")
        if experiment["status"] != ExperimentStatus.RUNNING.value:
            raise RuntimeError(f"Experiment not running: status={experiment['status']}")
        experiment["status"] = ExperimentStatus.CANCELLED.value
        logger.info("Experiment cancelled: %s", experiment_id)

    async def get_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment results."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return {
            "experiment_id": experiment_id,
            "status": experiment["status"],
            "started_at": experiment.get("started_at"),
            "completed_at": experiment.get("completed_at"),
        }
