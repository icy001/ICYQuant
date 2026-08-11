"""Lineage Resolver — resolve full lineage from any starting point.

Supports forward resolution (what came from this?) and backward
resolution (why did this happen?).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage_node import LineageNode, NodeType
from .lineage_graph import LineageGraph
from .lineage_errors import LineageNodeNotFoundError


@dataclass
class LineageResolution:
    """The result of resolving a lineage from a starting point."""

    lineage_id: str
    direction: str  # "forward" | "backward"
    nodes: list[LineageNode] = field(default_factory=list)
    source_node_id: str = ""

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    def display(self) -> str:
        """Return a tree-style string representation."""
        if not self.nodes:
            return "(empty lineage)"
        indent = ""
        rows: list[str] = []
        for node in self.nodes:
            rows.append(
                f"{indent}{node.node_type.label}: {node.object_id}"
            )
            indent = "  "
        return "\n".join(rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "direction": self.direction,
            "source_node_id": self.source_node_id,
            "nodes": [n.to_dict() for n in self.nodes],
        }


@dataclass
class LineageResolver:
    """Resolves a full control lineage from a given starting point.

    Works over a registry of LineageGraphs keyed by lineage_id and
    can resolve by order, trade, certificate, decision, or flow.
    """

    _graphs: dict[str, LineageGraph] = field(default_factory=dict)

    # ── Registration ──────────────────────────────────────────────

    def register(self, graph: LineageGraph) -> None:
        """Index a lineage graph for resolution."""
        self._graphs[graph.lineage_id] = graph

    def register_many(self, graphs: list[LineageGraph]) -> None:
        for g in graphs:
            self.register(g)

    # ── Node lookup ───────────────────────────────────────────────

    def _find_node(self, object_id: str,
                   node_type: NodeType | None = None,
                   ) -> tuple[str, LineageNode]:
        """Scan all graphs for a node matching object_id (and optionally type).

        Returns (lineage_id, node).
        """
        for lid, graph in self._graphs.items():
            for n in graph.nodes.values():
                if n.object_id == object_id:
                    if node_type is None or n.node_type == node_type:
                        return lid, n
        raise LineageNodeNotFoundError(object_id)

    # ── Resolution entry points ───────────────────────────────────

    def resolve_by_order(self, order_id: str) -> LineageResolution:
        """Resolve the full lineage backward from an order ID."""
        lid, node = self._find_node(order_id, NodeType.ORDER)
        graph = self._graphs[lid]
        nodes = graph.backward_from(node.node_id)
        return LineageResolution(
            lineage_id=lid,
            direction="backward",
            nodes=nodes,
            source_node_id=node.node_id,
        )

    def resolve_by_trade(self, trade_id: str) -> LineageResolution:
        """Resolve the full lineage backward from a trade ID."""
        lid, node = self._find_node(trade_id, NodeType.TRADE)
        graph = self._graphs[lid]
        nodes = graph.backward_from(node.node_id)
        return LineageResolution(
            lineage_id=lid,
            direction="backward",
            nodes=nodes,
            source_node_id=node.node_id,
        )

    def resolve_by_certificate(self, certificate_id: str
                               ) -> LineageResolution:
        """Resolve lineage bidirectionally from a certificate."""
        lid, node = self._find_node(certificate_id, NodeType.CERTIFICATE)
        graph = self._graphs[lid]
        backward = graph.backward_from(node.node_id)
        forward = graph.forward_from(node.node_id)
        # merge: ancestors (backward) already have anchor; append forward
        # excluding the anchor itself
        all_nodes = list(backward) + [
            n for n in forward if n.node_id != node.node_id
        ]
        return LineageResolution(
            lineage_id=lid,
            direction="bidirectional",
            nodes=all_nodes,
            source_node_id=node.node_id,
        )

    def resolve_by_decision(self, decision_id: str) -> LineageResolution:
        """Resolve forward from a decision."""
        lid, node = self._find_node(decision_id, NodeType.DECISION)
        graph = self._graphs[lid]
        forward = graph.forward_from(node.node_id)
        backward = graph.backward_from(node.node_id)
        # prepend ancestors (excluding anchor)
        all_nodes = (
            [n for n in backward if n.node_id != node.node_id]
            + list(forward)
        )
        return LineageResolution(
            lineage_id=lid,
            direction="bidirectional",
            nodes=all_nodes,
            source_node_id=node.node_id,
        )

    def resolve_by_flow(self, flow_id: str) -> list[LineageResolution]:
        """Resolve all lineages that contain a node with this flow_id."""
        results: list[LineageResolution] = []
        for lid, graph in self._graphs.items():
            nodes = [
                n for n in graph.nodes.values()
                if n.flow_id == flow_id
            ]
            if nodes:
                for n in nodes:
                    backward = graph.backward_from(n.node_id)
                    results.append(LineageResolution(
                        lineage_id=lid,
                        direction="backward",
                        nodes=backward,
                        source_node_id=n.node_id,
                    ))
        return results

    def resolve_lineage(self, lineage_id: str) -> LineageResolution:
        """Resolve the full graph for a given lineage_id."""
        graph = self._graphs.get(lineage_id)
        if graph is None:
            raise LineageNodeNotFoundError(
                lineage_id, lineage_id=lineage_id,
            )
        root = graph.root_nodes
        if root:
            nodes = graph.forward_from(root[0])
            return LineageResolution(
                lineage_id=lineage_id,
                direction="forward",
                nodes=nodes,
                source_node_id=root[0],
            )
        return LineageResolution(
            lineage_id=lineage_id,
            direction="forward",
            nodes=[],
        )
