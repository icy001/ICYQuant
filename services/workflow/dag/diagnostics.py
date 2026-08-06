"""
DAG Diagnostics — inspection and debugging tools for DAG execution.

Provides:
- DAG structure visualization (text-based)
- Node/edge inspection
- Execution state dump
- Bottleneck identification
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.workflow.dag.dag import DAG, DAGStatus
from services.workflow.dag.critical_path import CriticalPathAnalyzer
from services.workflow.dag.topological_sort import TopologicalSort

logger = logging.getLogger(__name__)


class DAGDiagnostics:
    """
    Diagnostic tools for inspecting and debugging DAGs.

    Useful for development, testing, and production troubleshooting.
    """

    def __init__(self):
        self.cpa = CriticalPathAnalyzer()
        self.topo = TopologicalSort()

    def inspect(self, dag: DAG) -> Dict[str, Any]:
        """
        Produce a comprehensive inspection report for a DAG.

        Returns:
            Dict with structure, statistics, and potential issues.
        """
        source_nodes = [n.node_id for n in dag.get_source_nodes()]
        sink_nodes = [n.node_id for n in dag.get_sink_nodes()]

        issues: List[str] = []

        # Check for potential issues
        if not source_nodes:
            issues.append("No source (entry) nodes found")
        if not sink_nodes:
            issues.append("No sink (exit) nodes found")

        for node_id, dag_node in dag.nodes.items():
            if dag_node.indegree == 0 and dag_node.outdegree == 0:
                issues.append(f"Orphan node: {node_id}")

        # Get critical path
        try:
            cp_result = self.cpa.analyze(dag)
            critical_path = cp_result.critical_path
        except Exception:
            critical_path = []

        return {
            "dag_id": dag.dag_id,
            "workflow_id": dag.workflow_id,
            "status": dag.status.value,
            "structure": {
                "node_count": dag.node_count,
                "edge_count": dag.edge_count,
                "source_nodes": source_nodes,
                "sink_nodes": sink_nodes,
                "stages": dag.stages,
            },
            "critical_path": critical_path,
            "issues": issues,
            "metadata": dag.metadata,
        }

    def visualize(self, dag: DAG) -> str:
        """
        Generate a text-based visualization of the DAG.

        Returns:
            Multi-line string showing the DAG structure.
        """
        lines = [f"DAG: {dag.dag_id} (workflow: {dag.workflow_id})"]
        lines.append(f"Status: {dag.status.value}")
        lines.append(f"Nodes: {dag.node_count}, Edges: {dag.edge_count}")
        lines.append("")

        if dag.stages:
            for stage_idx, stage_nodes in enumerate(dag.stages):
                lines.append(f"  Stage {stage_idx}:")
                for node_id in stage_nodes:
                    dag_node = dag.nodes.get(node_id)
                    if dag_node:
                        deps = ", ".join(dag_node.dependencies) if dag_node.dependencies else "none"
                        lines.append(f"    [{node_id}] deps=[{deps}]")
                lines.append("")
        else:
            lines.append("  (no stages — DAG not topologically sorted)")
            for node_id, dag_node in dag.nodes.items():
                deps = ", ".join(dag_node.dependencies) if dag_node.dependencies else "none"
                succs = ", ".join(dag.get_successors(node_id))
                lines.append(f"  [{node_id}] deps=[{deps}] -> [{succs}]")

        return "\n".join(lines)

    def diff(self, dag_a: DAG, dag_b: DAG) -> Dict[str, Any]:
        """
        Compute the difference between two DAGs.

        Returns:
            Dict with added/removed/changed nodes and edges.
        """
        nodes_a = set(dag_a.nodes.keys())
        nodes_b = set(dag_b.nodes.keys())

        edges_a = {(e.source_id, e.target_id) for e in dag_a.edges}
        edges_b = {(e.source_id, e.target_id) for e in dag_b.edges}

        return {
            "nodes_added": list(nodes_b - nodes_a),
            "nodes_removed": list(nodes_a - nodes_b),
            "nodes_common": list(nodes_a & nodes_b),
            "edges_added": list(edges_b - edges_a),
            "edges_removed": list(edges_a - edges_b),
        }
