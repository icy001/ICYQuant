"""Research Service — business logic layer for research platform operations.

Orchestrates validation, persistence, and lifecycle operations
for experiments, datasets, and related entities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .research_context import ResearchContext
from .research_factory import ResearchFactory
from .research_registry import ResearchRegistry
from .research_repository import ResearchRepository
from .research_validator import ResearchValidator

logger = logging.getLogger(__name__)


class ResearchService:
    """Business logic layer for the research platform.

    Coordinates:
    * Validation → Factory → Repository pipeline
    * Registry-based type resolution
    * Context propagation across operations
    """

    def __init__(
        self,
        repository: Optional[ResearchRepository] = None,
        registry: Optional[ResearchRegistry] = None,
        context: Optional[ResearchContext] = None,
    ) -> None:
        self._repository = repository or ResearchRepository()
        self._registry = registry or ResearchRegistry()
        self._context = context or ResearchContext()
        self._factory = ResearchFactory()

    @property
    def context(self) -> ResearchContext:
        return self._context

    @property
    def repository(self) -> ResearchRepository:
        return self._repository

    @property
    def registry(self) -> ResearchRegistry:
        return self._registry

    # ── experiment service ────────────────────────────────────────────────

    async def create_experiment(
        self,
        name: str,
        dataset: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment with validation and persistence."""
        data = self._factory.create_experiment(
            name=name, dataset=dataset, config=config,
            tags=tags, metadata=metadata,
        )
        ResearchValidator.validate_experiment_create(data)
        result = await self._repository.create_experiment(data)
        logger.info("Experiment '%s' created: %s", name, result["id"])
        return result

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_experiment(experiment_id)

    async def list_experiments(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return await self._repository.list_experiments(
            status=status, tags=tags, limit=limit, offset=offset,
        )

    async def update_experiment(
        self, experiment_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return await self._repository.update_experiment(experiment_id, updates)

    async def delete_experiment(self, experiment_id: str) -> bool:
        return await self._repository.delete_experiment(experiment_id)

    # ── dataset service ───────────────────────────────────────────────────

    async def register_dataset(
        self,
        name: str,
        source: str,
        schema: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a new dataset with validation and persistence."""
        data = self._factory.create_dataset(
            name=name, source=source, schema=schema,
            tags=tags, metadata=metadata,
        )
        ResearchValidator.validate_dataset_create(data)
        result = await self._repository.create_dataset(data)
        logger.info("Dataset '%s' registered: %s", name, result["id"])
        return result

    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_dataset(dataset_id)

    async def list_datasets(
        self,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return await self._repository.list_datasets(
            source=source, tags=tags, limit=limit, offset=offset,
        )

    # ── run service ───────────────────────────────────────────────────────

    async def create_run(
        self,
        experiment_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = self._factory.create_run(
            experiment_id=experiment_id, config=config,
        )
        ResearchValidator.validate_run_create(data)
        return await self._repository.create_run(data)

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_run(run_id)

    async def list_runs(
        self,
        experiment_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._repository.list_runs(
            experiment_id=experiment_id, status=status, limit=limit,
        )

    # ── artifact service ──────────────────────────────────────────────────

    async def create_artifact(
        self,
        experiment_id: str,
        name: str,
        artifact_type: str,
        path: str = "",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = self._factory.create_artifact(
            experiment_id=experiment_id, name=name,
            artifact_type=artifact_type, path=path,
            run_id=run_id, metadata=metadata,
        )
        ResearchValidator.validate_artifact_create(data)
        return await self._repository.create_artifact(data)

    async def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return await self._repository.get_artifact(artifact_id)

    async def list_artifacts(
        self,
        experiment_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._repository.list_artifacts(
            experiment_id=experiment_id, artifact_type=artifact_type, limit=limit,
        )

    def __repr__(self) -> str:
        return f"ResearchService(repo={self._repository})"
