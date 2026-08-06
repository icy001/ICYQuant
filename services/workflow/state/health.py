"""State health — unified health check for all state components."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .checkpoint_manager import CheckpointManager
from .snapshot_manager import SnapshotManager
from .wal import WAL
from .journal import Journal
from .consistency_checker import ConsistencyChecker

logger = logging.getLogger(__name__)


class StateHealthChecker:
    """Unified health check for workflow state management components.

    Returns a health status dict compatible with monitoring systems.
    """

    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        wal: Optional[WAL] = None,
        journal: Optional[Journal] = None,
        consistency_checker: Optional[ConsistencyChecker] = None,
    ):
        self._checkpoint = checkpoint_manager
        self._snapshot = snapshot_manager
        self._wal = wal
        self._journal = journal
        self._consistency = consistency_checker

    async def check(self) -> Dict[str, Any]:
        """Run all health checks. Returns a dict with per-component status."""
        components: Dict[str, bool] = {}

        # Checkpoint
        components["checkpoint_manager"] = self._checkpoint is not None

        # Snapshot
        components["snapshot_manager"] = self._snapshot is not None

        # WAL
        components["wal"] = self._wal is not None

        # Journal
        components["journal"] = self._journal is not None

        # Consistency checker
        components["consistency_checker"] = self._consistency is not None

        all_healthy = all(components.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
