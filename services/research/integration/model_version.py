"""Model Version — version management for research models.

Commit 11 Part 1.5: Tracks model versions, provides comparison capabilities,
and manages version lifecycle (staging, production, archived).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelVersionState(str, Enum):
    """Model version lifecycle states."""

    CREATED = "created"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelVersion:
    """Manages individual model versions with staging/production lifecycle.

    Tracks version metadata, evaluation metrics, and stage transitions.

    Usage::

        version = ModelVersion(model_id="model-abc", version_num=1)
        await version.initialize()
        await version.set_metrics({"sharpe": 1.5, "max_drawdown": -0.15})
        await version.promote_to_staging()
        await version.promote_to_production()
    """

    def __init__(
        self,
        model_id: str,
        version_num: int,
        *,
        version_id: Optional[str] = None,
        version_name: Optional[str] = None,
    ) -> None:
        self._id: str = version_id or f"mv-{uuid4().hex[:12]}"
        self._model_id: str = model_id
        self._version_num: int = version_num
        self._version_name: str = version_name or f"v{version_num}"
        self._state: ModelVersionState = ModelVersionState.CREATED

        self._created_at: datetime = datetime.now(timezone.utc)
        self._staged_at: Optional[datetime] = None
        self._production_at: Optional[datetime] = None
        self._archived_at: Optional[datetime] = None

        # Version metadata
        self._metrics: Dict[str, Any] = {}
        self._params: Dict[str, Any] = {}
        self._tags: Dict[str, str] = {}
        self._description: str = ""
        self._changelog: List[str] = []

        # Artifact references
        self._artifacts: List[str] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def version_num(self) -> int:
        return self._version_num

    @property
    def version_name(self) -> str:
        return self._version_name

    @property
    def state(self) -> ModelVersionState:
        return self._state

    @property
    def metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_production(self) -> bool:
        return self._state == ModelVersionState.PRODUCTION

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the version."""
        logger.info("Initializing ModelVersion [%s] for %s v%d", self._id, self._model_id, self._version_num)
        await asyncio.sleep(0.001)

    async def shutdown(self) -> None:
        """Clean up version resources."""
        self._artifacts.clear()

    # ------------------------------------------------------------------
    # State Transitions
    # ------------------------------------------------------------------

    async def promote_to_staging(self) -> None:
        """Promote version to staging."""
        if self._state != ModelVersionState.CREATED:
            raise RuntimeError(f"Cannot promote to staging from state: {self._state.value}")
        self._state = ModelVersionState.STAGING
        self._staged_at = datetime.now(timezone.utc)
        self._changelog.append(f"Promoted to staging at {self._staged_at.isoformat()}")
        logger.info("Version %s promoted to staging", self._id)

    async def promote_to_production(self) -> None:
        """Promote version to production."""
        if self._state != ModelVersionState.STAGING:
            raise RuntimeError(f"Cannot promote to production from state: {self._state.value}")
        self._state = ModelVersionState.PRODUCTION
        self._production_at = datetime.now(timezone.utc)
        self._changelog.append(f"Promoted to production at {self._production_at.isoformat()}")
        logger.info("Version %s promoted to production", self._id)

    async def archive(self) -> None:
        """Archive the version."""
        self._state = ModelVersionState.ARCHIVED
        self._archived_at = datetime.now(timezone.utc)
        self._changelog.append(f"Archived at {self._archived_at.isoformat()}")
        logger.info("Version %s archived", self._id)

    # ------------------------------------------------------------------
    # Metadata Management
    # ------------------------------------------------------------------

    async def set_metrics(self, metrics: Dict[str, Any]) -> None:
        """Set evaluation metrics for this version."""
        self._metrics = dict(metrics)
        logger.info("Metrics set for version %s: %s", self._id, list(metrics.keys()))

    async def set_params(self, params: Dict[str, Any]) -> None:
        """Set training parameters for this version."""
        self._params = dict(params)
        logger.info("Params set for version %s: %s", self._id, list(params.keys()))

    async def set_description(self, description: str) -> None:
        """Set version description."""
        self._description = description

    async def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the version."""
        self._tags[key] = value

    async def remove_tag(self, key: str) -> None:
        """Remove a tag."""
        self._tags.pop(key, None)

    async def add_changelog_entry(self, entry: str) -> None:
        """Add a changelog entry."""
        self._changelog.append(entry)

    # ------------------------------------------------------------------
    # Artifact Linking
    # ------------------------------------------------------------------

    async def link_artifact(self, artifact_id: str) -> None:
        """Link an artifact to this version."""
        if artifact_id not in self._artifacts:
            self._artifacts.append(artifact_id)

    async def unlink_artifact(self, artifact_id: str) -> None:
        """Unlink an artifact."""
        self._artifacts = [a for a in self._artifacts if a != artifact_id]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def to_dict(self) -> Dict[str, Any]:
        """Export version as dictionary."""
        return {
            "id": self._id,
            "model_id": self._model_id,
            "version_num": self._version_num,
            "version_name": self._version_name,
            "state": self._state.value,
            "metrics": self._metrics,
            "params": self._params,
            "tags": self._tags,
            "description": self._description,
            "changelog": self._changelog,
            "artifact_count": len(self._artifacts),
            "created_at": self._created_at.isoformat(),
            "staged_at": self._staged_at.isoformat() if self._staged_at else None,
            "production_at": self._production_at.isoformat() if self._production_at else None,
            "archived_at": self._archived_at.isoformat() if self._archived_at else None,
        }
