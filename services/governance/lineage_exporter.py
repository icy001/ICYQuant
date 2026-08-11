"""
Lineage Exporter — exports lineage graphs in various formats.

Supports export to:
  - Dict/JSON (for storage and API)
  - DOT (for Graphviz visualization)
  - Summary text (for human review)
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .lineage_graph import LineageGraph
from .lineage_node import LineageNodeType


class LineageExporter:
    """Exports lineage graphs in multiple formats."""

    def __init__(self, graph: Optional[LineageGraph] = None):
        self._graph = graph or LineageGraph()

    def set_graph(self, graph: LineageGraph) -> None:
        self._graph = graph

    # ── JSON/Dict ──

    def to_dict(self) -> Dict[str, Any]:
        """Export entire graph as a dict."""
        return self._graph.to_dict()

    def to_json(self, indent: int = 2) -> str:
        """Export entire graph as JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    # ── DOT (Graphviz) ──

    def to_dot(self, title: str = "ICYQuant Decision Lineage") -> str:
        """Export graph in DOT format for Graphviz visualization.

        Color codes:
          - Blue: Market/Factor/Signal/Strategy (data generating)
          - Green: Decision/Policy (core governance)
          - Orange: Authority/Approval (authorization)
          - Red: Order/Execution/Trade (execution)
          - Gray: Position/Ledger (settlement)
        """
        lines = [
            f'digraph "{title}" {{',
            '  rankdir=TB;',
            f'  label="{title}";',
            '  fontsize=18;',
            '  node [shape=box, style=filled, fontname="Arial"];',
            '  edge [fontname="Arial", fontsize=10];',
            '',
        ]

        # Node styles by type
        node_colors = {
            LineageNodeType.MARKET: "#BBDEFB",
            LineageNodeType.FACTOR: "#BBDEFB",
            LineageNodeType.SIGNAL: "#BBDEFB",
            LineageNodeType.STRATEGY: "#90CAF9",
            LineageNodeType.DECISION: "#A5D6A7",
            LineageNodeType.POLICY: "#A5D6A7",
            LineageNodeType.RISK: "#C8E6C9",
            LineageNodeType.ALLOCATION: "#C8E6C9",
            LineageNodeType.AUTHORITY: "#FFE0B2",
            LineageNodeType.DELEGATION: "#FFE0B2",
            LineageNodeType.APPROVAL: "#FFCC80",
            LineageNodeType.DECISION_GUARD: "#FFCC80",
            LineageNodeType.CERTIFICATE: "#FFCC80",
            LineageNodeType.ORDER: "#EF9A9A",
            LineageNodeType.EXECUTION: "#EF9A9A",
            LineageNodeType.TRADE: "#EF9A9A",
            LineageNodeType.POSITION: "#E0E0E0",
            LineageNodeType.LEDGER: "#E0E0E0",
            LineageNodeType.HUMAN_OVERRIDE: "#CE93D8",
            LineageNodeType.EMERGENCY_ACTION: "#CE93D8",
        }

        # Write nodes
        for node in self._graph._nodes.values():
            color = node_colors.get(node.node_type, "#FFFFFF")
            label = node.label.replace('"', '\\"')
            lines.append(
                f'  "{node.node_id}" [label="{label}", fillcolor="{color}"];'
            )

        lines.append("")

        # Write edges
        edge_styles = {
            "GENERATED": "solid",
            "USED": "dashed",
            "EVALUATED_BY": "dotted",
            "APPROVED_BY": "bold",
        }

        for edge in self._graph._edges.values():
            style = edge_styles.get(edge.edge_type.name, "solid")
            label = edge.label.replace('"', '\\"')
            lines.append(
                f'  "{edge.source_node_id}" -> "{edge.target_node_id}" '
                f'[label="{label}", style="{style}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    # ── Summary ──

    def to_summary(self) -> Dict[str, Any]:
        """Export a human-readable summary."""
        node_type_counts: Dict[str, int] = {}
        edge_type_counts: Dict[str, int] = {}

        for node in self._graph._nodes.values():
            name = node.node_type.name
            node_type_counts[name] = node_type_counts.get(name, 0) + 1

        for edge in self._graph._edges.values():
            name = edge.edge_type.name
            edge_type_counts[name] = edge_type_counts.get(name, 0) + 1

        return {
            "total_nodes": self._graph.node_count,
            "total_edges": self._graph.edge_count,
            "node_types": node_type_counts,
            "edge_types": edge_type_counts,
            "root_nodes": len(self._graph.find_root_nodes()),
            "leaf_nodes": len(self._graph.find_leaf_nodes()),
            "orphans": len(self._graph.find_orphans()),
            "broken_edges": len(self._graph.find_broken_edges()),
        }
