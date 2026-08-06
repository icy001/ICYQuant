"""Experiment Lineage — tracks the provenance chain of research experiments.

Lineage captures the full ancestry of an experiment:
* Dataset → Factor → Model → Backtest → Report

Every result can be traced back to its origin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4


class LineageNodeType(str, Enum):
    """Types of nodes in an experiment lineage graph."""

    DATASET = "dataset"
    FACTOR = "factor"
    FEATURE = "feature"
    MODEL = "model"
    BACKTEST = "backtest"
    OPTIMIZATION = "optimization"
    PORTFOLIO = "portfolio"
    REPORT = "report"
    PUBLICATION = "publication"
    CUSTOM = "custom"


@dataclass
class LineageNode:
    """A node in the experiment lineage DAG.

    Each node represents a research artifact or processing step.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    node_type: LineageNodeType = LineageNodeType.CUSTOM
    name: str = ""
    description: str = ""
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"LineageNode({self.node_type.value}: {self.name})"

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class LineageEdge:
    """A directed edge connecting two lineage nodes.

    Represents a dependency: source → target.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    target_id: str = ""
    relationship: str = "derived_from"  # derived_from, depends_on, produces, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"LineageEdge({self.source_id[:8]} → {self.target_id[:8]})"


@dataclass
class ExperimentLineage:
    """Complete lineage DAG for an experiment.

    Tracks the full provenance chain:
        Dataset → Factor → Model → Backtest → Report

    Supports:
    * Adding nodes and edges
    * Querying ancestry and descendants
    * Serialization for persistence
    """

    experiment_id: str = ""
    nodes: Dict[str, LineageNode] = field(default_factory=dict)
    edges: List[LineageEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── node operations ───────────────────────────────────────────────────

    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.edges = [
                e for e in self.edges
                if e.source_id != node_id and e.target_id != node_id
            ]
            return True
        return False

    def find_nodes_by_type(self, node_type: LineageNodeType) -> List[LineageNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    # ── edge operations ───────────────────────────────────────────────────

    def add_edge(self, source_id: str, target_id: str, relationship: str = "derived_from") -> Optional[LineageEdge]:
        """Add a directed edge between two nodes."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
        edge = LineageEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
        )
        self.edges.append(edge)
        return edge

    def remove_edge(self, edge_id: str) -> bool:
        before = len(self.edges)
        self.edges = [e for e in self.edges if e.id != edge_id]
        return len(self.edges) < before

    # ── traversal ─────────────────────────────────────────────────────────

    def get_ancestors(self, node_id: str) -> List[LineageNode]:
        """Get all ancestor nodes (recursive upstream)."""
        ancestors: List[LineageNode] = []
        visited: Set[str] = set()
        self._traverse_upstream(node_id, visited, ancestors)
        return ancestors

    def get_descendants(self, node_id: str) -> List[LineageNode]:
        """Get all descendant nodes (recursive downstream)."""
        descendants: List[LineageNode] = []
        visited: Set[str] = set()
        self._traverse_downstream(node_id, visited, descendants)
        return descendants

    def get_direct_parents(self, node_id: str) -> List[LineageNode]:
        """Get immediate parent nodes."""
        parent_ids = {e.source_id for e in self.edges if e.target_id == node_id}
        return [self.nodes[pid] for pid in parent_ids if pid in self.nodes]

    def get_direct_children(self, node_id: str) -> List[LineageNode]:
        """Get immediate child nodes."""
        child_ids = {e.target_id for e in self.edges if e.source_id == node_id}
        return [self.nodes[cid] for cid in child_ids if cid in self.nodes]

    # ── lineage chain ─────────────────────────────────────────────────────

    def build_chain(self, start_node_id: str) -> List[LineageNode]:
        """Build the full chain from start node to root."""
        chain: List[LineageNode] = [self.nodes[start_node_id]]
        current = start_node_id
        while True:
            parents = self.get_direct_parents(current)
            if not parents:
                break
            chain.insert(0, parents[0])
            current = parents[0].id
        return chain

    # ── serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentLineage":
        lineage = cls(experiment_id=data.get("experiment_id", ""))
        for nd in data.get("nodes", []):
            node = LineageNode(
                id=nd["id"],
                node_type=LineageNodeType(nd["node_type"]),
                name=nd.get("name", ""),
                description=nd.get("description", ""),
                version=nd.get("version", "1.0"),
                metadata=nd.get("metadata", {}),
            )
            lineage.add_node(node)
        for ed in data.get("edges", []):
            lineage.edges.append(LineageEdge(
                id=ed.get("id", str(uuid4())),
                source_id=ed["source_id"],
                target_id=ed["target_id"],
                relationship=ed.get("relationship", "derived_from"),
                metadata=ed.get("metadata", {}),
            ))
        return lineage

    # ── internal ──────────────────────────────────────────────────────────

    def _traverse_upstream(self, node_id: str, visited: Set[str], result: List[LineageNode]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        for parent in self.get_direct_parents(node_id):
            result.append(parent)
            self._traverse_upstream(parent.id, visited, result)

    def _traverse_downstream(self, node_id: str, visited: Set[str], result: List[LineageNode]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        for child in self.get_direct_children(node_id):
            result.append(child)
            self._traverse_downstream(child.id, visited, result)

    # ── properties ────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def __repr__(self) -> str:
        return f"ExperimentLineage(exp={self.experiment_id[:8]}, nodes={self.node_count}, edges={self.edge_count})"
