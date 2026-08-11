"""
Rollback Engine — Model version rollback management.

Supports rolling back models, strategies, portfolios, risk policies,
and execution policies to previous stable versions.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RollbackEngine:
    """
    Manages version rollbacks for models and policies.

    When a new version degrades, the Rollback Engine can restore
    the previous known-good version.
    """

    def __init__(self):
        self._rollbacks: list[dict] = []
        self._snapshots: dict[str, dict] = {}

    def snapshot(self, entity_id: str, version: str, state: dict) -> None:
        """Save a snapshot of an entity's state for future rollback."""
        self._snapshots[f"{entity_id}:{version}"] = {
            **state,
            "snapshot_at": time.time(),
        }

    def get_snapshot(self, entity_id: str, version: str) -> Optional[dict]:
        """Retrieve a saved snapshot."""
        return self._snapshots.get(f"{entity_id}:{version}")

    async def rollback(
        self,
        entity_id: str,
        from_version: str,
        to_version: str,
        reason: str = "",
        operator: str = "autonomous",
    ) -> tuple[bool, str]:
        """
        Rollback an entity to a previous version.

        Returns (success, message).
        """
        snapshot = self.get_snapshot(entity_id, to_version)
        if not snapshot:
            return False, f"No snapshot for v{to_version}"

        self._rollbacks.append({
            "entity_id": entity_id,
            "from_version": from_version,
            "to_version": to_version,
            "reason": reason,
            "operator": operator,
            "timestamp": time.time(),
        })

        logger.warning("Rollback: %s v%s → v%s (%s)", entity_id, from_version, to_version, reason)
        return True, ""

    def can_rollback(self, entity_id: str) -> list[str]:
        """Get available rollback versions for an entity."""
        versions = []
        for key in self._snapshots:
            if key.startswith(f"{entity_id}:"):
                versions.append(key.split(":", 1)[1])
        return versions

    def stats(self) -> dict:
        return {
            "rollbacks_total": len(self._rollbacks),
            "snapshots_total": len(self._snapshots),
        }
