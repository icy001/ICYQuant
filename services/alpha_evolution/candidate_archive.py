"""
Candidate Archive — Central registry for all factor/alpha candidates.

Unified store for:
    - Discovery candidates
    - Evolution candidates
    - Validated candidates
    - Promoted candidates
    - Rejected candidates

Provides query interface for the entire candidate lifecycle.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CandidateStatus(Enum):
    DISCOVERED = "discovered"
    EVOLVING = "evolving"
    EVALUATED = "evaluated"
    VALIDATED = "validated"
    ELITE = "elite"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    REDUNDANT = "redundant"
    ARCHIVED = "archived"


class CandidateArchive:
    """Central archive for all factor and alpha candidates."""

    def __init__(self, max_candidates: int = 5000):
        self._candidates: Dict[str, Dict[str, Any]] = {}
        self._max_candidates = max_candidates

    async def register(self, candidate_id: str, data: Dict[str, Any]) -> None:
        """Register a new candidate."""
        data.setdefault("status", CandidateStatus.DISCOVERED.value)
        data.setdefault("history", [])
        self._candidates[candidate_id] = data
        await self._prune()

    async def update_status(self, candidate_id: str, status: CandidateStatus) -> None:
        if candidate_id in self._candidates:
            old_status = self._candidates[candidate_id].get("status")
            self._candidates[candidate_id]["status"] = status.value
            self._candidates[candidate_id].setdefault("history", []).append({
                "from": old_status,
                "to": status.value,
            })
            logger.debug("Candidate %s: %s → %s", candidate_id[:12], old_status, status.value)

    async def get(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        return self._candidates.get(candidate_id)

    async def list_by_status(self, status: CandidateStatus, limit: int = 100) -> List[Dict[str, Any]]:
        return [c for c in self._candidates.values() if c.get("status") == status.value][:limit]

    async def list_promoted(self, limit: int = 50) -> List[Dict[str, Any]]:
        promoted = await self.list_by_status(CandidateStatus.PROMOTED, limit * 2)
        promoted.sort(key=lambda c: c.get("fitness", 0), reverse=True)
        return promoted[:limit]

    async def _prune(self) -> None:
        if len(self._candidates) > self._max_candidates:
            candidates = [
                (oid, c) for oid, c in self._candidates.items()
                if c.get("status") not in (CandidateStatus.PROMOTED.value, CandidateStatus.ELITE.value)
            ]
            candidates.sort(key=lambda x: x[1].get("fitness", 0))
            for oid, _ in candidates[:len(self._candidates) - self._max_candidates]:
                del self._candidates[oid]

    async def get_stats(self) -> Dict[str, Any]:
        statuses = {}
        for c in self._candidates.values():
            s = c.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {"total": len(self._candidates), "by_status": statuses}

    async def get_top_by_fitness(self, n: int = 20) -> List[Dict[str, Any]]:
        sorted_c = sorted(self._candidates.values(), key=lambda c: c.get("fitness", 0), reverse=True)
        return sorted_c[:n]
