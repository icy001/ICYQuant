"""
DAG Builder — fluent API for constructing DAGs from workflow definitions.

Supports:
- Fluent API (method chaining)
- YAML / JSON deserialization
- Python DSL (reserved)

Usage:
    dag = (
        DAGBuilder("my_workflow")
            .node(entry_node)
            .node(process_node)
            .node(exit_node)
            .edge("entry", "process")
            .edge("process", "exit")
            .build()
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.workflow.dag.dag import DAG, DAGNode, DAGStatus
from services.workflow.dag.dependency_graph import DependencyGraph
from services.workflow.models.node import Node
from services.workflow.models.edge import Edge
from services.workflow.models.workflow import WorkflowDefinition

logger = logging.getLogger(__name__)


class DAGBuilder:
    """
    Fluent builder for constructing executable DAGs.

    Accumulates nodes and edges, then compiles into a validated DAG.
    """

    def __init__(self, workflow_id: str = "", name: str = ""):
        self._dag = DAG(workflow_id=workflow_id)
        self._name = name
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._metadata: Dict[str, Any] = {}

    def node(self, node: Node) -> "DAGBuilder":
        """Add a node to the DAG."""
        self._nodes[node.node_id] = node
        return self

    def nodes(self, *nodes: Node) -> "DAGBuilder":
        """Add multiple nodes."""
        for n in nodes:
            self._nodes[n.node_id] = n
        return self

    def edge(self, source_id: str, target_id: str, **kwargs) -> "DAGBuilder":
        """Add an edge from source to target."""
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            metadata=kwargs,
        )
        self._edges.append(edge)
        return self

    def edges(self, *edges: Edge) -> "DAGBuilder":
        """Add multiple edges."""
        self._edges.extend(edges)
        return self

    def metadata(self, **kwargs) -> "DAGBuilder":
        """Set DAG metadata."""
        self._metadata.update(kwargs)
        return self

    def from_workflow(self, wf: WorkflowDefinition) -> "DAGBuilder":
        """Build from a WorkflowDefinition."""
        self._dag.workflow_id = wf.workflow_id
        for node in wf.nodes:
            self._nodes[node.node_id] = node
        for edge in wf.edges:
            self._edges.append(edge)
        self._metadata.update(wf.metadata or {})
        return self

    def from_dict(self, data: Dict[str, Any]) -> "DAGBuilder":
        """Build from a dictionary representation."""
        self._dag.workflow_id = data.get("workflow_id", "")
        for node_data in data.get("nodes", []):
            node = Node.from_dict(node_data) if hasattr(Node, "from_dict") else Node(**node_data)
            self._nodes[node.node_id] = node
        for edge_data in data.get("edges", []):
            edge = Edge.from_dict(edge_data) if hasattr(Edge, "from_dict") else Edge(**edge_data)
            self._edges.append(edge)
        self._metadata.update(data.get("metadata", {}))
        return self

    def build(self) -> DAG:
        """
        Compile the accumulated nodes and edges into a DAG.

        Does NOT validate — use DAGCompiler for full compilation with validation.
        """
        for node in self._nodes.values():
            self._dag.add_node(node)

        for edge in self._edges:
            self._dag.add_edge(edge)

        self._dag.metadata.update(self._metadata)
        self._dag.status = DAGStatus.COMPILED
        return self._dag

    def to_dependency_graph(self) -> DependencyGraph:
        """Convert the builder state to a DependencyGraph."""
        graph = DependencyGraph(workflow_id=self._dag.workflow_id)
        for node in self._nodes.values():
            graph.add_node(node)
        for edge in self._edges:
            graph.add_edge(edge)
        return graph

    def reset(self) -> "DAGBuilder":
        """Reset builder state for reuse."""
        self._dag = DAG(workflow_id=self._dag.workflow_id)
        self._nodes.clear()
        self._edges.clear()
        self._metadata.clear()
        return self
