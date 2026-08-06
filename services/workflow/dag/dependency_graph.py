"""
Dependency Graph — represents the dependency relationships between workflow nodes.

Provides the core data structure that the DAG compiler, scheduler, and executor
all operate upon.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from services.workflow.models.node import Node
from services.workflow.models.edge import Edge


class DependencyType(str):
    """Types of dependencies between nodes."""
    HARD = "hard"               # Must complete before successor starts
    SOFT = "soft"               # Preferred but not required
    DATA = "data"               # Data dependency (output of A is input to B)
    CONDITIONAL = "conditional" # Only if condition is met
    DYNAMIC = "dynamic"         # Resolved at runtime


@dataclass
class Dependency:
    """A single dependency between two nodes."""

    source_id: str
    target_id: str
    dep_type: str = DependencyType.HARD
    condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.dep_type))


@dataclass
class DependencyGraph:
    """
    Full dependency graph for a workflow.

    Tracks all nodes and their dependency relationships. Supports:
    - Single dependency (A → B)
    - Multi-dependency (A, B → C)
    - Conditional dependency (A → B if condition)
    - Dynamic dependency (resolved at runtime, reserved)
    """

    workflow_id: str
    nodes: Dict[str, Node] = field(default_factory=dict)
    dependencies: Dict[str, List[Dependency]] = field(default_factory=dict)
    reverse_dependencies: Dict[str, List[Dependency]] = field(default_factory=dict)
    indegree_map: Dict[str, int] = field(default_factory=dict)
    outdegree_map: Dict[str, int] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """Register a node in the dependency graph."""
        self.nodes[node.node_id] = node
        self.dependencies.setdefault(node.node_id, [])
        self.reverse_dependencies.setdefault(node.node_id, [])
        self.indegree_map.setdefault(node.node_id, 0)
        self.outdegree_map.setdefault(node.node_id, 0)

    def add_dependency(self, dep: Dependency) -> None:
        """Add a dependency between two nodes."""
        self.dependencies.setdefault(dep.source_id, []).append(dep)
        self.reverse_dependencies.setdefault(dep.target_id, []).append(dep)
        self.indegree_map[dep.target_id] = self.indegree_map.get(dep.target_id, 0) + 1
        self.outdegree_map[dep.source_id] = self.outdegree_map.get(dep.source_id, 0) + 1

    def add_edge(self, edge: Edge) -> None:
        """Add a dependency from a workflow Edge."""
        dep = Dependency(
            source_id=edge.source_id,
            target_id=edge.target_id,
            dep_type=DependencyType.HARD,
            metadata={"edge_id": edge.edge_id},
        )
        self.add_dependency(dep)

    def get_dependencies(self, node_id: str) -> List[Dependency]:
        """Get all dependencies for a node (nodes it depends on)."""
        return self.reverse_dependencies.get(node_id, [])

    def get_dependents(self, node_id: str) -> List[Dependency]:
        """Get all dependents of a node (nodes that depend on it)."""
        return self.dependencies.get(node_id, [])

    def get_indegree(self, node_id: str) -> int:
        return self.indegree_map.get(node_id, 0)

    def get_outdegree(self, node_id: str) -> int:
        return self.outdegree_map.get(node_id, 0)

    def is_ready(self, node_id: str, completed: Set[str]) -> bool:
        """Check if a node is ready to execute given the set of completed nodes."""
        deps = self.get_dependencies(node_id)
        return all(d.source_id in completed for d in deps)

    @property
    def source_nodes(self) -> List[str]:
        """Nodes with no dependencies (indegree == 0)."""
        return [nid for nid, deg in self.indegree_map.items() if deg == 0]

    @property
    def sink_nodes(self) -> List[str]:
        """Nodes with no dependents (outdegree == 0)."""
        return [nid for nid, deg in self.outdegree_map.items() if deg == 0]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def dependency_count(self) -> int:
        return sum(len(deps) for deps in self.dependencies.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "node_count": self.node_count,
            "dependency_count": self.dependency_count,
            "source_nodes": self.source_nodes,
            "sink_nodes": self.sink_nodes,
        }
