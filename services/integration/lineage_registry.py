"""Lineage Registry — authoritative repository for all control lineages.

Stores LineageGraphs and provides lookup, status management, and
cross-lineage queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage.lineage_node import LineageNode, NodeType
from .lineage.lineage_graph import LineageGraph
from .lineage.lineage_errors import LineageNodeNotFoundError


@dataclass
class LineageRegistryEntry:
    """Metadata and status for a registered lineage."""

    lineage_id: str
    graph: LineageGraph
    status: str = "ACTIVE"  # ACTIVE | COMPLETED | FROZEN | REVOKED
    created_at: float = field(
        default_factory=lambda: __import__("time").time(),
    )
    completed_at: float = 0.0
    node_count: int = 0
    edge_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


@dataclass
class LineageRegistry:
    """Central registry for all control lineage graphs.

    Provides:
    - Registration and lookup by lineage_id
    - Cross-reference by object_id (order, trade, certificate, etc.)
    - Status management
    - Statistics and summary queries
    """

    _entries: dict[str, LineageRegistryEntry] = field(default_factory=dict)
    _object_index: dict[str, str] = field(default_factory=dict)
    """object_id → lineage_id"""

    # ── Registration ──────────────────────────────────────────────

    def register(self, graph: LineageGraph,
                 status: str = "ACTIVE") -> LineageRegistryEntry:
        """Register a lineage graph and index all its nodes."""
        entry = LineageRegistryEntry(
            lineage_id=graph.lineage_id,
            graph=graph,
            status=status,
            node_count=graph.node_count,
            edge_count=graph.edge_count,
        )
        self._entries[graph.lineage_id] = entry

        # Index by object_id
        for n in graph.nodes.values():
            if n.object_id:
                self._object_index[n.object_id] = graph.lineage_id

        return entry

    # ── Lookup ────────────────────────────────────────────────────

    def get(self, lineage_id: str) -> LineageRegistryEntry | None:
        return self._entries.get(lineage_id)

    def get_graph(self, lineage_id: str) -> LineageGraph | None:
        entry = self._entries.get(lineage_id)
        return entry.graph if entry else None

    def find_by_object_id(self, object_id: str) -> LineageRegistryEntry | None:
        """Find the lineage containing the given object."""
        lid = self._object_index.get(object_id)
        if lid:
            return self._entries.get(lid)
        return None

    def find_lineage_id(self, object_id: str) -> str:
        """Return lineage_id for an object, or empty string."""
        return self._object_index.get(object_id, "")

    # ── Status management ─────────────────────────────────────────

    def complete(self, lineage_id: str) -> None:
        entry = self._entries.get(lineage_id)
        if entry:
            entry.status = "COMPLETED"
            entry.completed_at = __import__("time").time()

    def freeze(self, lineage_id: str) -> None:
        entry = self._entries.get(lineage_id)
        if entry:
            entry.status = "FROZEN"

    def revoke(self, lineage_id: str) -> None:
        entry = self._entries.get(lineage_id)
        if entry:
            entry.status = "REVOKED"

    # ── Queries ───────────────────────────────────────────────────

    @property
    def active_lineages(self) -> list[LineageRegistryEntry]:
        return [e for e in self._entries.values()
                if e.status == "ACTIVE"]

    @property
    def lineage_count(self) -> int:
        return len(self._entries)

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._entries.values():
            counts[e.status] = counts.get(e.status, 0) + 1
        return counts

    def list_lineages(self) -> list[str]:
        return list(self._entries.keys())

    # ── Validation helpers ────────────────────────────────────────

    def has_lineage(self, object_id: str) -> bool:
        """Check whether an object has a lineage registered."""
        return object_id in self._object_index

    def validate_ancestor(self, object_id: str,
                          ancestor_object_id: str) -> bool:
        """Check if ancestor is actually in the backward traversal of object."""
        lid = self._object_index.get(object_id)
        if not lid:
            return False
        graph = self._entries[lid].graph
        node = graph.get_node_by_object_id(object_id)
        if node is None:
            return False
        ancestors = graph.backward_from(node.node_id)
        ancestor_ids = {n.object_id for n in ancestors}
        return ancestor_object_id in ancestor_ids
