"""
Strategy repository for persistent storage and retrieval.

Provides CRUD operations for strategy definitions, metadata, and version
history backed by the platform's data infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .strategy_manifest import StrategyManifest
from .strategy_metadata import StrategyMetadata
from .strategy_version import StrategyVersion, VersionHistory

logger = logging.getLogger(__name__)


@dataclass
class RepositoryResult:
    """Result of a repository operation."""

    success: bool
    data: Any = None
    error: str = ""
    affected_rows: int = 0


class StrategyRepository:
    """Repository for strategy persistence.

    Uses an in-memory store by default. In production, this would be
    backed by a database (PostgreSQL) through the infrastructure layer.
    """

    def __init__(self) -> None:
        # In-memory stores
        self._manifests: Dict[str, StrategyManifest] = {}
        self._metadata_store: Dict[str, StrategyMetadata] = {}
        self._version_histories: Dict[str, VersionHistory] = {}
        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyRepository initialized")

    async def shutdown(self) -> None:
        self._manifests.clear()
        self._metadata_store.clear()
        self._version_histories.clear()
        self._initialized = False
        logger.info("StrategyRepository shut down")

    # ── CRUD: Manifest ──

    async def save_manifest(self, manifest: StrategyManifest) -> RepositoryResult:
        try:
            key = f"{manifest.name}_{manifest.version}"
            self._manifests[key] = manifest
            return RepositoryResult(success=True, data=manifest, affected_rows=1)
        except Exception as e:
            return RepositoryResult(success=False, error=str(e))

    async def get_manifest(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[StrategyManifest]:
        if version:
            key = f"{name}_{version}"
            return self._manifests.get(key)

        # Return latest version
        candidates = [
            m for k, m in self._manifests.items() if k.startswith(f"{name}_")
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda m: StrategyVersion.parse(m.version),
        )

    async def list_manifests(
        self,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StrategyManifest]:
        manifests = list(self._manifests.values())
        if name:
            manifests = [m for m in manifests if m.name == name]
        return manifests[offset : offset + limit]

    async def delete_manifest(self, name: str, version: str) -> RepositoryResult:
        key = f"{name}_{version}"
        if key in self._manifests:
            del self._manifests[key]
            return RepositoryResult(success=True, affected_rows=1)
        return RepositoryResult(success=False, error=f"Manifest not found: {key}")

    # ── CRUD: Metadata ──

    async def save_metadata(self, metadata: StrategyMetadata) -> RepositoryResult:
        try:
            self._metadata_store[metadata.strategy_id] = metadata
            return RepositoryResult(success=True, data=metadata, affected_rows=1)
        except Exception as e:
            return RepositoryResult(success=False, error=str(e))

    async def get_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        return self._metadata_store.get(strategy_id)

    async def update_metadata(
        self,
        strategy_id: str,
        updates: Dict[str, Any],
    ) -> RepositoryResult:
        metadata = self._metadata_store.get(strategy_id)
        if metadata is None:
            return RepositoryResult(
                success=False,
                error=f"Metadata not found: {strategy_id}",
            )

        for field, value in updates.items():
            if hasattr(metadata, field):
                setattr(metadata, field, value)

        metadata.updated_at = datetime.now(timezone.utc)
        return RepositoryResult(success=True, data=metadata, affected_rows=1)

    async def delete_metadata(self, strategy_id: str) -> RepositoryResult:
        if strategy_id in self._metadata_store:
            del self._metadata_store[strategy_id]
            return RepositoryResult(success=True, affected_rows=1)
        return RepositoryResult(success=False, error=f"Metadata not found: {strategy_id}")

    # ── CRUD: Version History ──

    async def save_version_history(self, history: VersionHistory) -> RepositoryResult:
        try:
            self._version_histories[history.strategy_id] = history
            return RepositoryResult(success=True, data=history, affected_rows=1)
        except Exception as e:
            return RepositoryResult(success=False, error=str(e))

    async def get_version_history(
        self,
        strategy_id: str,
    ) -> Optional[VersionHistory]:
        return self._version_histories.get(strategy_id)

    # ── Counts ──

    @property
    def manifest_count(self) -> int:
        return len(self._manifests)

    @property
    def metadata_count(self) -> int:
        return len(self._metadata_store)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "manifests": self.manifest_count,
            "metadata": self.metadata_count,
            "version_histories": len(self._version_histories),
            "initialized": self._initialized,
        }
