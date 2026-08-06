"""Research Repository — persistence layer for research entities.

Provides CRUD operations for experiments, datasets, runs, and artifacts
with pluggable storage backends.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ResearchRepository:
    """Pluggable persistence layer for research entities.

    Supports:
    * Experiment storage (create, read, update, delete, list)
    * Dataset metadata storage
    * Run/execution records
    * Artifact metadata

    Backend: currently in-memory; designed for swap to SQL/NoSQL.
    """

    def __init__(self, backend: str = "memory") -> None:
        self._backend = backend
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._artifacts: Dict[str, Dict[str, Any]] = {}

    # ── experiment CRUD ───────────────────────────────────────────────────

    async def create_experiment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        experiment_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": experiment_id,
            "name": data.get("name", ""),
            "dataset": data.get("dataset"),
            "config": data.get("config", {}),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "status": data.get("status", "created"),
            "version": 1,
            "created_at": data.get("created_at", now),
            "updated_at": now,
        }
        self._experiments[experiment_id] = record
        logger.debug("Created experiment: %s", experiment_id)
        return record

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        return self._experiments.get(experiment_id)

    async def update_experiment(
        self, experiment_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._experiments.get(experiment_id)
        if record is None:
            return None
        record.update(updates)
        record["updated_at"] = datetime.now(timezone.utc)
        return record

    async def delete_experiment(self, experiment_id: str) -> bool:
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            return True
        return False

    async def list_experiments(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self._experiments.values())
        if status:
            results = [r for r in results if r.get("status") == status]
        if tags:
            results = [
                r for r in results
                if any(t in (r.get("tags") or []) for t in tags)
            ]
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[offset : offset + limit]

    # ── dataset CRUD ──────────────────────────────────────────────────────

    async def create_dataset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        dataset_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": dataset_id,
            "name": data.get("name", ""),
            "source": data.get("source", ""),
            "schema": data.get("schema", {}),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "version": 1,
            "status": data.get("status", "active"),
            "created_at": data.get("created_at", now),
            "updated_at": now,
        }
        self._datasets[dataset_id] = record
        logger.debug("Created dataset: %s", dataset_id)
        return record

    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self._datasets.get(dataset_id)

    async def list_datasets(
        self,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self._datasets.values())
        if source:
            results = [r for r in results if r.get("source") == source]
        if tags:
            results = [
                r for r in results
                if any(t in (r.get("tags") or []) for t in tags)
            ]
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[offset : offset + limit]

    # ── run CRUD ──────────────────────────────────────────────────────────

    async def create_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": run_id,
            "experiment_id": data.get("experiment_id", ""),
            "status": data.get("status", "pending"),
            "config": data.get("config", {}),
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
            "result": data.get("result"),
            "error": data.get("error"),
            "created_at": now,
        }
        self._runs[run_id] = record
        return record

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    async def list_runs(
        self,
        experiment_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = list(self._runs.values())
        if experiment_id:
            results = [r for r in results if r.get("experiment_id") == experiment_id]
        if status:
            results = [r for r in results if r.get("status") == status]
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    # ── artifact CRUD ─────────────────────────────────────────────────────

    async def create_artifact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        artifact_id = data.get("id") or str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "id": artifact_id,
            "experiment_id": data.get("experiment_id", ""),
            "run_id": data.get("run_id"),
            "type": data.get("type", "generic"),
            "name": data.get("name", ""),
            "path": data.get("path", ""),
            "metadata": data.get("metadata", {}),
            "created_at": now,
        }
        self._artifacts[artifact_id] = record
        return record

    async def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self._artifacts.get(artifact_id)

    async def list_artifacts(
        self,
        experiment_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = list(self._artifacts.values())
        if experiment_id:
            results = [r for r in results if r.get("experiment_id") == experiment_id]
        if artifact_type:
            results = [r for r in results if r.get("type") == artifact_type]
        return results[:limit]

    def __repr__(self) -> str:
        return (
            f"ResearchRepository(backend={self._backend}, "
            f"experiments={len(self._experiments)}, "
            f"datasets={len(self._datasets)}, "
            f"runs={len(self._runs)}, artifacts={len(self._artifacts)})"
        )
