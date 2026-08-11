"""
Lineage Snapshot — frozen snapshot of lineage state at a point in time.

Used to capture and persist the full lineage state for later
reconstruction, replay, or time-travel queries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lineage_node import LineageNode
from .lineage_edge import LineageEdge
from .audit_hash import AuditHash


@dataclass
class LineageSnapshot:
    """A frozen snapshot of a lineage graph at a specific point in time.

    Includes the full node/edge state plus a hash for tamper detection.
    """

    snapshot_id: str
    correlation_id: str
    node_id: str  # The node this snapshot is anchored to

    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)

    snapshot_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute the snapshot hash from all contained data."""
        data = {
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "node_id": self.node_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "timestamp": self.timestamp,
        }
        self.snapshot_hash = AuditHash.compute_snapshot_hash(data)
        return self.snapshot_hash

    def verify_hash(self) -> bool:
        """Verify that the stored hash matches recomputed hash."""
        if not self.snapshot_hash:
            return False
        expected = AuditHash.compute_snapshot_hash({
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "node_id": self.node_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "timestamp": self.timestamp,
        })
        return self.snapshot_hash == expected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "node_id": self.node_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "snapshot_hash": self.snapshot_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LineageSnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            correlation_id=data.get("correlation_id", ""),
            node_id=data.get("node_id", ""),
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            snapshot_hash=data.get("snapshot_hash", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def capture(
        cls,
        graph: Any,  # LineageGraph
        node_id: str,
        correlation_id: str = "",
    ) -> "LineageSnapshot":
        """Capture a snapshot from a LineageGraph."""
        import uuid
        full_lineage = graph.get_full_lineage(node_id)
        all_nodes = [full_lineage["node"]] if full_lineage["node"] else []
        all_nodes += full_lineage["upstream"] + full_lineage["downstream"]

        # Get edges for these nodes
        node_ids = {n.get("node_id", "") for n in all_nodes if n}
        relevant_edges: List[Dict[str, Any]] = []
        for e in graph._edges.values():
            if e.source_node_id in node_ids and e.target_node_id in node_ids:
                relevant_edges.append(e.to_dict())

        snap = cls(
            snapshot_id=f"LSNAP-{uuid.uuid4().hex[:12].upper()}",
            correlation_id=correlation_id,
            node_id=node_id,
            nodes=[n for n in all_nodes if n],
            edges=relevant_edges,
        )
        snap.compute_hash()
        return snap
