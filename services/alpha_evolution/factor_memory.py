"""Factor Memory — Persistent store of factor evolution history."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FactorMemory:
    """Persistent memory for factor candidates."""

    def __init__(self, max_entries: int = 20000):
        self._factors: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries

    async def create(self, factor_id: str, data: Dict[str, Any]) -> None:
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._factors[factor_id] = data
        await self._prune()

    async def get(self, factor_id: str) -> Optional[Dict[str, Any]]:
        return self._factors.get(factor_id)

    async def update(self, factor_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if factor_id in self._factors:
            self._factors[factor_id].update(updates)
        return self._factors.get(factor_id)

    async def list_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        return [f for f in self._factors.values() if f.get("status") == status][:limit]

    async def list_top(self, limit: int = 50) -> List[Dict[str, Any]]:
        sorted_f = sorted(self._factors.values(), key=lambda f: f.get("fitness", 0), reverse=True)
        return sorted_f[:limit]

    async def _prune(self) -> None:
        if len(self._factors) > self._max_entries:
            candidates = [(oid, f) for oid, f in self._factors.items() if f.get("status") != "promoted"]
            candidates.sort(key=lambda x: x[1].get("fitness", 0))
            for oid, _ in candidates[: len(self._factors) - self._max_entries]:
                del self._factors[oid]

    async def get_stats(self) -> Dict[str, Any]:
        statuses = {}
        for f in self._factors.values():
            s = f.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {"total": len(self._factors), "by_status": statuses}
