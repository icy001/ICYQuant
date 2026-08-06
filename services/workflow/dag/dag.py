"""
DAG (Directed Acyclic Graph) — the core graph structure for workflow execution.

Represents a compiled, validated, executable DAG built from a Workflow Definition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from services.workflow.models.node import Node
from services.workflow.models.edge import Edge


class DAGStatus(str, Enum):
    """DAG lifecycle status."""
    CREATED = "created"
    COMPILED = "compiled"
    VALIDATED = "validated"
    OPTIMIZED = "optimized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DAGNode:
    """A node within the DAG, wrapping the workflow Node with execution metadata."""

    node_id: str
    node: Node
    indegree: int = 0
    outdegree: int = 0
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    stage: int = 0
    critical_path_weight: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_source(self) -> bool:
        return self.indegree == 0

    @property
    def is_sink(self) -> bool:
        return self.outdegree == 0


@dataclass
class DAG:
    """
    The compiled Directed Acyclic Graph for workflow execution.

    Attributes:
        dag_id: Unique identifier for this DAG instance.
        workflow_id: The source workflow definition ID.
        nodes: Map of node_id -> DAGNode.
        edges: List of all edges in the DAG.
        adjacency: Adjacency list (node_id -> set of successor node_ids).
        reverse_adjacency: Reverse adjacency (node_id -> set of predecessor node_ids).
        stages: Execution stages (topological levels).
        status: Current DAG status.
        metadata: Arbitrary metadata.
    """

    dag_id: str = field(default_factory=lambda: f"dag_{uuid.uuid4().hex[:12]}")
    workflow_id: str = ""
    nodes: Dict[str, DAGNode] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    adjacency: Dict[str, Set[str]] = field(default_factory=dict)
    reverse_adjacency: Dict[str, Set[str]] = field(default_factory=dict)
    stages: List[List[str]] = field(default_factory=list)
    status: DAGStatus = DAGStatus.CREATED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> DAGNode:
        """Add a workflow node to the DAG."""
        dag_node = DAGNode(node_id=node.node_id, node=node)
        self.nodes[node.node_id] = dag_node
        self.adjacency.setdefault(node.node_id, set())
        self.reverse_adjacency.setdefault(node.node_id, set())
        return dag_node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge between two nodes in the DAG."""
        self.edges.append(edge)
        self.adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
        self.reverse_adjacency.setdefault(edge.target_id, set()).add(edge.source_id)

        if edge.source_id in self.nodes:
            self.nodes[edge.source_id].outdegree += 1
            self.nodes[edge.source_id].dependents.add(edge.target_id)
        if edge.target_id in self.nodes:
            self.nodes[edge.target_id].indegree += 1
            self.nodes[edge.target_id].dependencies.add(edge.source_id)

    def get_node(self, node_id: str) -> Optional[DAGNode]:
        return self.nodes.get(node_id)

    def get_successors(self, node_id: str) -> Set[str]:
        return self.adjacency.get(node_id, set())

    def get_predecessors(self, node_id: str) -> Set[str]:
        return self.reverse_adjacency.get(node_id, set())

    def get_source_nodes(self) -> List[DAGNode]:
        """Return all source nodes (indegree == 0)."""
        return [n for n in self.nodes.values() if n.is_source]

    def get_sink_nodes(self) -> List[DAGNode]:
        """Return all sink nodes (outdegree == 0)."""
        return [n for n in self.nodes.values() if n.is_sink]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dag_id": self.dag_id,
            "workflow_id": self.workflow_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "stages": self.stages,
            "status": self.status.value,
            "metadata": self.metadata,
        }
