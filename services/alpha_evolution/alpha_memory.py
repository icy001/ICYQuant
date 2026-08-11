"""
Alpha Memory — Persistent store of all alpha candidates and their evolution history.

Records:
    - Alpha genome snapshots
    - Fitness history across generations
    - Validation results
    - Promotion/Rejection events
    - Lineage information
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlphaMemory:
    """
    Persistent memory for alpha candidates.

    Stores complete history of every alpha ever created, evaluated, or promoted.
    """

    def __init__(self, max_entries: int = 10000):
        self._alphas: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries

    # ── CRUD ───────────────────────────────────────────────

    async def create(self, alpha_id: str, data: Dict[str, Any]) -> None:
        """Record a new alpha candidate."""
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("status", "discovered")
        data.setdefault("generations", [])
        self._alphas[alpha_id] = data
        await self._prune()

    async def update(self, alpha_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing alpha record."""
        if alpha_id not in self._alphas:
            return None
        self._alphas[alpha_id].update(updates)
        self._alphas[alpha_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self._alphas[alpha_id]

    async def get(self, alpha_id: str) -> Optional[Dict[str, Any]]:
        return self._alphas.get(alpha_id)

    async def delete(self, alpha_id: str) -> bool:
        return self._alphas.pop(alpha_id, None) is not None

    # ── Queries ────────────────────────────────────────────

    async def list_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List alphas by status (discovered, validated, promoted, etc.)."""
        return [
            a for a in self._alphas.values()
            if a.get("status") == status
        ][:limit]

    async def list_promoted(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List promoted alphas, sorted by fitness."""
        promoted = [a for a in self._alphas.values() if a.get("status") == "promoted"]
        promoted.sort(key=lambda a: a.get("fitness", 0), reverse=True)
        return promoted[:limit]

    async def list_by_generation(self, generation: int) -> List[Dict[str, Any]]:
        return [
            a for a in self._alphas.values()
            if a.get("generation_born") == generation
        ]

    async def record_generation(
        self, alpha_id: str, generation: int, fitness: float, status: str
    ) -> None:
        """Record a generation snapshot for an alpha."""
        alpha = self._alphas.get(alpha_id)
        if alpha:
            alpha.setdefault("generations", []).append({
                "generation": generation,
                "fitness": fitness,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # ── Maintenance ────────────────────────────────────────

    async def _prune(self) -> None:
        """Prune oldest entries if exceeding max."""
        if len(self._alphas) > self._max_entries:
            # Keep promoted alphas, prune lowest fitness
            candidates = [
                (oid, a) for oid, a in self._alphas.items()
                if a.get("status") != "promoted" and a.get("status") != "elite"
            ]
            candidates.sort(key=lambda x: x[1].get("fitness", 0))
            to_remove = len(self._alphas) - self._max_entries
            for oid, _ in candidates[:to_remove]:
                del self._alphas[oid]
            logger.debug("Pruned %d alpha memory entries", to_remove)

    async def get_stats(self) -> Dict[str, Any]:
        statuses = {}
        for a in self._alphas.values():
            s = a.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {"total": len(self._alphas), "by_status": statuses}
