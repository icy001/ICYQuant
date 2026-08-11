"""
Lineage Tracker — data provenance tracking for the data lake,
capturing full data lineage from ingestion through transformation
to consumption.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LineageEventType(str, Enum):
    """Types of lineage events in the data lake."""
    INGESTION = "ingestion"
    TRANSFORMATION = "transformation"
    COMPACTION = "compaction"
    SNAPSHOT = "snapshot"
    QUERY = "query"
    DELETION = "deletion"
    EXPORT = "export"
    ARCHIVE = "archive"
    RESTORE = "restore"
    SCHEMA_EVOLUTION = "schema_evolution"
    PARTITION_EVOLUTION = "partition_evolution"


@dataclass
class LineageNode:
    """A node in the data lineage graph representing a dataset version."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dataset: str = ""
    version_id: str = ""
    event_type: LineageEventType = LineageEventType.INGESTION
    partition: str = ""
    file_count: int = 0
    row_count: int = 0
    byte_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""


@dataclass
class LineageEdge:
    """A directed edge in the data lineage graph."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    transformation: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataLineage:
    """Complete data lineage for a dataset."""
    dataset: str
    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def root_node(self) -> Optional[LineageNode]:
        """Get the root (first) node in the lineage."""
        return self.nodes[0] if self.nodes else None

    @property
    def latest_node(self) -> Optional[LineageNode]:
        """Get the latest node in the lineage."""
        return self.nodes[-1] if self.nodes else None

    @property
    def total_transformations(self) -> int:
        """Count of transformation edges."""
        return sum(
            1 for e in self.edges
            if e.transformation == LineageEventType.TRANSFORMATION.value
        )


class LineageTracker:
    """
    Tracks data lineage for the data lake.

    Captures the full lifecycle of data: ingestion → transformation
    → compaction → snapshot → deletion, with checksums for
    integrity verification.

    Features:
    - Directed acyclic graph (DAG) lineage model
    - Event-based lineage capture
    - Upstream/downstream dependency tracing
    - Lineage search and filtering
    - Impact analysis

    Usage::

        tracker = LineageTracker()
        await tracker.initialize()
        node = await tracker.record_event(
            dataset="us_equity_trades",
            version_id="v20240101",
            event_type=LineageEventType.INGESTION,
            row_count=5_000_000,
        )
    """

    def __init__(self, max_nodes_per_dataset: int = 10000) -> None:
        self.max_nodes_per_dataset = max_nodes_per_dataset
        self._lineages: dict[str, DataLineage] = {}
        self._nodes: dict[str, LineageNode] = {}
        self._edges: dict[str, LineageEdge] = {}

    async def initialize(self) -> None:
        """Initialize the lineage tracker."""
        logger.info("LineageTracker initialized.")

    async def stop(self) -> None:
        """Stop the lineage tracker."""
        self._lineages.clear()
        self._nodes.clear()
        self._edges.clear()
        logger.info("LineageTracker stopped.")

    # ---- Event Recording ----

    async def record_event(
        self,
        dataset: str,
        version_id: str,
        event_type: LineageEventType,
        *,
        partition: str = "",
        file_count: int = 0,
        row_count: int = 0,
        byte_count: int = 0,
        parent_node_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LineageNode:
        """Record a lineage event for a dataset."""
        node = LineageNode(
            dataset=dataset,
            version_id=version_id,
            event_type=event_type,
            partition=partition,
            file_count=file_count,
            row_count=row_count,
            byte_count=byte_count,
            metadata=metadata or {},
        )
        self._nodes[node.node_id] = node

        # Get or create lineage
        if dataset not in self._lineages:
            self._lineages[dataset] = DataLineage(dataset=dataset)
        lineage = self._lineages[dataset]

        # Enforce node limit
        if len(lineage.nodes) >= self.max_nodes_per_dataset:
            oldest = lineage.nodes.pop(0)
            self._nodes.pop(oldest.node_id, None)

        lineage.nodes.append(node)

        # Create edge from parent
        if parent_node_id and parent_node_id in self._nodes:
            edge = LineageEdge(
                source_node_id=parent_node_id,
                target_node_id=node.node_id,
                transformation=event_type.value,
            )
            self._edges[edge.edge_id] = edge
            lineage.edges.append(edge)

        lineage.updated_at = datetime.now(timezone.utc)

        logger.debug(
            "Lineage event: %s/%s [%s] rows=%d files=%d node=%s",
            dataset, event_type.value, version_id, row_count, file_count,
            node.node_id[:8],
        )
        return node

    # ---- Queries ----

    async def get_lineage(self, dataset: str) -> Optional[DataLineage]:
        """Get the complete lineage for a dataset."""
        return self._lineages.get(dataset)

    async def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Get a specific lineage node."""
        return self._nodes.get(node_id)

    async def get_edge(self, edge_id: str) -> Optional[LineageEdge]:
        """Get a specific lineage edge."""
        return self._edges.get(edge_id)

    async def get_upstream(
        self, node_id: str
    ) -> list[LineageNode]:
        """Get upstream (parent) nodes for a given node."""
        upstream = []
        for edge in self._edges.values():
            if edge.target_node_id == node_id:
                parent = self._nodes.get(edge.source_node_id)
                if parent:
                    upstream.append(parent)
        return upstream

    async def get_downstream(
        self, node_id: str
    ) -> list[LineageNode]:
        """Get downstream (child) nodes for a given node."""
        downstream = []
        for edge in self._edges.values():
            if edge.source_node_id == node_id:
                child = self._nodes.get(edge.target_node_id)
                if child:
                    downstream.append(child)
        return downstream

    async def get_ancestors(self, node_id: str) -> list[LineageNode]:
        """Get all ancestor nodes (recursive upstream)."""
        ancestors: list[LineageNode] = []
        visited: set[str] = set()

        def _walk(current_id: str) -> None:
            if current_id in visited:
                return
            visited.add(current_id)
            for edge in self._edges.values():
                if edge.target_node_id == current_id:
                    parent = self._nodes.get(edge.source_node_id)
                    if parent:
                        ancestors.append(parent)
                        _walk(parent.node_id)

        _walk(node_id)
        return ancestors

    async def get_descendants(self, node_id: str) -> list[LineageNode]:
        """Get all descendant nodes (recursive downstream)."""
        descendants: list[LineageNode] = []
        visited: set[str] = set()

        def _walk(current_id: str) -> None:
            if current_id in visited:
                return
            visited.add(current_id)
            for edge in self._edges.values():
                if edge.source_node_id == current_id:
                    child = self._nodes.get(edge.target_node_id)
                    if child:
                        descendants.append(child)
                        _walk(child.node_id)

        _walk(node_id)
        return descendants

    async def impact_analysis(
        self, node_id: str
    ) -> dict[str, Any]:
        """Analyze the impact of changes to a node (all descendants)."""
        descendants = await self.get_descendants(node_id)
        total_rows = sum(n.row_count for n in descendants)
        total_bytes = sum(n.byte_count for n in descendants)
        return {
            "node_id": node_id,
            "affected_datasets": list({n.dataset for n in descendants}),
            "affected_versions": [n.version_id for n in descendants],
            "total_descendants": len(descendants),
            "total_rows_affected": total_rows,
            "total_bytes_affected": total_bytes,
        }

    async def search(
        self,
        dataset: Optional[str] = None,
        event_type: Optional[LineageEventType] = None,
        since: Optional[datetime] = None,
    ) -> list[LineageNode]:
        """Search lineage nodes by criteria."""
        results: list[LineageNode] = []
        for node in self._nodes.values():
            if dataset and node.dataset != dataset:
                continue
            if event_type and node.event_type != event_type:
                continue
            if since and node.timestamp < since:
                continue
            results.append(node)
        return results

    async def get_summary(self) -> dict[str, Any]:
        """Get lineage tracker summary."""
        datasets = list(self._lineages.keys())
        event_type_counts: dict[str, int] = {}
        for node in self._nodes.values():
            et = node.event_type.value
            event_type_counts[et] = event_type_counts.get(et, 0) + 1

        return {
            "total_datasets": len(datasets),
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "event_type_distribution": event_type_counts,
            "datasets": datasets,
        }
