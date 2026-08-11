"""
ICYQuant Data Lineage Service.

Commit 16 Part 1.5 — End-to-end data lineage tracking service.
Traces data provenance from source exchange through normalization,
streaming, and storage, providing impact analysis and audit capability.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LineageEventType(str, Enum):
    """Types of lineage events."""
    INGEST = "ingest"
    NORMALIZE = "normalize"
    TRANSFORM = "transform"
    PUBLISH = "publish"
    PERSIST = "persist"
    QUERY = "query"
    DERIVE = "derive"
    ARCHIVE = "archive"
    DELETE = "delete"


@dataclass
class LineageNode:
    """A node in the data lineage graph."""
    node_id: str = ""
    dataset_id: str = ""
    node_type: LineageEventType = LineageEventType.INGEST
    description: str = ""
    timestamp: Optional[datetime] = None
    input_datasets: list[str] = field(default_factory=list)
    output_datasets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    """An edge connecting two lineage nodes."""
    edge_id: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    edge_type: str = ""
    timestamp: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """The complete lineage graph for a dataset."""
    dataset_id: str = ""
    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ImpactAnalysis:
    """Result of upstream/downstream impact analysis."""
    dataset_id: str = ""
    analysis_type: str = "downstream"  # downstream or upstream
    impacted_datasets: list[str] = field(default_factory=list)
    impact_paths: list[list[str]] = field(default_factory=list)
    severity: str = "low"
    analyzed_at: Optional[datetime] = None


class LineageService:
    """End-to-end data lineage tracking service.

    Tracks data provenance:
      Exchange → Connectivity → Normalization → Streaming →
      Data Lake → Derived Datasets → Consumption

    Provides:
      - Lineage graph construction and query
      - Upstream/downstream impact analysis
      - Data provenance audit trail
      - Dataset dependency mapping
    """

    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}
        self._edges: dict[str, LineageEdge] = {}
        self._graphs: dict[str, LineageGraph] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Node & Edge Management
    # ------------------------------------------------------------------

    async def add_node(self, node: LineageNode) -> str:
        """Add a node to the lineage graph."""
        async with self._lock:
            if not node.node_id:
                node.node_id = str(uuid.uuid4())[:12]
            node.timestamp = node.timestamp or datetime.now(timezone.utc)
            self._nodes[node.node_id] = node

            # Build/update graph
            for ds_id in node.output_datasets:
                if ds_id not in self._graphs:
                    self._graphs[ds_id] = LineageGraph(dataset_id=ds_id, created_at=datetime.now(timezone.utc))
                graph = self._graphs[ds_id]
                if node not in graph.nodes:
                    graph.nodes.append(node)
                graph.updated_at = datetime.now(timezone.utc)

        logger.debug("Lineage node added: %s (%s → %s)",
                     node.node_id, node.input_datasets, node.output_datasets)
        return node.node_id

    async def add_edge(self, edge: LineageEdge) -> str:
        """Add an edge to the lineage graph."""
        async with self._lock:
            if not edge.edge_id:
                edge.edge_id = str(uuid.uuid4())[:12]
            edge.timestamp = edge.timestamp or datetime.now(timezone.utc)
            self._edges[edge.edge_id] = edge
        return edge.edge_id

    async def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Get a lineage node by ID."""
        return self._nodes.get(node_id)

    # ------------------------------------------------------------------
    # Graph Queries
    # ------------------------------------------------------------------

    async def get_graph(self, dataset_id: str) -> Optional[LineageGraph]:
        """Get the full lineage graph for a dataset."""
        return self._graphs.get(dataset_id)

    async def get_upstream(self, dataset_id: str, depth: int = 5) -> list[str]:
        """Get upstream datasets that feed into this dataset."""
        upstream: set[str] = set()
        current = {dataset_id}
        for _ in range(depth):
            next_level: set[str] = set()
            for node in self._nodes.values():
                if set(node.output_datasets) & current:
                    next_level.update(node.input_datasets)
            upstream.update(next_level)
            current = next_level
            if not current:
                break
        return list(upstream)

    async def get_downstream(self, dataset_id: str, depth: int = 5) -> list[str]:
        """Get downstream datasets derived from this dataset."""
        downstream: set[str] = set()
        current = {dataset_id}
        for _ in range(depth):
            next_level: set[str] = set()
            for node in self._nodes.values():
                if set(node.input_datasets) & current:
                    next_level.update(node.output_datasets)
            downstream.update(next_level)
            current = next_level
            if not current:
                break
        return list(downstream)

    async def impact_analysis(self, dataset_id: str, analysis_type: str = "downstream") -> ImpactAnalysis:
        """Run impact analysis for upstream or downstream."""
        start = datetime.now(timezone.utc)
        if analysis_type == "downstream":
            impacted = await self.get_downstream(dataset_id)
        else:
            impacted = await self.get_upstream(dataset_id)

        severity = "critical" if len(impacted) > 20 else ("high" if len(impacted) > 10 else "low")
        return ImpactAnalysis(
            dataset_id=dataset_id,
            analysis_type=analysis_type,
            impacted_datasets=impacted,
            severity=severity,
            analyzed_at=start,
        )

    # ------------------------------------------------------------------
    # Lineage Tracing
    # ------------------------------------------------------------------

    async def trace_record(
        self, record_id: str, source_exchange: str, instrument_id: str,
        dataset_id: str,
    ) -> str:
        """Trace a data record through the pipeline."""
        node = LineageNode(
            node_type=LineageEventType.INGEST,
            description=f"Record {record_id} from {source_exchange}",
            input_datasets=[source_exchange],
            output_datasets=[dataset_id],
            metadata={"record_id": record_id, "instrument_id": instrument_id, "source": source_exchange},
        )
        return await self.add_node(node)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def graph_count(self) -> int:
        return len(self._graphs)
