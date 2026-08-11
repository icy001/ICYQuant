"""
Decision Lineage — End-to-end lineage tracking for autonomous decisions.

Traces every decision from initial research through to final execution,
creating a complete audit trail from hypothesis to fill.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LineageNode:
    """A single node in the decision lineage tree."""
    node_id: str
    node_type: str  # research, alpha, strategy, portfolio, risk, execution, fill
    timestamp: float
    entity_id: str = ""
    parent_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    children: list[str] = field(default_factory=list)


class DecisionLineage:
    """
    Complete lineage tracker for autonomous decisions.

    Builds a directed acyclic graph (DAG) of all decisions, from
    initial research hypotheses through to execution fills, enabling
    full answer to: "Why was this trade executed?"
    """

    def __init__(self):
        self._nodes: dict[str, LineageNode] = {}
        self._root_nodes: list[str] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str,
        entity_id: str = "",
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> LineageNode:
        """Add a node to the lineage tree."""
        import time
        node = LineageNode(
            node_id=node_id,
            node_type=node_type,
            timestamp=time.time(),
            entity_id=entity_id,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        self._nodes[node_id] = node

        if parent_id:
            parent = self._nodes.get(parent_id)
            if parent:
                parent.children.append(node_id)
        else:
            self._root_nodes.append(node_id)

        return node

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_chain(self, node_id: str) -> list[dict]:
        """Get the full chain from root to the given node."""
        chain = []
        current = self._nodes.get(node_id)
        while current:
            chain.append({
                "node_id": current.node_id,
                "node_type": current.node_type,
                "entity_id": current.entity_id,
                "timestamp": current.timestamp,
                "metadata": current.metadata,
            })
            current = self._nodes.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))

    def get_tree(self, node_id: Optional[str] = None) -> dict:
        """Get the full tree from a given node."""
        if node_id:
            return self._build_tree(node_id)
        # Return all root trees
        return {
            "roots": [
                self._build_tree(root) for root in self._root_nodes
            ]
        }

    def _build_tree(self, node_id: str) -> dict:
        node = self._nodes.get(node_id)
        if not node:
            return {}
        return {
            "node_id": node.node_id,
            "node_type": node.node_type,
            "entity_id": node.entity_id,
            "timestamp": node.timestamp,
            "children": [
                self._build_tree(child) for child in node.children
            ],
        }

    def find_by_entity(self, entity_id: str) -> list[LineageNode]:
        """Find all nodes matching an entity ID."""
        return [n for n in self._nodes.values() if n.entity_id == entity_id]

    # ------------------------------------------------------------------
    # Full Pipeline Trace
    # ------------------------------------------------------------------

    def build_pipeline_trace(
        self,
        research_id: str = "",
        alpha_id: str = "",
        strategy_id: str = "",
        portfolio_id: str = "",
        risk_decision_id: str = "",
        execution_plan_id: str = "",
        order_id: str = "",
        execution_id: str = "",
        fill_id: str = "",
    ) -> dict:
        """Build a complete pipeline trace with all stages."""
        trace = {
            "stages": [],
            "complete": True,
            "gaps": [],
        }

        stages = [
            ("research", research_id),
            ("alpha", alpha_id),
            ("strategy", strategy_id),
            ("portfolio", portfolio_id),
            ("risk_decision", risk_decision_id),
            ("execution_plan", execution_plan_id),
            ("order", order_id),
            ("execution", execution_id),
            ("fill", fill_id),
        ]

        for stage_name, entity_id in stages:
            nodes = self.find_by_entity(entity_id) if entity_id else []
            trace["stages"].append({
                "stage": stage_name,
                "entity_id": entity_id,
                "has_lineage": len(nodes) > 0,
                "nodes": len(nodes),
            })
            if not entity_id:
                trace["gaps"].append(stage_name)
                trace["complete"] = False

        return trace

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_nodes": len(self._nodes),
            "root_count": len(self._root_nodes),
            "max_depth": self._max_depth(),
            "node_types": self._count_by_type(),
        }

    def _max_depth(self) -> int:
        def depth(node_id: str) -> int:
            node = self._nodes.get(node_id)
            if not node or not node.children:
                return 1
            return 1 + max(depth(c) for c in node.children)

        if not self._root_nodes:
            return 0
        return max(depth(r) for r in self._root_nodes)

    def _count_by_type(self) -> dict:
        counts: dict[str, int] = {}
        for node in self._nodes.values():
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts
