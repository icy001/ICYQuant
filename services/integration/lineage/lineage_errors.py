"""Lineage-related error types."""

from __future__ import annotations


class LineageError(Exception):
    """Base error for all lineage operations."""

    def __init__(self, message: str, lineage_id: str = "",
                 code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.lineage_id: str = lineage_id
        self.code: str = code or "LINEAGE_ERROR"


class LineageNodeNotFoundError(LineageError):
    """No node found for the given node_id within a lineage."""

    def __init__(self, node_id: str, lineage_id: str = "") -> None:
        super().__init__(
            message=f"Lineage node not found: node_id={node_id}",
            lineage_id=lineage_id,
            code="LINEAGE_NODE_NOT_FOUND",
        )
        self.node_id: str = node_id


class LineageEdgeNotFoundError(LineageError):
    """No edge found between expected nodes."""

    def __init__(self, from_node_id: str, to_node_id: str,
                 lineage_id: str = "") -> None:
        super().__init__(
            message=(
                f"Lineage edge not found: "
                f"from={from_node_id} to={to_node_id}"
            ),
            lineage_id=lineage_id,
            code="LINEAGE_EDGE_NOT_FOUND",
        )
        self.from_node_id: str = from_node_id
        self.to_node_id: str = to_node_id


class LineageCycleError(LineageError):
    """A cycle was detected in the lineage graph."""

    def __init__(self, involved_nodes: list[str],
                 lineage_id: str = "") -> None:
        nodes = " → ".join(involved_nodes)
        super().__init__(
            message=f"Cycle detected in lineage graph: {nodes}",
            lineage_id=lineage_id,
            code="LINEAGE_CYCLE",
        )
        self.involved_nodes: list[str] = involved_nodes


class LineageIntegrityError(LineageError):
    """General lineage integrity violation (tampering / inconsistency)."""

    def __init__(self, message: str, lineage_id: str = "",
                 detail: str = "") -> None:
        super().__init__(
            message=message,
            lineage_id=lineage_id,
            code="LINEAGE_INTEGRITY",
        )
        self.detail: str = detail


class LineageBrokenLinkError(LineageError):
    """Two adjacent nodes exist but the expected edge is missing."""

    def __init__(self, from_node_id: str, to_node_id: str,
                 expected_edge_type: str = "",
                 lineage_id: str = "") -> None:
        super().__init__(
            message=(
                f"Broken lineage link: "
                f"from={from_node_id} to={to_node_id}"
                + (f" expected_type={expected_edge_type}"
                   if expected_edge_type else "")
            ),
            lineage_id=lineage_id,
            code="LINEAGE_BROKEN_LINK",
        )
        self.from_node_id: str = from_node_id
        self.to_node_id: str = to_node_id
        self.expected_edge_type: str = expected_edge_type


class LineageMissingEventError(LineageError):
    """An expected control event is missing from the audit chain."""

    def __init__(self, expected_event_type: str,
                 between_from: str = "", between_to: str = "",
                 lineage_id: str = "") -> None:
        msg = f"Missing control event: {expected_event_type}"
        if between_from and between_to:
            msg += f" (between {between_from} and {between_to})"
        super().__init__(
            message=msg,
            lineage_id=lineage_id,
            code="LINEAGE_MISSING_EVENT",
        )
        self.expected_event_type: str = expected_event_type
        self.between_from: str = between_from
        self.between_to: str = between_to


class LineageInconsistencyError(LineageError):
    """Lineage IDs differ where they must be identical."""

    def __init__(self, expected_lineage_id: str,
                 actual_lineage_id: str,
                 context: str = "") -> None:
        super().__init__(
            message=(
                f"Lineage mismatch: expected={expected_lineage_id}"
                f" actual={actual_lineage_id}"
                + (f" context={context}" if context else "")
            ),
            lineage_id=expected_lineage_id,
            code="LINEAGE_INCONSISTENCY",
        )
        self.expected_lineage_id: str = expected_lineage_id
        self.actual_lineage_id: str = actual_lineage_id
        self.context: str = context
