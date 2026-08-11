"""Lineage Query — type-safe query interface for lineage graphs.

Provides get_lineage(), get_decision_history(), get_order_history(),
and other audit-oriented queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage_node import LineageNode, NodeType
from .lineage_graph import LineageGraph
from .lineage_snapshot import DecisionSnapshot


@dataclass
class LineageQuery:
    """Query interface operating over registered lineage graphs.

    Designed to answer institutional audit questions such as:
    - "Show me everything about order ORDER-001"
    - "What was the decision chain for this trade?"
    - "Which strategies produced trades in the last hour?"
    """

    _graphs: dict[str, LineageGraph] = field(default_factory=dict)
    _snapshots: dict[str, DecisionSnapshot] = field(default_factory=dict)

    # ── Registration ──────────────────────────────────────────────

    def register(self, graph: LineageGraph,
                 snapshots: dict[str, DecisionSnapshot] | None = None,
                 ) -> None:
        self._graphs[graph.lineage_id] = graph
        if snapshots:
            self._snapshots.update(snapshots)

    # ── Query: Lineage ────────────────────────────────────────────

    def get_lineage(self, lineage_id: str) -> dict[str, Any] | None:
        """Return full graph data for a lineage_id."""
        graph = self._graphs.get(lineage_id)
        if graph is None:
            return None
        return graph.to_dict()

    # ── Query: Decision history ───────────────────────────────────

    def get_decision_history(self, decision_id: str) -> dict[str, Any]:
        """Return all lineage nodes and edges related to a decision."""
        result: dict[str, Any] = {
            "decision_id": decision_id,
            "nodes": [],
            "edges": [],
            "snapshots": [],
        }
        for graph in self._graphs.values():
            for n in graph.nodes.values():
                if n.object_id == decision_id and n.node_type == NodeType.DECISION:
                    # collect full backward lineage
                    backward = graph.backward_from(n.node_id)
                    forward = graph.forward_from(n.node_id)
                    result["nodes"] = [x.to_dict() for x in backward + forward]
                    result["edges"] = [
                        e.to_dict() for e in graph.edges
                    ]
                    snap = self._snapshots.get(n.node_id)
                    if snap:
                        result["snapshots"].append(snap.to_dict())
                    return result
        return result

    # ── Query: Control history ────────────────────────────────────

    def get_control_history(self, lineage_id: str) -> dict[str, Any]:
        """Return control-layer nodes (Risk/Gov/Auth/Approval) for a lineage."""
        graph = self._graphs.get(lineage_id)
        if graph is None:
            return {"lineage_id": lineage_id, "nodes": [], "snapshots": []}

        control_nodes = [
            n.to_dict() for n in graph.nodes.values()
            if n.node_type.is_control_node
        ]
        snapshots = []
        for n in graph.nodes.values():
            snap = self._snapshots.get(n.node_id)
            if snap:
                snapshots.append(snap.to_dict())

        return {
            "lineage_id": lineage_id,
            "nodes": control_nodes,
            "snapshots": snapshots,
        }

    # ── Query: Order history ──────────────────────────────────────

    def get_order_history(self, order_id: str) -> dict[str, Any]:
        """Return the full ancestor chain for an order."""
        for graph in self._graphs.values():
            node = graph.get_node_by_object_id(order_id)
            if node and node.node_type == NodeType.ORDER:
                backward = graph.backward_from(node.node_id)
                forward = graph.forward_from(node.node_id)
                return {
                    "order_id": order_id,
                    "lineage_id": node.lineage_id,
                    "nodes": [n.to_dict() for n in backward + forward],
                    "edges": [e.to_dict() for e in graph.edges],
                }
        return {"order_id": order_id, "nodes": [], "edges": []}

    # ── Query: Certificate history ────────────────────────────────

    def get_certificate_history(self, certificate_id: str
                                ) -> dict[str, Any]:
        """Return the control lineage leading to and from a certificate."""
        for graph in self._graphs.values():
            node = graph.get_node_by_object_id(certificate_id)
            if node and node.node_type == NodeType.CERTIFICATE:
                backward = graph.backward_from(node.node_id)
                forward = graph.forward_from(node.node_id)
                return {
                    "certificate_id": certificate_id,
                    "lineage_id": node.lineage_id,
                    "nodes": [n.to_dict() for n in backward + forward],
                    "edges": [e.to_dict() for e in graph.edges],
                }
        return {
            "certificate_id": certificate_id,
            "nodes": [],
            "edges": [],
        }

    # ── Query: Strategy → trades ──────────────────────────────────

    def get_strategy_trades(self, strategy_id: str) -> dict[str, Any]:
        """Return all trades that originated from the given strategy."""
        trades: list[dict[str, Any]] = []
        for graph in self._graphs.values():
            node = graph.get_node_by_object_id(strategy_id)
            if node and node.node_type == NodeType.STRATEGY:
                forward = graph.forward_from(node.node_id)
                for n in forward:
                    if n.node_type == NodeType.TRADE:
                        trades.append(n.to_dict())
        return {
            "strategy_id": strategy_id,
            "trades": trades,
        }
