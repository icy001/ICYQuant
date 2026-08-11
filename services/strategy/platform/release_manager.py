"""
Release Manager — Strategy version release management.

Manages release artifacts, channels, and version promotion
through the release pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReleaseStatus(str, Enum):
    """Release status."""
    DRAFT = "draft"
    BUILDING = "building"
    BUILT = "built"
    TESTING = "testing"
    VALIDATED = "validated"
    RELEASING = "releasing"
    RELEASED = "released"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReleaseChannel(str, Enum):
    """Release distribution channels."""
    DEV = "dev"
    STAGING = "staging"
    CANARY = "canary"
    PRODUCTION = "production"
    ARCHIVE = "archive"


@dataclass
class ReleaseArtifact:
    """Release artifact metadata."""
    artifact_id: str
    strategy_id: str
    version: str
    channel: ReleaseChannel = ReleaseChannel.DEV
    status: ReleaseStatus = ReleaseStatus.DRAFT
    package_hash: str = ""
    changelog: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    released_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class ReleaseManager:
    """
    Manages strategy release lifecycle and version promotion.

    Handles artifact creation, channel management, and release
    workflow across development, staging, canary, and production.

    Usage::

        rm = ReleaseManager()
        await rm.initialize()
        artifact = await rm.create_release(strategy_id, "1.2.0")
        await rm.promote(artifact.artifact_id, ReleaseChannel.PRODUCTION)
    """

    def __init__(self) -> None:
        self._releases: dict[str, ReleaseArtifact] = {}
        self._release_counter: int = 0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the release manager."""
        logger.info("ReleaseManager initialized.")

    async def stop(self) -> None:
        """Stop the release manager."""
        logger.info("ReleaseManager stopped.")

    # ---- Release Operations ----

    async def create_release(
        self,
        strategy_id: str,
        version: str,
        channel: ReleaseChannel = ReleaseChannel.DEV,
        changelog: str = "",
        **kwargs: Any,
    ) -> ReleaseArtifact:
        """Create a new release artifact."""
        async with self._lock:
            self._release_counter += 1
            artifact_id = f"rel_{self._release_counter:06d}"

            artifact = ReleaseArtifact(
                artifact_id=artifact_id,
                strategy_id=strategy_id,
                version=version,
                channel=channel,
                changelog=changelog,
                metadata=kwargs,
            )
            self._releases[artifact_id] = artifact

        logger.info(f"Release created: {artifact_id} ({strategy_id} v{version})")
        return artifact

    async def promote(
        self,
        artifact_id: str,
        target_channel: ReleaseChannel,
    ) -> ReleaseArtifact:
        """Promote a release to a new channel."""
        async with self._lock:
            artifact = self._releases.get(artifact_id)
            if not artifact:
                raise ValueError(f"Release not found: {artifact_id}")

            old_channel = artifact.channel
            artifact.channel = target_channel
            artifact.status = ReleaseStatus.RELEASED
            artifact.released_at = datetime.now(timezone.utc)

        logger.info(f"Release promoted: {artifact_id} {old_channel} -> {target_channel}")
        return artifact

    async def supersede(
        self,
        artifact_id: str,
        new_version: str,
    ) -> ReleaseArtifact:
        """Mark a release as superseded by a newer version."""
        async with self._lock:
            artifact = self._releases.get(artifact_id)
            if not artifact:
                raise ValueError(f"Release not found: {artifact_id}")

            artifact.status = ReleaseStatus.SUPERSEDED
            artifact.metadata["superseded_by"] = new_version

        logger.info(f"Release superseded: {artifact_id} by {new_version}")
        return artifact

    async def get_release(self, artifact_id: str) -> Optional[ReleaseArtifact]:
        """Get a release by ID."""
        return self._releases.get(artifact_id)

    async def get_latest_release(
        self,
        strategy_id: str,
        channel: Optional[ReleaseChannel] = None,
    ) -> Optional[ReleaseArtifact]:
        """Get the latest release for a strategy, optionally filtered by channel."""
        releases = [
            r for r in self._releases.values()
            if r.strategy_id == strategy_id
            and r.status == ReleaseStatus.RELEASED
        ]
        if channel:
            releases = [r for r in releases if r.channel == channel]
        if not releases:
            return None
        return max(releases, key=lambda r: r.released_at or r.created_at)

    async def list_releases(
        self,
        strategy_id: Optional[str] = None,
        channel: Optional[ReleaseChannel] = None,
        status: Optional[ReleaseStatus] = None,
        limit: int = 100,
    ) -> list[ReleaseArtifact]:
        """List releases with optional filters."""
        results = list(self._releases.values())
        if strategy_id:
            results = [r for r in results if r.strategy_id == strategy_id]
        if channel:
            results = [r for r in results if r.channel == channel]
        if status:
            results = [r for r in results if r.status == status]
        return sorted(results, key=lambda r: r.created_at, reverse=True)[:limit]
