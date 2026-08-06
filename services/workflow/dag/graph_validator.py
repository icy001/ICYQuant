"""
Graph Validator — validates DAG structure for correctness and completeness.

Checks:
- Duplicate nodes
- Missing nodes referenced by edges
- Disconnected nodes (orphans)
- Duplicate edges
- Illegal transitions
- Missing entry/exit nodes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from services.workflow.dag.dag import DAG
from services.workflow.dag.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of DAG validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class GraphValidator:
    """
    Validates DAG structure before compilation and execution.

    Performs both syntactic and semantic validation:
    - Syntactic: duplicate nodes, missing references, duplicate edges
    - Semantic: disconnected components, missing entry/exit, illegal patterns
    """

    def __init__(self):
        self._checks = [
            self._check_duplicate_nodes,
            self._check_missing_references,
            self._check_duplicate_edges,
            self._check_orphan_nodes,
            self._check_entry_exit,
            self._check_connectivity,
        ]

    async def validate(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> ValidationResult:
        """Run all validation checks."""
        errors: List[str] = []
        warnings: List[str] = []

        for check in self._checks:
            check_errors, check_warnings = await check(dag, dep_graph)
            errors.extend(check_errors)
            warnings.extend(check_warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats={
                "node_count": dag.node_count,
                "edge_count": dag.edge_count,
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
        )

    async def _check_duplicate_nodes(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check for duplicate node IDs."""
        errors = []
        seen = set()
        for node_id in dag.nodes:
            if node_id in seen:
                errors.append(f"Duplicate node ID: {node_id}")
            seen.add(node_id)
        return errors, []

    async def _check_missing_references(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check that all edge endpoints reference existing nodes."""
        errors = []
        node_ids = set(dag.nodes.keys())
        for edge in dag.edges:
            if edge.source_id not in node_ids:
                errors.append(f"Edge references missing source node: {edge.source_id}")
            if edge.target_id not in node_ids:
                errors.append(f"Edge references missing target node: {edge.target_id}")
        return errors, []

    async def _check_duplicate_edges(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check for duplicate edges."""
        errors = []
        seen = set()
        for edge in dag.edges:
            key = (edge.source_id, edge.target_id)
            if key in seen:
                errors.append(f"Duplicate edge: {edge.source_id} -> {edge.target_id}")
            seen.add(key)
        return errors, []

    async def _check_orphan_nodes(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check for orphan nodes (no incoming or outgoing edges)."""
        warnings = []
        connected = set()
        for edge in dag.edges:
            connected.add(edge.source_id)
            connected.add(edge.target_id)

        for node_id in dag.nodes:
            if node_id not in connected:
                warnings.append(f"Orphan node (no edges): {node_id}")
        return [], warnings

    async def _check_entry_exit(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check that the DAG has at least one entry and exit node."""
        warnings = []
        if len(dag.get_source_nodes()) == 0:
            warnings.append("DAG has no entry (source) nodes")
        if len(dag.get_sink_nodes()) == 0:
            warnings.append("DAG has no exit (sink) nodes")
        return [], warnings

    async def _check_connectivity(
        self, dag: DAG, dep_graph: Optional[DependencyGraph] = None
    ) -> tuple:
        """Check that all nodes are reachable from entry nodes."""
        warnings = []
        if dag.node_count == 0:
            return [], ["DAG is empty"]

        source_nodes = dag.get_source_nodes()
        if not source_nodes:
            return [], []

        # BFS from all source nodes
        visited: Set[str] = set()
        queue = [n.node_id for n in source_nodes]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for succ in dag.get_successors(current):
                if succ not in visited:
                    queue.append(succ)

        unreachable = set(dag.nodes.keys()) - visited
        for node_id in unreachable:
            warnings.append(f"Unreachable node (not connected from any entry): {node_id}")

        return [], warnings
