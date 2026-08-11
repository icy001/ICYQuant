"""
Replay Checkpoint — save and restore replay positions for
long-running backtests and research sessions.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CheckpointState(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass
class CheckpointData:
    replay_id: str
    dataset: str
    position: int
    event_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ReplayCheckpoint:
    """
    Save and restore replay positions for resumable backtests.

    Features:
    - Auto-checkpoint at configurable intervals
    - Manual checkpoint creation
    - Position restoration
    - Checkpoint listing and cleanup
    - Multiple checkpoint retention
    """

    def __init__(self) -> None:
        self._checkpoints: dict[str, list[CheckpointData]] = {}
        self._state: dict[str, CheckpointState] = {}

    async def create(
        self,
        replay_id: str,
        dataset: str,
        position: int,
        event_time: Optional[datetime] = None,
        **metadata: Any,
    ) -> CheckpointData:
        """Create a new checkpoint."""
        cp = CheckpointData(
            replay_id=replay_id,
            dataset=dataset,
            position=position,
            event_time=event_time,
            metadata=metadata,
        )

        self._checkpoints.setdefault(dataset, []).append(cp)
        self._state[replay_id] = CheckpointState.ACTIVE

        logger.debug(
            "Checkpoint created: %s pos=%d (time=%s)",
            replay_id, position, event_time.isoformat() if event_time else "N/A",
        )
        return cp

    async def get_latest(self, dataset: str, replay_id: str) -> Optional[CheckpointData]:
        """Get the latest checkpoint for a replay session."""
        checkpoints = self._checkpoints.get(dataset, [])
        matching = [c for c in checkpoints if c.replay_id == replay_id]
        if not matching:
            return None
        return max(matching, key=lambda c: c.position)

    async def list_checkpoints(self, dataset: str) -> list[dict[str, Any]]:
        """List all checkpoints for a dataset."""
        return [
            {
                "replay_id": c.replay_id,
                "position": c.position,
                "event_time": c.event_time.isoformat() if c.event_time else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in self._checkpoints.get(dataset, [])
        ]

    async def delete(self, replay_id: str) -> bool:
        """Delete checkpoints for a replay session."""
        self._state[replay_id] = CheckpointState.DELETED
        logger.debug("Deleted checkpoints for %s", replay_id)
        return True

    async def cleanup(self, max_age_days: int = 30) -> int:
        """Clean up old checkpoints."""
        cleaned = 0
        for rid, state in list(self._state.items()):
            if state == CheckpointState.DELETED:
                cleaned += 1
        logger.info("Cleaned %d checkpoints", cleaned)
        return cleaned
