"""
Lineage Tracker — Tracks evolutionary lineage of factors and alphas.

Records parent-child relationships:
    - Which parent(s) produced each offspring
    - Mutation or crossover origin
    - Generation of creation
    - Full ancestral chain

Enables answering: "How was this alpha created?"
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LineageTracker:
    """Tracks evolutionary lineage of all individuals."""

    def __init__(self):
        self._lineage: Dict[str, Dict[str, Any]] = {}

    async def record_birth(
        self,
        child_id: str,
        parent_ids: List[str],
        method: str,  # "seed", "mutation", "crossover"
        generation: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the birth of a new individual."""
        self._lineage[child_id] = {
            "child_id": child_id,
            "parent_ids": parent_ids,
            "method": method,
            "generation_born": generation,
            "metadata": metadata or {},
        }

    async def get_lineage(self, individual_id: str) -> Optional[Dict[str, Any]]:
        return self._lineage.get(individual_id)

    async def get_ancestors(
        self, individual_id: str, max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Trace the full ancestral chain."""
        ancestors = []
        current = individual_id
        depth = 0
        while current and depth < max_depth:
            record = self._lineage.get(current)
            if not record:
                break
            ancestors.append(record)
            parents = record.get("parent_ids", [])
            current = parents[0] if parents else None
            depth += 1
        return ancestors

    async def get_descendants(self, individual_id: str) -> List[str]:
        """Find all descendants of an individual."""
        descendants = []
        for child_id, record in self._lineage.items():
            if individual_id in record.get("parent_ids", []):
                descendants.append(child_id)
                descendants.extend(await self.get_descendants(child_id))
        return descendants

    async def get_stats(self) -> Dict[str, Any]:
        methods = {}
        for record in self._lineage.values():
            m = record.get("method", "unknown")
            methods[m] = methods.get(m, 0) + 1
        return {"total_tracked": len(self._lineage), "by_method": methods}
