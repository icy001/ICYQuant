"""
Risk repository — Legacy and Foundation layers.

The legacy ``RiskRepository`` provides a simple key-value store.
The ``FoundationRiskRepository`` adds async persistence for policies,
profiles, limits, snapshots, evaluations, and approvals used by the
production Risk Management Platform.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy Risk Repository
# ---------------------------------------------------------------------------


class RiskRepository:
    """Legacy in-memory key-value risk repository (backwards-compatible)."""

    def __init__(self) -> None:
        self.storage: dict[str, Any] = {}

    def save(self, key: str, value: Any) -> None:
        self.storage[key] = value

    def load(self, key: str) -> Any:
        return self.storage.get(key)


# ---------------------------------------------------------------------------
# Foundation Risk Repository
# ---------------------------------------------------------------------------


class FoundationRiskRepository:
    """
    Foundation-level async risk repository with structured persistence.

    Provides CRUD operations for all risk platform entities: policies,
    profiles, limits, snapshots, evaluations, and approvals.

    Usage::

        repo = FoundationRiskRepository()
        await repo.save_policy(policy)
        policy = await repo.load_policy("POL-001")
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._policies: dict[str, dict[str, Any]] = {}
        self._profiles: dict[str, dict[str, Any]] = {}
        self._limits: dict[str, dict[str, Any]] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._evaluations: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._configurations: dict[str, dict[str, Any]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    # ---- Policies ----

    async def save_policy(self, policy_id: str, policy: dict[str, Any]) -> None:
        async with self._lock:
            self._policies[policy_id] = policy
            logger.debug(f"Policy saved: {policy_id}")

    async def load_policy(self, policy_id: str) -> Optional[dict[str, Any]]:
        return self._policies.get(policy_id)

    async def list_policies(self) -> list[dict[str, Any]]:
        return list(self._policies.values())

    async def delete_policy(self, policy_id: str) -> bool:
        async with self._lock:
            return self._policies.pop(policy_id, None) is not None

    # ---- Profiles ----

    async def save_profile(self, profile_id: str, profile: dict[str, Any]) -> None:
        async with self._lock:
            self._profiles[profile_id] = profile
            logger.debug(f"Profile saved: {profile_id}")

    async def load_profile(self, profile_id: str) -> Optional[dict[str, Any]]:
        return self._profiles.get(profile_id)

    async def list_profiles(self) -> list[dict[str, Any]]:
        return list(self._profiles.values())

    async def delete_profile(self, profile_id: str) -> bool:
        async with self._lock:
            return self._profiles.pop(profile_id, None) is not None

    # ---- Limits ----

    async def save_limit(self, limit_id: str, limit: dict[str, Any]) -> None:
        async with self._lock:
            self._limits[limit_id] = limit

    async def load_limit(self, limit_id: str) -> Optional[dict[str, Any]]:
        return self._limits.get(limit_id)

    async def list_limits(self) -> list[dict[str, Any]]:
        return list(self._limits.values())

    async def delete_limit(self, limit_id: str) -> bool:
        async with self._lock:
            return self._limits.pop(limit_id, None) is not None

    # ---- Snapshots ----

    async def save_snapshot(self, snapshot_id: str, snapshot: dict[str, Any]) -> None:
        async with self._lock:
            self._snapshots[snapshot_id] = {
                **snapshot,
                "persisted_at": datetime.now(timezone.utc).isoformat(),
            }

    async def load_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        return self._snapshots.get(snapshot_id)

    async def list_snapshots(self) -> list[dict[str, Any]]:
        return sorted(
            self._snapshots.values(),
            key=lambda s: s.get("persisted_at", ""),
            reverse=True,
        )

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        async with self._lock:
            return self._snapshots.pop(snapshot_id, None) is not None

    # ---- Evaluations ----

    async def save_evaluation(self, eval_id: str, evaluation: dict[str, Any]) -> None:
        async with self._lock:
            self._evaluations[eval_id] = evaluation

    async def load_evaluation(self, eval_id: str) -> Optional[dict[str, Any]]:
        return self._evaluations.get(eval_id)

    async def list_evaluations(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        items = list(self._evaluations.values())
        return items[offset : offset + limit]

    # ---- Approvals ----

    async def save_approval(self, approval_id: str, approval: dict[str, Any]) -> None:
        async with self._lock:
            self._approvals[approval_id] = approval

    async def load_approval(self, approval_id: str) -> Optional[dict[str, Any]]:
        return self._approvals.get(approval_id)

    # ---- Configurations ----

    async def save_configuration(self, config_id: str, config: dict[str, Any]) -> None:
        async with self._lock:
            self._configurations[config_id] = config

    async def load_configuration(self, config_id: str) -> Optional[dict[str, Any]]:
        return self._configurations.get(config_id)

    # ---- Metadata ----

    async def save_metadata(self, key: str, value: dict[str, Any]) -> None:
        async with self._lock:
            self._metadata[key] = value

    async def load_metadata(self, key: str) -> Optional[dict[str, Any]]:
        return self._metadata.get(key)

    # ---- Bulk Operations ----

    async def health_check(self) -> dict[str, Any]:
        """Return repository health status."""
        return {
            "policies_count": len(self._policies),
            "profiles_count": len(self._profiles),
            "limits_count": len(self._limits),
            "snapshots_count": len(self._snapshots),
            "evaluations_count": len(self._evaluations),
            "approvals_count": len(self._approvals),
            "configurations_count": len(self._configurations),
        }

    async def clear(self) -> None:
        """Clear all stored data (primarily for testing)."""
        async with self._lock:
            self._policies.clear()
            self._profiles.clear()
            self._limits.clear()
            self._snapshots.clear()
            self._evaluations.clear()
            self._approvals.clear()
            self._configurations.clear()
            self._metadata.clear()
            logger.warning("FoundationRiskRepository cleared.")