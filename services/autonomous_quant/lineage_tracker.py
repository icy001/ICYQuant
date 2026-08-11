"""Lineage Tracker — Full research lineage from observation to strategy.

Traces: Market Observation → Opportunity → Hypothesis → Research Plan →
Feature → Factor → Alpha → Strategy → Backtest → Validation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LineageTracker:
    """Tracks complete research lineage for audit and reproducibility."""

    def __init__(self) -> None:
        self._lineages: Dict[str, Dict[str, Any]] = {}

    async def start_lineage(self, cycle_id: str) -> str:
        lineage_id = f"lin_{cycle_id}"
        self._lineages[lineage_id] = {
            "lineage_id": lineage_id,
            "cycle_id": cycle_id,
            "nodes": [],
            "edges": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        return lineage_id

    async def add_node(
        self,
        lineage_id: str,
        node_type: str,
        node_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        lineage = self._lineages.get(lineage_id)
        if not lineage:
            return
        node = {
            "node_type": node_type,
            "node_id": node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        if lineage["nodes"]:
            prev = lineage["nodes"][-1]
            lineage["edges"].append({
                "from": prev["node_id"],
                "from_type": prev["node_type"],
                "to": node_id,
                "to_type": node_type,
            })
        lineage["nodes"].append(node)

    async def complete_lineage(self, lineage_id: str) -> None:
        lineage = self._lineages.get(lineage_id)
        if lineage:
            lineage["status"] = "completed"
            lineage["completed_at"] = datetime.now(timezone.utc).isoformat()

    async def get_lineage(self, lineage_id: str) -> Optional[Dict[str, Any]]:
        return self._lineages.get(lineage_id)

    async def get_all_lineages(self) -> Dict[str, Any]:
        return {
            "total": len(self._lineages),
            "active": sum(1 for l in self._lineages.values() if l["status"] == "active"),
            "completed": sum(1 for l in self._lineages.values() if l["status"] == "completed"),
        }
