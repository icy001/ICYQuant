"""
Model Version — Semantic versioning for autonomous models.

Tracks model versions with lineage (parent→child) and supports
version comparison and rollback.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelVersionInfo:
    """Version metadata for a model."""
    model_id: str
    version: str
    parent_version: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    change_summary: str = ""
    author: str = "autonomous"
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "change_summary": self.change_summary,
            "author": self.author,
            "metrics": self.metrics,
        }


class ModelVersion:
    """
    Manages model versions with semantic versioning.

    Supports:
    - Version creation with parent lineage
    - Version comparison (newer/older)
    - Version history retrieval
    - Rollback to previous versions
    """

    def __init__(self):
        self._versions: dict[str, list[ModelVersionInfo]] = {}
        self._active: dict[str, str] = {}  # model_id → active version

    def create_version(
        self,
        model_id: str,
        version: str,
        parent_version: Optional[str] = None,
        change_summary: str = "",
        author: str = "autonomous",
        metrics: Optional[dict] = None,
    ) -> ModelVersionInfo:
        """Create a new version for a model."""
        info = ModelVersionInfo(
            model_id=model_id,
            version=version,
            parent_version=parent_version,
            change_summary=change_summary,
            author=author,
            metrics=metrics or {},
        )
        self._versions.setdefault(model_id, []).append(info)
        self._active[model_id] = version
        logger.info("Model %s version %s created", model_id, version)
        return info

    def get_active(self, model_id: str) -> Optional[str]:
        """Get the active version for a model."""
        return self._active.get(model_id)

    def set_active(self, model_id: str, version: str) -> bool:
        """Set the active version (rollback)."""
        versions = self._versions.get(model_id, [])
        if any(v.version == version for v in versions):
            self._active[model_id] = version
            logger.info("Model %s → v%s activated", model_id, version)
            return True
        return False

    def history(self, model_id: str) -> list[ModelVersionInfo]:
        """Get full version history for a model."""
        return list(self._versions.get(model_id, []))

    def latest(self, model_id: str) -> Optional[ModelVersionInfo]:
        """Get the latest version for a model."""
        versions = self._versions.get(model_id, [])
        return versions[-1] if versions else None

    def stats(self) -> dict:
        return {
            "models_with_versions": len(self._versions),
            "total_versions": sum(len(v) for v in self._versions.values()),
        }
