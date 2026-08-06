"""Workflow Validator — validates workflow definitions for correctness.

Performs static analysis on workflow definitions to ensure they are:
* Acyclic (no loops in the DAG)
* Complete (no missing nodes or edges)
* Well-formed (valid transitions, no duplicate nodes)
* Executable (at least one entry and exit node)

Validation checks:
1. Duplicate node detection
2. Missing edge references (dangling targets)
3. Cycle detection (DFS-based)
4. Orphan node detection
5. Entry/exit node presence
6. Connectivity check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .workflow_definition import WorkflowDefinition

logger = logging.getLogger(__name__)


class ValidationSeverity:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: str
    code: str
    message: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None

    def __str__(self) -> str:
        prefix = f"[{self.severity.upper()}] {self.code}"
        if self.node_id:
            prefix += f" (node={self.node_id})"
        if self.edge_id:
            prefix += f" (edge={self.edge_id})"
        return f"{prefix}: {self.message}"


@dataclass
class ValidationReport:
    """Result of workflow validation."""

    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def add_error(self, code: str, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(severity=ValidationSeverity.ERROR, code=code, message=message, **kwargs))
        self.is_valid = False

    def add_warning(self, code: str, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(severity=ValidationSeverity.WARNING, code=code, message=message, **kwargs))

    def add_info(self, code: str, message: str, **kwargs) -> None:
        self.issues.append(ValidationIssue(severity=ValidationSeverity.INFO, code=code, message=message, **kwargs))


class WorkflowValidator:
    """Validates workflow definitions for correctness and executability."""

    def __init__(self) -> None:
        pass

    def validate(self, definition: WorkflowDefinition) -> ValidationReport:
        """Run all validation checks on a workflow definition.

        Returns a :class:`ValidationReport` with all issues found.
        """
        report = ValidationReport()

        self._check_duplicate_nodes(definition, report)
        self._check_missing_references(definition, report)
        self._check_cycles(definition, report)
        self._check_orphan_nodes(definition, report)
        self._check_entry_exit(definition, report)
        self._check_connectivity(definition, report)
        self._check_edge_validity(definition, report)

        report.summary = {
            "errors": report.error_count,
            "warnings": report.warning_count,
            "total_nodes": definition.node_count,
            "total_edges": definition.edge_count,
        }

        if report.is_valid:
            logger.info("Workflow %s v%s: validation passed (%d nodes, %d edges)",
                        definition.name, definition.version,
                        definition.node_count, definition.edge_count)
        else:
            logger.warning("Workflow %s v%s: validation failed with %d errors",
                           definition.name, definition.version, report.error_count)

        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_duplicate_nodes(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Check for duplicate node IDs."""
        seen: Set[str] = set()
        for node in definition.nodes:
            if node.node_id in seen:
                report.add_error(
                    "DUPLICATE_NODE",
                    f"Duplicate node ID: {node.node_id}",
                    node_id=node.node_id,
                )
            seen.add(node.node_id)

    def _check_missing_references(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Check that all edge references point to existing nodes."""
        node_ids = {n.node_id for n in definition.nodes}
        for edge in definition.edges:
            if edge.source_id not in node_ids:
                report.add_error(
                    "MISSING_SOURCE",
                    f"Edge references non-existent source node: {edge.source_id}",
                    edge_id=edge.edge_id,
                )
            if edge.target_id not in node_ids:
                report.add_error(
                    "MISSING_TARGET",
                    f"Edge references non-existent target node: {edge.target_id}",
                    edge_id=edge.edge_id,
                )

    def _check_cycles(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Detect cycles using DFS with white/gray/black coloring."""
        if definition.node_count == 0:
            return

        node_ids = {n.node_id for n in definition.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        for edge in definition.edges:
            adj.setdefault(edge.source_id, []).append(edge.target_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in node_ids}

        def dfs(node: str, path: List[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj.get(node, []):
                if color.get(neighbor) == GRAY:
                    # Found a back edge → cycle
                    cycle = path[path.index(neighbor):] + [neighbor]
                    report.add_error(
                        "CYCLE_DETECTED",
                        f"Cycle detected: {' → '.join(cycle)}",
                        node_id=node,
                    )
                    return True
                if color.get(neighbor) == WHITE:
                    if dfs(neighbor, path):
                        return True
            path.pop()
            color[node] = BLACK
            return False

        for nid in node_ids:
            if color.get(nid) == WHITE:
                dfs(nid, [])

    def _check_orphan_nodes(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Check for nodes with no incoming or outgoing edges (orphans)."""
        if definition.node_count <= 1:
            return

        sources = {e.source_id for e in definition.edges}
        targets = {e.target_id for e in definition.edges}

        for node in definition.nodes:
            has_incoming = node.node_id in targets
            has_outgoing = node.node_id in sources
            if not has_incoming and not has_outgoing:
                report.add_warning(
                    "ORPHAN_NODE",
                    f"Node is isolated (no edges): {node.node_id}",
                    node_id=node.node_id,
                )

    def _check_entry_exit(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Ensure the workflow has at least one entry and one exit point."""
        if definition.node_count == 0:
            report.add_error("EMPTY_WORKFLOW", "Workflow has no nodes")
            return

        entry_nodes = definition.entry_nodes
        exit_nodes = definition.exit_nodes

        if not entry_nodes:
            report.add_error("NO_ENTRY", "Workflow has no entry nodes (no nodes without incoming edges)")

        if not exit_nodes:
            report.add_error("NO_EXIT", "Workflow has no exit nodes (no nodes without outgoing edges)")

        if len(entry_nodes) > 1:
            report.add_warning(
                "MULTIPLE_ENTRY",
                f"Workflow has multiple entry nodes: {[n.node_id for n in entry_nodes]}",
            )

        if len(exit_nodes) > 1:
            report.add_warning(
                "MULTIPLE_EXIT",
                f"Workflow has multiple exit nodes: {[n.node_id for n in exit_nodes]}",
            )

    def _check_connectivity(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Check that all nodes are reachable from entry nodes."""
        if definition.node_count <= 1:
            return

        adj: Dict[str, List[str]] = {n.node_id: [] for n in definition.nodes}
        for edge in definition.edges:
            adj.setdefault(edge.source_id, []).append(edge.target_id)

        entry_nodes = [n.node_id for n in definition.entry_nodes]
        if not entry_nodes:
            return

        visited: Set[str] = set()
        stack = list(entry_nodes)
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    stack.append(neighbor)

        all_nodes = {n.node_id for n in definition.nodes}
        unreachable = all_nodes - visited
        for node_id in unreachable:
            report.add_warning(
                "UNREACHABLE_NODE",
                f"Node is not reachable from any entry point: {node_id}",
                node_id=node_id,
            )

    def _check_edge_validity(self, definition: WorkflowDefinition, report: ValidationReport) -> None:
        """Check for duplicate edges and self-loops."""
        seen_edges: Set[tuple] = set()
        for edge in definition.edges:
            key = (edge.source_id, edge.target_id)
            if key in seen_edges:
                report.add_warning(
                    "DUPLICATE_EDGE",
                    f"Duplicate edge: {edge.source_id} → {edge.target_id}",
                    edge_id=edge.edge_id,
                )
            seen_edges.add(key)

            if edge.source_id == edge.target_id:
                report.add_error(
                    "SELF_LOOP",
                    f"Self-loop detected: {edge.source_id} → {edge.source_id}",
                    edge_id=edge.edge_id,
                )
