"""Research Factory — object construction for research platform entities.

Provides factory methods for creating experiments, datasets, runs,
and related entities with sensible defaults.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ResearchFactory:
    """Factory for constructing research platform entities.

    Each factory method produces a dictionary suitable for persistence
    via the ResearchRepository, ensuring consistent defaults and
    required fields.
    """

    @staticmethod
    def create_experiment(
        name: str,
        dataset: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        experiment_type: str = "default",
    ) -> Dict[str, Any]:
        """Build an experiment entity."""
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "name": name,
            "experiment_type": experiment_type,
            "dataset": dataset,
            "config": config or {},
            "tags": tags or [],
            "metadata": metadata or {},
            "status": "created",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def create_dataset(
        name: str,
        source: str,
        schema: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dataset_type: str = "default",
    ) -> Dict[str, Any]:
        """Build a dataset entity."""
        now = datetime.now(timezone.utc)
        return {
            "id": str(uuid4()),
            "name": name,
            "dataset_type": dataset_type,
            "source": source,
            "schema": schema or {},
            "tags": tags or [],
            "metadata": metadata or {},
            "version": 1,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def create_run(
        experiment_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a run entity."""
        return {
            "id": str(uuid4()),
            "experiment_id": experiment_id,
            "status": "pending",
            "config": config or {},
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def create_artifact(
        experiment_id: str,
        name: str,
        artifact_type: str,
        path: str = "",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build an artifact entity."""
        return {
            "id": str(uuid4()),
            "experiment_id": experiment_id,
            "run_id": run_id,
            "type": artifact_type,
            "name": name,
            "path": path,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def create_dataset_snapshot(
        dataset_id: str,
        version: int,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a dataset snapshot entity."""
        return {
            "id": str(uuid4()),
            "dataset_id": dataset_id,
            "version": version,
            "description": description or "",
            "snapshot_type": "full",
            "created_at": datetime.now(timezone.utc),
            "row_count": 0,
            "checksum": "",
        }

    @staticmethod
    def create_experiment_version(
        experiment_id: str,
        version: int,
        config: Dict[str, Any],
        parent_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build an experiment version entity."""
        return {
            "id": str(uuid4()),
            "experiment_id": experiment_id,
            "version": version,
            "parent_version": parent_version,
            "config": config,
            "created_at": datetime.now(timezone.utc),
            "status": "active",
        }
