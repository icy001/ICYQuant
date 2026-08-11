"""
Lineage Engine — central engine for building and querying decision lineage.

This is the main entry point for recording lineage nodes/edges and
resolving full decision chains. Works in tandem with AuditEngine
to provide complete traceability.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .lineage_node import LineageNode, LineageNodeType
from .lineage_edge import LineageEdge, LineageEdgeType
from .lineage_graph import LineageGraph
from .lineage_resolver import LineageResolver
from .lineage_snapshot import LineageSnapshot
from .lineage_query import LineageQuery, QueryDirection


class LineageEngine:
    """Central lineage recording and resolution engine.

    Responsibilities:
      1. Record nodes as decisions flow through the system
      2. Connect nodes with typed edges
      3. Resolve forward/backward lineage
      4. Capture lineage snapshots for integrity
      5. Support structured queries
    """

    def __init__(self, graph: Optional[LineageGraph] = None):
        self._graph = graph or LineageGraph()
        self._resolver = LineageResolver(self._graph)
        self._snapshots: Dict[str, LineageSnapshot] = {}

    # ── Recording ──

    def record_node(
        self,
        node_type: LineageNodeType,
        entity_type: str,
        entity_id: str,
        state: Optional[Dict[str, Any]] = None,
        correlation_id: str = "",
        label: str = "",
    ) -> LineageNode:
        """Record a node in the lineage graph."""
        node = LineageNode.create(
            node_type=node_type,
            entity_type=entity_type,
            entity_id=entity_id,
            state=state or {},
            correlation_id=correlation_id,
            label=label,
        )
        return self._graph.add_node(node)

    def record_edge(
        self,
        edge_type: LineageEdgeType,
        source_node_id: str,
        target_node_id: str,
    ) -> LineageEdge:
        """Record an edge between two existing nodes."""
        return self._graph.connect(source_node_id, target_node_id, edge_type)

    def record_chain(
        self,
        nodes_data: List[Dict[str, Any]],
        correlation_id: str = "",
    ) -> List[LineageNode]:
        """Record a chain of connected nodes.

        Each dict: {node_type, entity_type, entity_id, edge_type, state?}
        edge_type connects from the previous node to this one.
        """
        cid = correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}"
        recorded: List[LineageNode] = []
        prev_node_id: Optional[str] = None

        for i, data in enumerate(nodes_data):
            node = self.record_node(
                node_type=data["node_type"],
                entity_type=data.get("entity_type", ""),
                entity_id=data.get("entity_id", ""),
                state=data.get("state", {}),
                correlation_id=cid,
            )
            recorded.append(node)

            if prev_node_id and "edge_type" in data:
                self.record_edge(
                    edge_type=data["edge_type"],
                    source_node_id=prev_node_id,
                    target_node_id=node.node_id,
                )

            prev_node_id = node.node_id

        return recorded

    # ── Resolution ──

    def resolve_forward(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Resolve forward lineage from a node."""
        return self._resolver.resolve_forward(node_id, max_depth)

    def resolve_backward(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Resolve backward lineage from a node."""
        return self._resolver.resolve_backward(node_id, max_depth)

    def resolve_full(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Resolve full lineage around a node."""
        return self._resolver.resolve_full(node_id, max_depth)

    def why_executed(self, trade_id: str) -> Dict[str, Any]:
        """Answer: Why was this trade executed?"""
        return self._resolver.why_executed(trade_id)

    def why_rejected(self, decision_id: str) -> Dict[str, Any]:
        """Answer: Why was this decision rejected?"""
        return self._resolver.why_rejected(decision_id)

    # ── Query ──

    def query(self, query: "LineageQuery") -> Dict[str, Any]:
        """Execute a structured lineage query."""
        return query.execute_and_format(self._graph)

    def query_by_entity(self, entity_type: str, entity_id: str) -> List[LineageNode]:
        """Find all lineage nodes for a specific entity."""
        return self._graph.get_nodes_by_entity(entity_type, entity_id)

    def query_by_correlation(self, correlation_id: str) -> List[LineageNode]:
        """Find all lineage nodes sharing a correlation_id."""
        return self._graph.get_nodes_by_correlation(correlation_id)

    # ── Snapshot ──

    def take_snapshot(
        self, node_id: str, correlation_id: str = ""
    ) -> LineageSnapshot:
        """Capture a frozen snapshot of the current lineage state."""
        snap = LineageSnapshot.capture(self._graph, node_id, correlation_id)
        self._snapshots[snap.snapshot_id] = snap
        return snap

    def get_snapshot(self, snapshot_id: str) -> Optional[LineageSnapshot]:
        """Retrieve a previously captured snapshot."""
        return self._snapshots.get(snapshot_id)

    def replay_node(self, node_id: str) -> Dict[str, Any]:
        """Replay the lineage to verify consistency.

        Takes a snapshot and verifies its hash.
        """
        snap = self.take_snapshot(node_id)
        hash_valid = snap.verify_hash()
        return {
            "snapshot_id": snap.snapshot_id,
            "node_id": node_id,
            "hash_valid": hash_valid,
            "snapshot_hash": snap.snapshot_hash,
            "node_count": len(snap.nodes),
            "edge_count": len(snap.edges),
        }

    # ── Completeness ──

    def check_completeness(self, correlation_id: str) -> Dict[str, Any]:
        """Check if a lineage chain has all required nodes.

        Required chain: MARKET → SIGNAL → STRATEGY → DECISION →
                        POLICY → AUTHORITY → APPROVAL → ORDER →
                        EXECUTION → TRADE
        """
        nodes = self.query_by_correlation(correlation_id)
        node_types_found = {n.node_type for n in nodes}

        required = [
            LineageNodeType.DECISION,
            LineageNodeType.POLICY,
            LineageNodeType.AUTHORITY,
        ]
        optional = [
            LineageNodeType.MARKET,
            LineageNodeType.SIGNAL,
            LineageNodeType.STRATEGY,
            LineageNodeType.APPROVAL,
            LineageNodeType.ORDER,
            LineageNodeType.EXECUTION,
            LineageNodeType.TRADE,
        ]

        missing = [t for t in required if t not in node_types_found]
        found_optional = [t for t in optional if t in node_types_found]

        return {
            "complete": len(missing) == 0,
            "correlation_id": correlation_id,
            "nodes_found": [n.node_type.name for n in nodes],
            "missing_required": [t.name for t in missing],
            "found_optional": [t.name for t in found_optional],
            "total_nodes": len(nodes),
        }

    # ── Orphan Detection ──

    def detect_orphans(self) -> Dict[str, Any]:
        """Detect orphan nodes in the lineage graph."""
        orphans = self._graph.find_orphans()
        broken_edges = self._graph.find_broken_edges()
        return {
            "orphan_count": len(orphans),
            "orphans": [o.to_dict() for o in orphans],
            "broken_edge_count": len(broken_edges),
            "broken_edges": [e.to_dict() for e in broken_edges],
        }

    # ── Properties ──

    @property
    def graph(self) -> LineageGraph:
        return self._graph

    @property
    def node_count(self) -> int:
        return self._graph.node_count

    @property
    def edge_count(self) -> int:
        return self._graph.edge_count

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "snapshot_count": self.snapshot_count,
        }
