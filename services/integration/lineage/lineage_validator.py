"""Lineage Validator — enforces lineage invariants and structural rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage_node import LineageNode, NodeType
from .lineage_graph import LineageGraph
from .lineage_errors import (
    LineageIntegrityError,
    LineageCycleError,
    LineageBrokenLinkError,
    LineageInconsistencyError,
)


@dataclass
class LineageValidationError:
    """A single validation finding."""

    field: str = ""
    code: str = ""
    message: str = ""
    node_id: str = ""


@dataclass
class LineageValidationReport:
    """Aggregate result of validating a lineage graph."""

    valid: bool = True
    lineage_id: str = ""
    errors: list[LineageValidationError] = field(default_factory=list)
    warnings: list[LineageValidationError] = field(default_factory=list)
    validated_at: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    def add_error(self, field: str = "", code: str = "",
                  message: str = "", node_id: str = "") -> None:
        self.errors.append(LineageValidationError(
            field=field, code=code, message=message, node_id=node_id,
        ))
        self.valid = False

    def add_warning(self, field: str = "", code: str = "",
                    message: str = "", node_id: str = "") -> None:
        self.warnings.append(LineageValidationError(
            field=field, code=code, message=message, node_id=node_id,
        ))


# The minimum required node types for a complete control lineage.
REQUIRED_NODE_TYPES: list[NodeType] = [
    NodeType.STRATEGY,
    NodeType.SIGNAL,
    NodeType.DECISION,
    NodeType.RISK_DECISION,
    NodeType.GOVERNANCE_DECISION,
    NodeType.AUTHORITY_DECISION,
    NodeType.APPROVAL,
    NodeType.ORDER_INTENT,
    NodeType.CERTIFICATE,
    NodeType.ORDER,
]

# Optional (execution-layer) but strongly recommended.
RECOMMENDED_NODE_TYPES: list[NodeType] = [
    NodeType.ADMISSION,
    NodeType.EXECUTION,
    NodeType.TRADE,
]


@dataclass
class LineageValidator:
    """Validates structural and semantic correctness of a lineage graph.

    Checks for cycles, broken links, missing required nodes, lineage ID
    consistency, and parent-child integrity.
    """

    strict: bool = False
    """When True, warn on recommended-but-missing node types."""

    # ── Top-level validation ──────────────────────────────────────

    def validate(self, graph: LineageGraph) -> LineageValidationReport:
        report = LineageValidationReport(lineage_id=graph.lineage_id)

        self._check_cycles(graph, report)
        self._check_broken_links(graph, report)
        self._check_required_nodes(graph, report)
        self._check_lineage_id_consistency(graph, report)
        self._check_parent_edges(graph, report)

        if self.strict:
            self._check_recommended_nodes(graph, report)

        return report

    # ── Individual checks ─────────────────────────────────────────

    def _check_cycles(self, graph: LineageGraph,
                      report: LineageValidationReport) -> None:
        if graph.has_cycle():
            report.add_error(
                code="LINEAGE_CYCLE",
                message="Lineage graph contains a cycle",
            )

    def _check_broken_links(self, graph: LineageGraph,
                            report: LineageValidationReport) -> None:
        issues = graph.check_broken_links()
        for msg in issues:
            report.add_error(code="LINEAGE_BROKEN_LINK", message=msg)

    def _check_required_nodes(self, graph: LineageGraph,
                              report: LineageValidationReport) -> None:
        present = {
            n.node_type for n in graph.nodes.values()
        }
        for nt in REQUIRED_NODE_TYPES:
            if nt not in present:
                report.add_error(
                    field="nodes",
                    code="MISSING_REQUIRED_NODE",
                    message=f"Required node type missing: {nt.name}",
                )

    def _check_recommended_nodes(self, graph: LineageGraph,
                                 report: LineageValidationReport) -> None:
        present = {
            n.node_type for n in graph.nodes.values()
        }
        for nt in RECOMMENDED_NODE_TYPES:
            if nt not in present:
                report.add_warning(
                    field="nodes",
                    code="MISSING_RECOMMENDED_NODE",
                    message=f"Recommended node type missing: {nt.name}",
                )

    def _check_lineage_id_consistency(
        self, graph: LineageGraph,
        report: LineageValidationReport,
    ) -> None:
        for n in graph.nodes.values():
            if n.lineage_id and n.lineage_id != graph.lineage_id:
                report.add_error(
                    field="lineage_id",
                    code="LINEAGE_ID_MISMATCH",
                    message=(
                        f"Node {n.node_id} has lineage_id "
                        f"{n.lineage_id} != graph {graph.lineage_id}"
                    ),
                    node_id=n.node_id,
                )
        for e in graph.edges:
            if e.lineage_id and e.lineage_id != graph.lineage_id:
                report.add_error(
                    field="lineage_id",
                    code="LINEAGE_ID_MISMATCH",
                    message=(
                        f"Edge {e.edge_id} has lineage_id "
                        f"{e.lineage_id} != graph {graph.lineage_id}"
                    ),
                )

    def _check_parent_edges(self, graph: LineageGraph,
                            report: LineageValidationReport) -> None:
        """Verify that every node with a parent_node_id has a
        corresponding incoming edge from that parent."""
        radj = graph._reverse_adjacency()
        for n in graph.nodes.values():
            if not n.parent_node_id:
                continue
            if n.parent_node_id not in graph.nodes:
                report.add_error(
                    code="ORPHAN_PARENT",
                    message=(
                        f"Node {n.node_id} references non-existent "
                        f"parent {n.parent_node_id}"
                    ),
                    node_id=n.node_id,
                )
                continue
            incoming = {
                from_id
                for from_id, _ in radj.get(n.node_id, [])
            }
            if n.parent_node_id not in incoming:
                report.add_error(
                    code="MISSING_PARENT_EDGE",
                    message=(
                        f"Node {n.node_id} parent_node_id={n.parent_node_id} "
                        f"has no corresponding edge"
                    ),
                    node_id=n.node_id,
                )
