"""Workflow definition model — the canonical, immutable workflow descriptor.

This module re-exports and extends the models-layer :class:`WorkflowDefinition`
with convenience factory methods for creating definitions from YAML, JSON,
and fluent builders.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models.node import NodeDefinition, NodeType, NodeConfig
from .models.edge import EdgeDefinition, EdgeType
from .models.metadata import WorkflowMetadata


class WorkflowStatus(str, enum.Enum):
    """Workflow lifecycle status."""

    DRAFT = "draft"
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    GRAYSCALE = "grayscale"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class WorkflowConfig:
    """Immutable workflow-level configuration."""

    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: Optional[float] = None
    parallel_node_limit: int = 10
    checkpoint_enabled: bool = True
    snapshot_on_complete: bool = True
    telemetry_enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable workflow definition — nodes, edges, metadata, and config.

    This is the canonical representation of a workflow. It is constructed via
    :class:`WorkflowBuilder` or deserialized from YAML/JSON.
    """

    name: str
    version: str
    nodes: List[NodeDefinition] = field(default_factory=list)
    edges: List[EdgeDefinition] = field(default_factory=list)
    config: WorkflowConfig = field(default_factory=WorkflowConfig)
    metadata: WorkflowMetadata = field(default_factory=WorkflowMetadata)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    registered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    owner: Optional[str] = None

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def entry_nodes(self) -> List[NodeDefinition]:
        """Return nodes with no incoming edges."""
        target_ids = {e.target_id for e in self.edges}
        return [n for n in self.nodes if n.node_id not in target_ids]

    @property
    def exit_nodes(self) -> List[NodeDefinition]:
        """Return nodes with no outgoing edges."""
        source_ids = {e.source_id for e in self.edges}
        return [n for n in self.nodes if n.node_id not in source_ids]

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[NodeDefinition]:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_outgoing_edges(self, node_id: str) -> List[EdgeDefinition]:
        return [e for e in self.edges if e.source_id == node_id]

    def get_incoming_edges(self, node_id: str) -> List[EdgeDefinition]:
        return [e for e in self.edges if e.target_id == node_id]

    def get_successors(self, node_id: str) -> List[str]:
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def get_predecessors(self, node_id: str) -> List[str]:
        return [e.source_id for e in self.edges if e.target_id == node_id]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "config": {
                "max_retries": self.config.max_retries,
                "retry_delay_seconds": self.config.retry_delay_seconds,
                "timeout_seconds": self.config.timeout_seconds,
                "parallel_node_limit": self.config.parallel_node_limit,
                "checkpoint_enabled": self.config.checkpoint_enabled,
                "snapshot_on_complete": self.config.snapshot_on_complete,
                "telemetry_enabled": self.config.telemetry_enabled,
                "labels": self.config.labels,
            },
            "metadata": self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else {},
            "status": self.status.value,
            "tags": self.tags,
            "owner": self.owner,
        }

    def __repr__(self) -> str:
        return (
            f"WorkflowDefinition(name={self.name!r}, version={self.version!r}, "
            f"nodes={self.node_count}, edges={self.edge_count}, status={self.status.value})"
        )
