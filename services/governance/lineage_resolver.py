"""
Lineage Resolver — forward and backward resolution of decision lineage.

  - Forward: Signal → Decision → Order → Execution → Trade
  - Backward: Trade → Order → Decision → Strategy → Signal → Market
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .lineage_graph import LineageGraph
from .lineage_node import LineageNode, LineageNodeType
from .lineage_edge import LineageEdge, LineageEdgeType


class LineageResolver:
    """Resolves full decision lineage in both directions.

    Forward resolution answers: "What happened because of X?"
    Backward resolution answers: "Why did Y happen?"
    """

    def __init__(self, graph: Optional[LineageGraph] = None):
        self._graph = graph or LineageGraph()

    @property
    def graph(self) -> LineageGraph:
        return self._graph

    # ── Forward Resolution ──

    def resolve_forward(
        self, node_id: str, max_depth: int = 20
    ) -> Dict[str, Any]:
        """Resolve what happened downstream of a node."""
        nodes = self._graph.get_downstream(node_id, max_depth)
        source = self._graph.get_node(node_id)
        return {
            "direction": "FORWARD",
            "source": source.to_dict() if source else None,
            "chain": [n.to_dict() for n in nodes],
            "chain_length": len(nodes),
            "terminal_node": nodes[-1].to_dict() if nodes else None,
        }

    def resolve_backward(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Resolve why a node happened (upstream)."""
        nodes = self._graph.get_upstream(node_id, max_depth)
        target = self._graph.get_node(node_id)
        return {
            "direction": "BACKWARD",
            "target": target.to_dict() if target else None,
            "chain": [n.to_dict() for n in nodes],
            "chain_length": len(nodes),
            "root_node": nodes[-1].to_dict() if nodes else None,
        }

    def resolve_full(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Resolve full lineage (both directions)."""
        return self._graph.get_full_lineage(node_id, max_depth)

    # ── Why Resolution ──

    def why_executed(self, trade_id: str) -> Dict[str, Any]:
        """Answer: Why was this trade executed?

        Returns the complete backward chain from Trade → Market.
        """
        trade_nodes = self._graph.get_nodes_by_entity("TRADE", trade_id)
        if not trade_nodes:
            return {"found": False, "trade_id": trade_id, "chain": []}

        node = trade_nodes[0]
        chain = self._graph.get_upstream(node.node_id)

        # Build narrative
        narrative = self._build_narrative(chain + [node], reverse=True)

        return {
            "found": True,
            "trade_id": trade_id,
            "chain": [n.to_dict() for n in chain + [node]],
            "chain_summary": narrative,
        }

    def why_rejected(self, decision_id: str) -> Dict[str, Any]:
        """Answer: Why was this decision rejected?

        Returns the specific policy rule or approval that blocked it.
        """
        nodes = self._graph.get_nodes_by_entity("DECISION", decision_id)
        if not nodes:
            return {"found": False, "decision_id": decision_id, "reasons": []}

        node = nodes[0]
        downstream = self._graph.get_downstream(node.node_id, max_depth=5)

        reasons: List[Dict[str, Any]] = []
        for d in downstream:
            if "rejected" in d.state.get("status", "").lower():
                reasons.append({
                    "node_id": d.node_id,
                    "node_type": d.node_type.name,
                    "entity_id": d.entity_id,
                    "state": d.state,
                })
            if d.node_type in (LineageNodeType.POLICY, LineageNodeType.APPROVAL):
                state = d.state
                if state.get("verdict") == "BLOCK" or state.get("effect") == "BLOCK":
                    reasons.append({
                        "node_id": d.node_id,
                        "node_type": d.node_type.name,
                        "entity_id": d.entity_id,
                        "reason": state.get("reason", "Policy blocked"),
                        "rule": state.get("rule_id", ""),
                        "observed": state.get("observed", ""),
                        "threshold": state.get("threshold", ""),
                    })

        return {
            "found": True,
            "decision_id": decision_id,
            "reasons": reasons,
            "rejected": len(reasons) > 0,
        }

    # ── Helpers ──

    def _build_narrative(
        self, nodes: List[LineageNode], reverse: bool = False
    ) -> List[str]:
        """Build a human-readable chain summary."""
        if reverse:
            nodes = list(reversed(nodes))
        narrative: List[str] = []
        for n in nodes:
            narrative.append(
                f"{n.node_type.name}: {n.label}"
            )
        return narrative

    def get_governance_state_at(
        self, node_id: str
    ) -> Dict[str, Any]:
        """Get the full governance state at a specific node.

        Collects: Active Policy, Authority, Approval, Risk state.
        """
        node = self._graph.get_node(node_id)
        if not node:
            return {"found": False}

        upstream = self._graph.get_upstream(node_id)
        state: Dict[str, Any] = {
            "at_node": node.to_dict(),
            "active_policy": None,
            "authority": None,
            "approval": None,
            "risk_snapshot": None,
        }

        for n in upstream:
            if n.node_type == LineageNodeType.POLICY:
                state["active_policy"] = n.to_dict()
            elif n.node_type == LineageNodeType.AUTHORITY:
                state["authority"] = n.to_dict()
            elif n.node_type == LineageNodeType.APPROVAL:
                state["approval"] = n.to_dict()
            elif n.node_type == LineageNodeType.RISK:
                state["risk_snapshot"] = n.to_dict()

        return state
