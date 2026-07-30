"""Feature DAG Engine.

Directed Acyclic Graph for feature computation dependencies.
Enables automatic topological ordering, incremental re-computation,
and parallel execution of independent feature nodes.

Usage::

    from services.feature_engineering import FeatureDAG, dag_node

    @dag_node(depends_on=["return"])
    def ema20(return_series):
        ...
"""

from __future__ import annotations

import functools
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, TypeVar

T = TypeVar("T")


class NodeState(str, Enum):
    """Execution state of a DAG node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    """A single node in the feature computation DAG.

    Each node represents one feature (or intermediate computation)
    with explicit upstream dependencies.
    """

    name: str
    func: Optional[Callable[..., Any]] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: NodeState = NodeState.PENDING
    cacheable: bool = True

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DAGNode):
            return False
        return self.name == other.name

    def __repr__(self) -> str:
        return f"DAGNode(name={self.name!r}, state={self.state.value})"


@dataclass
class DAGEdge:
    """Directed edge from source node to target node."""

    source: str
    target: str

    def __repr__(self) -> str:
        return f"DAGEdge({self.source} -> {self.target})"


def dag_node(
    depends_on: Optional[List[str]] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    cacheable: bool = True,
) -> Callable[[Callable[..., Any]], DAGNode]:
    """Decorator to register a function as a DAG node.

    Args:
        depends_on: List of upstream node names this node depends on.
        description: Human-readable description.
        tags: Optional tags for categorization.
        cacheable: Whether intermediate results should be cached.
    """
    def wrapper(func: Callable[..., Any]) -> DAGNode:
        node = DAGNode(
            name=func.__name__,
            func=func,
            description=description,
            tags=tags or [],
            cacheable=cacheable,
        )
        # Store dependencies on the node for later registration
        node.metadata["_depends_on"] = depends_on or []
        node.metadata["_is_decorated"] = True
        return node

    return wrapper


class FeatureDAG:
    """Directed Acyclic Graph engine for feature computation.

    Manages the dependency graph of all feature computations.
    Supports topological sort, parallel-ready node discovery,
    cycle detection, and sub-graph extraction.

    Example::

        dag = FeatureDAG()
        dag.add_node(DAGNode(name="raw_price", func=load_price))
        dag.add_node(DAGNode(name="return", func=calc_return))
        dag.add_edge("raw_price", "return")
        dag.add_edge("return", "ema20")

        order = dag.topological_order()
        # ["raw_price", "return", "ema20"]
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._nodes: Dict[str, DAGNode] = {}
        # _predecessors[n] = set of nodes that must run before n
        self._predecessors: Dict[str, Set[str]] = defaultdict(set)
        # _successors[n] = set of nodes that depend on n
        self._successors: Dict[str, Set[str]] = defaultdict(set)

    # ---- node management ----

    @property
    def nodes(self) -> Dict[str, DAGNode]:
        """All registered nodes keyed by name."""
        return self._nodes

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def add_node(self, node: DAGNode) -> None:
        """Register a node. If decorated, auto-wire declared dependencies."""
        if node.name in self._nodes:
            raise ValueError(f"Node '{node.name}' already exists in DAG '{self.name}'")
        self._nodes[node.name] = node
        self._predecessors.setdefault(node.name, set())
        self._successors.setdefault(node.name, set())

        # Auto-wire dependencies from @dag_node decorator
        deps: List[str] = node.metadata.get("_depends_on", [])
        for dep in deps:
            self.add_edge(dep, node.name)

    def remove_node(self, node_name: str) -> None:
        """Remove a node and all edges connected to it."""
        if node_name not in self._nodes:
            raise KeyError(f"Node '{node_name}' not found")
        # Remove incoming edges
        for pred in list(self._predecessors.get(node_name, set())):
            self._successors[pred].discard(node_name)
        # Remove outgoing edges
        for succ in list(self._successors.get(node_name, set())):
            self._predecessors[succ].discard(node_name)
        del self._predecessors[node_name]
        del self._successors[node_name]
        del self._nodes[node_name]

    def get_node(self, name: str) -> DAGNode:
        if name not in self._nodes:
            raise KeyError(f"Node '{name}' not found in DAG '{self.name}'")
        return self._nodes[name]

    # ---- edge management ----

    def add_edge(self, source: str, target: str) -> None:
        """Add a directed dependency: source must run before target."""
        if source == target:
            raise ValueError(f"Self-loop detected: {source} -> {target}")
        if source not in self._nodes:
            raise KeyError(f"Source node '{source}' not registered")
        if target not in self._nodes:
            raise KeyError(f"Target node '{target}' not registered")

        self._successors[source].add(target)
        self._predecessors[target].add(source)

        if self._has_cycle():
            self._successors[source].discard(target)
            self._predecessors[target].discard(source)
            raise ValueError(f"Adding edge {source} -> {target} would create a cycle")

    def remove_edge(self, source: str, target: str) -> None:
        self._successors[source].discard(target)
        self._predecessors[target].discard(source)

    # ---- traversal ----

    def predecessors(self, node_name: str) -> Set[str]:
        """Direct upstream dependencies."""
        return self._predecessors.get(node_name, set()).copy()

    def successors(self, node_name: str) -> Set[str]:
        """Direct downstream dependents."""
        return self._successors.get(node_name, set()).copy()

    def upstream(self, node_name: str, max_depth: int = -1) -> List[str]:
        """All ancestor nodes via BFS. max_depth=-1 means unlimited."""
        visited: Set[str] = set()
        result: List[str] = []
        queue: deque[Tuple[str, int]] = deque([(node_name, 0)])

        while queue:
            current, depth = queue.popleft()
            if max_depth >= 0 and depth >= max_depth:
                continue
            for pred in sorted(self._predecessors.get(current, set())):
                if pred not in visited:
                    visited.add(pred)
                    result.append(pred)
                    queue.append((pred, depth + 1))
        return result

    def downstream(self, node_name: str, max_depth: int = -1) -> List[str]:
        """All descendant nodes via BFS."""
        visited: Set[str] = set()
        result: List[str] = []
        queue: deque[Tuple[str, int]] = deque([(node_name, 0)])

        while queue:
            current, depth = queue.popleft()
            if max_depth >= 0 and depth >= max_depth:
                continue
            for succ in sorted(self._successors.get(current, set())):
                if succ not in visited:
                    visited.add(succ)
                    result.append(succ)
                    queue.append((succ, depth + 1))
        return result

    # ---- topological sort ----

    def topological_order(self) -> List[str]:
        """Kahn's algorithm: return nodes in dependency-safe execution order.

        Returns:
            List of node names in topological order.
        Raises:
            RuntimeError: If a cycle is detected (should not happen).
        """
        in_degree: Dict[str, int] = {
            name: len(preds) for name, preds in self._predecessors.items()
        }
        queue: deque[str] = deque(
            name for name, deg in in_degree.items() if deg == 0
        )
        result: List[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for succ in sorted(self._successors.get(node, set())):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(result) != len(self._nodes):
            raise RuntimeError(
                f"Cycle detected in DAG '{self.name}'. "
                f"Completed {len(result)}/{len(self._nodes)} nodes."
            )

        return result

    def execution_layers(self) -> List[List[str]]:
        """Group nodes into parallel-executable layers.

        Each layer contains nodes whose dependencies are all satisfied
        by previous layers — enabling parallel execution within a layer.
        """
        topo = self.topological_order()
        node_depths: Dict[str, int] = {}

        for node in topo:
            preds = self._predecessors.get(node, set())
            if not preds:
                node_depths[node] = 0
            else:
                node_depths[node] = 1 + max(node_depths[p] for p in preds)

        max_depth = max(node_depths.values()) if node_depths else 0
        layers: List[List[str]] = [[] for _ in range(max_depth + 1)]
        for node, depth in node_depths.items():
            layers[depth].append(node)

        return [layer for layer in layers if layer]

    # ---- ready nodes ----

    def ready_nodes(self) -> List[str]:
        """Nodes whose all predecessors are COMPLETED or SKIPPED."""
        ready: List[str] = []
        for name, node in self._nodes.items():
            if node.state not in (NodeState.PENDING, NodeState.READY):
                continue
            preds = self._predecessors.get(name, set())
            all_done = all(
                self._nodes[p].state in (NodeState.COMPLETED, NodeState.SKIPPED)
                for p in preds
            )
            if all_done:
                ready.append(name)
        return ready

    def reset(self) -> None:
        """Reset all nodes to PENDING state."""
        for node in self._nodes.values():
            node.state = NodeState.PENDING

    # ---- sub-graph ----

    def subgraph(self, node_names: List[str]) -> "FeatureDAG":
        """Extract a sub-DAG containing only the given nodes and their dependencies."""
        needed: Set[str] = set(node_names)
        # Collect all ancestors
        for name in list(needed):
            needed.update(self.upstream(name))

        sub = FeatureDAG(name=f"{self.name}_subgraph")
        for name in sorted(needed):
            if name in self._nodes:
                sub.add_node(self._nodes[name])
        for name in needed:
            for succ in self._successors.get(name, set()):
                if succ in needed:
                    sub._successors.setdefault(name, set()).add(succ)
                    sub._predecessors.setdefault(succ, set()).add(name)
        return sub

    # ---- cycle detection ----

    def _has_cycle(self) -> bool:
        """Check for cycles using DFS with three-color marking."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {name: WHITE for name in self._nodes}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for succ in self._successors.get(node, set()):
                if color[succ] == GRAY:
                    return True
                if color[succ] == WHITE and dfs(succ):
                    return True
            color[node] = BLACK
            return False

        return any(color[n] == WHITE and dfs(n) for n in self._nodes)

    # ---- repr ----

    def __repr__(self) -> str:
        return f"FeatureDAG(name={self.name!r}, nodes={self.node_count})"

    def summary(self) -> Dict[str, Any]:
        """Return a structural summary of the DAG."""
        roots = [n for n in self._nodes if not self._predecessors.get(n)]
        leaves = [
            n for n in self._nodes if not self._successors.get(n)
        ]
        return {
            "name": self.name,
            "total_nodes": self.node_count,
            "total_edges": sum(len(v) for v in self._successors.values()),
            "roots": roots,
            "leaves": leaves,
            "layers": len(self.execution_layers()),
            "topological_order": self.topological_order(),
        }
