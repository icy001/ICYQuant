"""
Rollout-specific audit integration.

Provides audit logging for rollout operations
including assignment decisions, progressive
stage transitions, and segment matching.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RolloutAudit:
    """
    Audit logging for rollout operations.

    Records rollout decisions, stage transitions,
    and configuration changes for compliance
    and debugging purposes.

    Usage:
        audit = RolloutAudit()
        await audit.record_assignment(
            flag_key="new-risk",
            target_id="account_123",
            assigned=True,
            percentage=10.0,
        )
    """

    def __init__(self, max_entries: int = 50000) -> None:
        """
        Initialize rollout audit.

        Args:
            max_entries: Maximum audit entries to retain.
        """
        self._entries: List[Dict[str, Any]] = []
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
        self._counters: Dict[str, int] = {
            "assignment": 0,
            "stage_transition": 0,
            "config_change": 0,
            "rollback": 0,
        }

    async def record_assignment(
        self,
        flag_key: str,
        target_id: str,
        assigned: bool,
        percentage: float,
        hash_value: Optional[int] = None,
        bucket: Optional[int] = None,
        segment_id: str = "",
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """
        Record a rollout assignment decision.

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            assigned: Whether target was assigned.
            percentage: Percentage used.
            hash_value: Computed hash value.
            bucket: Assigned bucket.
            segment_id: Matching segment ID.
            trace_id: Correlation trace ID.

        Returns:
            The audit entry.
        """
        entry = {
            "type": "assignment",
            "flag_key": flag_key,
            "target_id": target_id,
            "assigned": assigned,
            "percentage": percentage,
            "hash_value": hash_value,
            "bucket": bucket,
            "segment_id": segment_id,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._counters["assignment"] += 1
        await self._store_entry(entry)
        return entry

    async def record_stage_transition(
        self,
        feature_key: str,
        from_stage: int,
        to_stage: int,
        from_percentage: float,
        to_percentage: float,
        reason: str = "",
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """
        Record a progressive rollout stage transition.

        Args:
            feature_key: Feature flag key.
            from_stage: Previous stage index.
            to_stage: New stage index.
            from_percentage: Previous percentage.
            to_percentage: New percentage.
            reason: Reason for transition.
            trace_id: Correlation trace ID.

        Returns:
            The audit entry.
        """
        entry = {
            "type": "stage_transition",
            "feature_key": feature_key,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "from_percentage": from_percentage,
            "to_percentage": to_percentage,
            "reason": reason,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._counters["stage_transition"] += 1
        await self._store_entry(entry)
        return entry

    async def record_config_change(
        self,
        feature_key: str,
        change_type: str,
        old_value: Any,
        new_value: Any,
        operator: str = "system",
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Record a rollout configuration change.

        Args:
            feature_key: Feature flag key.
            change_type: Type of change.
            old_value: Previous value.
            new_value: New value.
            operator: Who performed the change.
            reason: Reason for the change.

        Returns:
            The audit entry.
        """
        entry = {
            "type": "config_change",
            "feature_key": feature_key,
            "change_type": change_type,
            "old_value": old_value,
            "new_value": new_value,
            "operator": operator,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._counters["config_change"] += 1
        await self._store_entry(entry)
        return entry

    async def record_rollback(
        self,
        feature_key: str,
        from_percentage: float,
        to_percentage: float,
        reason: str = "",
        operator: str = "system",
    ) -> Dict[str, Any]:
        """
        Record a rollout rollback.

        Args:
            feature_key: Feature flag key.
            from_percentage: Current percentage.
            to_percentage: Rollback percentage.
            reason: Reason for rollback.
            operator: Who performed the rollback.

        Returns:
            The audit entry.
        """
        entry = {
            "type": "rollback",
            "feature_key": feature_key,
            "from_percentage": from_percentage,
            "to_percentage": to_percentage,
            "reason": reason,
            "operator": operator,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._counters["rollback"] += 1
        await self._store_entry(entry)
        return entry

    async def query(
        self,
        flag_key: Optional[str] = None,
        entry_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit entries.

        Args:
            flag_key: Filter by flag key.
            entry_type: Filter by entry type.
            limit: Max entries to return.

        Returns:
            List of matching entries.
        """
        async with self._lock:
            entries = list(reversed(self._entries))

        if flag_key:
            entries = [
                e for e in entries
                if e.get("flag_key") == flag_key
                or e.get("feature_key") == flag_key
            ]
        if entry_type:
            entries = [e for e in entries if e.get("type") == entry_type]

        return entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
            "by_type": dict(self._counters),
        }

    async def clear(self) -> None:
        """Clear all audit entries."""
        async with self._lock:
            self._entries.clear()
            self._counters = {k: 0 for k in self._counters}

    async def _store_entry(self, entry: Dict[str, Any]) -> None:
        """Store an audit entry with eviction."""
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                excess = len(self._entries) - self._max_entries
                self._entries = self._entries[excess:]
