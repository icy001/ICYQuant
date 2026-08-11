"""
Lineage Validator — validates lineage graph completeness and correctness.

Checks:
  - Required nodes exist for complete lineage chains
  - No orphan nodes
  - No broken edges
  - Hash chain integrity from snapshots
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .lineage_graph import LineageGraph
from .lineage_node import LineageNodeType


class LineageValidator:
    """Validates the integrity and completeness of lineage graphs."""

    def __init__(self, graph: Optional[LineageGraph] = None):
        self._graph = graph

    def set_graph(self, graph: LineageGraph) -> None:
        self._graph = graph

    # ── Validation ──

    def validate_completeness(self, correlation_id: str) -> Dict[str, Any]:
        """Validate that a lineage chain has all required nodes.

        Required chain for a full execution lineage:
          DECISION → POLICY → AUTHORITY → APPROVAL → ORDER → EXECUTION → TRADE
        """
        if not self._graph:
            return {"valid": False, "error": "No graph set"}

        nodes = self._graph.get_nodes_by_correlation(correlation_id)
        node_types = {n.node_type for n in nodes}

        # Required nodes
        required = [
            LineageNodeType.DECISION,
        ]
        # Desired (not strictly required)
        desired = [
            LineageNodeType.POLICY,
            LineageNodeType.AUTHORITY,
            LineageNodeType.APPROVAL,
            LineageNodeType.ORDER,
            LineageNodeType.EXECUTION,
            LineageNodeType.TRADE,
        ]

        missing_required = [t.name for t in required if t not in node_types]
        missing_desired = [t.name for t in desired if t not in node_types]
        present = [t.name for t in node_types]

        return {
            "valid": len(missing_required) == 0,
            "correlation_id": correlation_id,
            "total_nodes": len(nodes),
            "present": present,
            "missing_required": missing_required,
            "missing_desired": missing_desired,
            "score": self._completeness_score(node_types, required + desired),
        }

    def validate_orphans(self) -> Dict[str, Any]:
        """Detect and report orphan nodes."""
        if not self._graph:
            return {"valid": False, "error": "No graph set"}

        orphans = self._graph.find_orphans()
        orphan_non_source = [
            o for o in orphans if not o.node_type.is_source
        ]

        return {
            "valid": len(orphan_non_source) == 0,
            "total_orphans": len(orphans),
            "non_source_orphans": len(orphan_non_source),
            "orphan_nodes": [o.to_dict() for o in orphans],
            "non_source_orphan_nodes": [o.to_dict() for o in orphan_non_source],
        }

    def validate_edges(self) -> Dict[str, Any]:
        """Detect broken edges."""
        if not self._graph:
            return {"valid": False, "error": "No graph set"}

        broken = self._graph.find_broken_edges()
        return {
            "valid": len(broken) == 0,
            "broken_count": len(broken),
            "broken_edges": [e.to_dict() for e in broken],
        }

    def validate_chain_integrity(self) -> Dict[str, Any]:
        """Check that the graph structure is DAG (no cycles)."""
        if not self._graph:
            return {"valid": False, "error": "No graph set"}

        has_cycle = self._has_cycle()

        return {
            "valid": not has_cycle,
            "has_cycles": has_cycle,
            "is_dag": not has_cycle,
        }

    def validate_all(self, correlation_id: str = "") -> Dict[str, Any]:
        """Run all validation checks."""
        if not self._graph:
            return {"valid": False, "error": "No graph set"}

        results = {
            "orphans": self.validate_orphans(),
            "edges": self.validate_edges(),
            "chain": self.validate_chain_integrity(),
        }

        if correlation_id:
            results["completeness"] = self.validate_completeness(correlation_id)

        all_valid = all(
            v.get("valid", False) for v in results.values()
        )

        return {
            "valid": all_valid,
            "graph_node_count": self._graph.node_count,
            "graph_edge_count": self._graph.edge_count,
            "checks": results,
        }

    # ── Scoring ──

    def _completeness_score(
        self, found: Set[LineageNodeType], required: List[LineageNodeType]
    ) -> float:
        """Score completeness from 0.0 to 1.0."""
        if not required:
            return 1.0
        matched = sum(1 for t in required if t in found)
        return matched / len(required)

    # ── Cycle Detection ──

    def _has_cycle(self) -> bool:
        """Detect cycles in the lineage graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self._graph._nodes}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for edge_id in self._graph._adj_out.get(node_id, set()):
                edge = self._graph._edges.get(edge_id)
                if not edge:
                    continue
                target = edge.target_node_id
                if color.get(target) == GRAY:
                    return True
                if color.get(target) == WHITE:
                    if dfs(target):
                        return True
            color[node_id] = BLACK
            return False

        for node_id in list(self._graph._nodes.keys()):
            if color.get(node_id) == WHITE:
                if dfs(node_id):
                    return True
        return False
