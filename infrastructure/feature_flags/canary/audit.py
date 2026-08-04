"""
Canary release audit logging.

Records canary deployment operations for
compliance and debugging.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class CanaryAudit:
    """
    Audit logging for canary deployments.

    Records stage transitions, promotions,
    rollbacks, and health status changes.

    Usage:
        audit = CanaryAudit()
        await audit.record_promotion("new-risk", 1, 5.0, 25.0)
    """

    def __init__(self, max_entries: int = 10000) -> None:
        """Initialize canary audit."""
        self._entries: List[Dict[str, Any]] = []
        self._max_entries = max_entries
        self._lock = asyncio.Lock()

    async def record_promotion(
        self,
        feature_key: str,
        from_stage: int,
        from_percentage: float,
        to_percentage: float,
    ) -> Dict[str, Any]:
        """Record a stage promotion."""
        entry = {
            "type": "promotion",
            "feature_key": feature_key,
            "from_stage": from_stage,
            "from_percentage": from_percentage,
            "to_percentage": to_percentage,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def record_rollback(
        self,
        feature_key: str,
        rollback_type: str,
        from_percentage: float,
        to_percentage: float,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Record a rollback."""
        entry = {
            "type": "rollback",
            "feature_key": feature_key,
            "rollback_type": rollback_type,
            "from_percentage": from_percentage,
            "to_percentage": to_percentage,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def record_health_change(
        self,
        feature_key: str,
        from_status: str,
        to_status: str,
        score: float,
    ) -> Dict[str, Any]:
        """Record a health status change."""
        entry = {
            "type": "health_change",
            "feature_key": feature_key,
            "from_status": from_status,
            "to_status": to_status,
            "score": score,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def query(
        self,
        feature_key: Optional[str] = None,
        entry_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit entries."""
        async with self._lock:
            entries = list(reversed(self._entries))
        if feature_key:
            entries = [e for e in entries if e.get("feature_key") == feature_key]
        if entry_type:
            entries = [e for e in entries if e.get("type") == entry_type]
        return entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
        }

    async def _store(self, entry: Dict[str, Any]) -> None:
        """Store an audit entry."""
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                excess = len(self._entries) - self._max_entries
                self._entries = self._entries[excess:]
