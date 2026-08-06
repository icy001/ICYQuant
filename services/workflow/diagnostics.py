"""Workflow Diagnostics — inspection, visualization, and troubleshooting tools.

The :class:`WorkflowDiagnostics` provides:
* Structured inspection of workflow definitions
* Text-based DAG visualization
* Execution timeline analysis
* Validation diagnostics
* Diff between workflow versions
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_definition import WorkflowDefinition
from .workflow_validator import WorkflowValidator, ValidationReport

logger = logging.getLogger(__name__)


class WorkflowDiagnostics:
    """Inspection and troubleshooting utilities for workflow definitions."""

    def __init__(self) -> None:
        self._validator = WorkflowValidator()

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def inspect(self, definition: WorkflowDefinition) -> Dict[str, Any]:
        """Return a structured inspection report for a workflow definition."""
        node_types = {}
        for node in definition.nodes:
            t = node.node_type.value
            node_types[t] = node_types.get(t, 0) + 1

        edge_types = {}
        for edge in definition.edges:
            t = edge.edge_type.value
            edge_types[t] = edge_types.get(t, 0) + 1

        return {
            "name": definition.name,
            "version": definition.version,
            "status": definition.status.value,
            "owner": definition.owner,
            "tags": definition.tags,
            "node_count": definition.node_count,
            "edge_count": definition.edge_count,
            "node_types": node_types,
            "edge_types": edge_types,
            "entry_nodes": [n.node_id for n in definition.entry_nodes],
            "exit_nodes": [n.node_id for n in definition.exit_nodes],
            "max_parallelism": self._estimate_parallelism(definition),
            "depth": self._estimate_depth(definition),
        }

    def _estimate_parallelism(self, definition: WorkflowDefinition) -> int:
        """Estimate the maximum parallelism in the DAG."""
        # Count nodes at each topological level
        indegree: Dict[str, int] = {}
        successors: Dict[str, List[str]] = {}
        for node in definition.nodes:
            indegree[node.node_id] = len(definition.get_incoming_edges(node.node_id))
            successors[node.node_id] = definition.get_successors(node.node_id)

        # Kahn's algorithm with level tracking
        level: Dict[str, int] = {}
        ready = [n.node_id for n in definition.nodes if indegree[n.node_id] == 0]
        for nid in ready:
            level[nid] = 0

        max_level_nodes = 0
        while ready:
            node_id = ready.pop(0)
            current_level = level.get(node_id, 0)
            same_level = sum(1 for nid, lvl in level.items() if lvl == current_level)
            max_level_nodes = max(max_level_nodes, same_level)

            for succ in successors.get(node_id, []):
                indegree[succ] -= 1
                level[succ] = max(level.get(succ, 0), current_level + 1)
                if indegree[succ] == 0:
                    ready.append(succ)

        return max_level_nodes

    def _estimate_depth(self, definition: WorkflowDefinition) -> int:
        """Estimate the critical path length (depth) of the DAG."""
        indegree: Dict[str, int] = {}
        successors: Dict[str, List[str]] = {}
        for node in definition.nodes:
            indegree[node.node_id] = len(definition.get_incoming_edges(node.node_id))
            successors[node.node_id] = definition.get_successors(node.node_id)

        level: Dict[str, int] = {}
        ready = [n.node_id for n in definition.nodes if indegree[n.node_id] == 0]
        for nid in ready:
            level[nid] = 0

        max_level = 0
        while ready:
            node_id = ready.pop(0)
            current_level = level[node_id]
            max_level = max(max_level, current_level)
            for succ in successors.get(node_id, []):
                indegree[succ] -= 1
                level[succ] = max(level.get(succ, 0), current_level + 1)
                if indegree[succ] == 0:
                    ready.append(succ)

        return max_level

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, definition: WorkflowDefinition) -> ValidationReport:
        """Run validation and return a report."""
        return self._validator.validate(definition)

    def validate_and_raise(self, definition: WorkflowDefinition) -> None:
        """Validate and raise ValueError if errors are found."""
        report = self._validator.validate(definition)
        if not report.is_valid:
            errors = [str(i) for i in report.issues if i.severity == "error"]
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

    # ------------------------------------------------------------------
    # Visualization (text-based)
    # ------------------------------------------------------------------

    def visualize_text(self, definition: WorkflowDefinition) -> str:
        """Return a text-based visualization of the workflow DAG."""
        lines = [f"Workflow: {definition.name} v{definition.version}"]
        lines.append(f"Nodes: {definition.node_count} | Edges: {definition.edge_count}")
        lines.append("-" * 50)

        # Group nodes by topological level
        indegree: Dict[str, int] = {}
        successors: Dict[str, List[str]] = {}
        for node in definition.nodes:
            indegree[node.node_id] = len(definition.get_incoming_edges(node.node_id))
            successors[node.node_id] = definition.get_successors(node.node_id)

        level: Dict[str, int] = {}
        ready = [n.node_id for n in definition.nodes if indegree[n.node_id] == 0]
        for nid in ready:
            level[nid] = 0

        queue = list(ready)
        while queue:
            node_id = queue.pop(0)
            for succ in successors.get(node_id, []):
                indegree[succ] -= 1
                level[succ] = max(level.get(succ, 0), level[node_id] + 1)
                if indegree[succ] == 0:
                    queue.append(succ)

        # Group by level
        max_level = max(level.values()) if level else 0
        for lvl in range(max_level + 1):
            nodes_at_level = [nid for nid, l in level.items() if l == lvl]
            node_info = []
            for nid in nodes_at_level:
                node = definition.get_node(nid)
                if node:
                    node_info.append(f"{nid}({node.node_type.value})")
            lines.append(f"  Level {lvl}: {', '.join(node_info)}")

        lines.append("-" * 50)
        lines.append("Edges:")
        for edge in definition.edges:
            lines.append(f"  {edge.source_id} → {edge.target_id} [{edge.edge_type.value}]")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(
        self,
        old: WorkflowDefinition,
        new: WorkflowDefinition,
    ) -> Dict[str, Any]:
        """Compute a diff between two workflow definitions."""
        old_node_ids = {n.node_id for n in old.nodes}
        new_node_ids = {n.node_id for n in new.nodes}

        old_edge_keys = {(e.source_id, e.target_id) for e in old.edges}
        new_edge_keys = {(e.source_id, e.target_id) for e in new.edges}

        return {
            "name": f"{old.name} ({old.version} → {new.version})",
            "nodes_added": sorted(new_node_ids - old_node_ids),
            "nodes_removed": sorted(old_node_ids - new_node_ids),
            "edges_added": [
                f"{s} → {t}" for s, t in sorted(new_edge_keys - old_edge_keys)
            ],
            "edges_removed": [
                f"{s} → {t}" for s, t in sorted(old_edge_keys - new_edge_keys)
            ],
            "node_count_change": new.node_count - old.node_count,
            "edge_count_change": new.edge_count - old.edge_count,
        }
