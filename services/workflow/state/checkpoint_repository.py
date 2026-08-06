"""Checkpoint repository — persistence layer for checkpoints.

Supports: in-memory (default), PostgreSQL, Object Storage (extensible).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .checkpoint_manager import Checkpoint

logger = logging.getLogger(__name__)


class CheckpointRepository:
    """Abstract repository for checkpoint CRUD operations.

    In-memory implementation suitable for single-node deployments.
    Replace with DB-backed implementation for production.
    """

    def __init__(self):
        self._store: Dict[str, Dict[int, Checkpoint]] = {}  # execution_id → version → checkpoint

    async def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint."""
        eid = checkpoint.execution_id
        if eid not in self._store:
            self._store[eid] = {}
        self._store[eid][checkpoint.version] = checkpoint
        logger.debug("Checkpoint saved: %s v%d", eid, checkpoint.version)

    async def get_latest(self, execution_id: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for an execution."""
        versions = self._store.get(execution_id, {})
        if not versions:
            return None
        latest_version = max(versions.keys())
        return versions[latest_version]

    async def get_version(
        self, execution_id: str, version: int
    ) -> Optional[Checkpoint]:
        """Get a specific checkpoint version."""
        return self._store.get(execution_id, {}).get(version)

    async def list_for_execution(self, execution_id: str) -> List[Checkpoint]:
        """List all checkpoints for an execution, newest first."""
        versions = self._store.get(execution_id, {})
        return sorted(versions.values(), key=lambda c: c.version, reverse=True)

    async def prune(self, execution_id: str, keep_last: int) -> int:
        """Remove old checkpoints, keeping the most recent N."""
        versions = self._store.get(execution_id, {})
        if len(versions) <= keep_last:
            return 0

        sorted_versions = sorted(versions.keys(), reverse=True)
        to_remove = sorted_versions[keep_last:]
        for v in to_remove:
            del versions[v]
        logger.info("Pruned %d old checkpoints for %s", len(to_remove), execution_id)
        return len(to_remove)

    async def delete_all(self, execution_id: str) -> None:
        """Delete all checkpoints for an execution."""
        self._store.pop(execution_id, None)
