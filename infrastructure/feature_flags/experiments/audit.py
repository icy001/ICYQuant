"""
Experiment audit logging.

Records experiment operations for
compliance and debugging.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional


class ExperimentAudit:
    """Audit logging for experiment operations."""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._max_entries = max_entries
        self._lock = asyncio.Lock()

    async def record_start(
        self,
        experiment_id: str,
        feature_key: str,
    ) -> Dict[str, Any]:
        entry = {
            "type": "start",
            "experiment_id": experiment_id,
            "feature_key": feature_key,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def record_assignment(
        self,
        experiment_id: str,
        target_id: str,
        variant_id: str,
    ) -> Dict[str, Any]:
        entry = {
            "type": "assignment",
            "experiment_id": experiment_id,
            "target_id": target_id,
            "variant_id": variant_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def record_completion(
        self,
        experiment_id: str,
        winner_id: str,
    ) -> Dict[str, Any]:
        entry = {
            "type": "completion",
            "experiment_id": experiment_id,
            "winner_id": winner_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._store(entry)
        return entry

    async def query(
        self,
        experiment_id: Optional[str] = None,
        entry_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            entries = list(reversed(self._entries))
        if experiment_id:
            entries = [e for e in entries if e.get("experiment_id") == experiment_id]
        if entry_type:
            entries = [e for e in entries if e.get("type") == entry_type]
        return entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
        }

    async def _store(self, entry: Dict[str, Any]) -> None:
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                excess = len(self._entries) - self._max_entries
                self._entries = self._entries[excess:]
