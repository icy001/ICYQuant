"""
Dependency Manager — Strategy dependency resolution and validation.

Manages inter-strategy dependencies, builds dependency graphs,
detects cycles, and validates dependency constraints.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DependencyStatus(str, Enum):
    """Dependency resolution status."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CYCLIC = "cyclic"
    CONFLICT = "conflict"
    MISSING = "missing"
    DEPRECATED = "deprecated"


@dataclass
class DependencyNode:
    """A node in the dependency graph."""
    strategy_id: str
    name: str = ""
    version: str = "0.1.0"
    dependencies: list[str] = field(default_factory=list)  # strategy_ids this depends on
    dependents: list[str] = field(default_factory=list)  # strategy_ids that depend on this
    status: DependencyStatus = DependencyStatus.RESOLVED
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraph:
    """Complete dependency graph for the platform."""
    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)
    cycles: list[list[str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


class DependencyManager:
    """
    Manages inter-strategy dependencies and resolution.

    Builds dependency graphs, detects cycles, validates constraints,
    and provides resolution ordering for deployment planning.

    Usage::

        dm = DependencyManager()
        await dm.initialize()
        await dm.add_node(DependencyNode(
            strategy_id="strat_001", name="Momentum",
            dependencies=["strat_002"],
        ))
        graph = await dm.build_graph()
        order = await dm.resolve_order(["strat_001"])
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._graph: Optional[DependencyGraph] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the dependency manager."""
        logger.info("DependencyManager initialized.")

    async def stop(self) -> None:
        """Stop the dependency manager."""
        logger.info("DependencyManager stopped.")

    # ---- Node Management ----

    async def add_node(self, node: DependencyNode) -> DependencyNode:
        """Add a dependency node."""
        async with self._lock:
            self._nodes[node.strategy_id] = node
            # Update dependents on dependency nodes
            for dep_id in node.dependencies:
                if dep_id in self._nodes:
                    dep_node = self._nodes[dep_id]
                    if node.strategy_id not in dep_node.dependents:
                        dep_node.dependents.append(node.strategy_id)

        logger.debug(f"Dependency node added: {node.strategy_id}")
        self._graph = None  # Invalidate cached graph
        return node

    async def remove_node(self, strategy_id: str) -> bool:
        """Remove a dependency node."""
        async with self._lock:
            node = self._nodes.pop(strategy_id, None)
            if not node:
                return False

            # Remove from dependents of dependencies
            for dep_id in node.dependencies:
                if dep_id in self._nodes:
                    dep_node = self._nodes[dep_id]
                    if strategy_id in dep_node.dependents:
                        dep_node.dependents.remove(strategy_id)

        self._graph = None
        return True

    async def add_dependency(self, strategy_id: str, depends_on: str) -> None:
        """Add a dependency relationship."""
        async with self._lock:
            node = self._nodes.get(strategy_id)
            if not node:
                raise ValueError(f"Node not found: {strategy_id}")

            if depends_on not in node.dependencies:
                node.dependencies.append(depends_on)

            dep_node = self._nodes.get(depends_on)
            if dep_node and strategy_id not in dep_node.dependents:
                dep_node.dependents.append(strategy_id)

        self._graph = None

    async def remove_dependency(self, strategy_id: str, depends_on: str) -> None:
        """Remove a dependency relationship."""
        async with self._lock:
            node = self._nodes.get(strategy_id)
            if node and depends_on in node.dependencies:
                node.dependencies.remove(depends_on)

            dep_node = self._nodes.get(depends_on)
            if dep_node and strategy_id in dep_node.dependents:
                dep_node.dependents.remove(strategy_id)

        self._graph = None

    # ---- Graph Analysis ----

    async def build_graph(self) -> DependencyGraph:
        """Build and cache the full dependency graph."""
        if self._graph:
            return self._graph

        graph = DependencyGraph(nodes=dict(self._nodes))
        cycles = self._detect_cycles()

        for node_id, node in self._nodes.items():
            for dep_id in node.dependencies:
                graph.edges.append((node_id, dep_id))
                if dep_id not in self._nodes:
                    node.status = DependencyStatus.MISSING
                    graph.unresolved.append(dep_id)

        graph.cycles = cycles
        for cycle in cycles:
            for node_id in cycle:
                if node_id in self._nodes:
                    self._nodes[node_id].status = DependencyStatus.CYCLIC

        self._graph = graph
        return graph

    async def resolve_order(self, strategy_ids: list[str]) -> list[str]:
        """Get topological sort of strategy deployment order."""
        # Build adjacency list
        in_degree: dict[str, int] = {}
        adj: dict[str, list[str]] = {}

        for sid in strategy_ids:
            if sid in self._nodes:
                in_degree.setdefault(sid, 0)
                for dep_id in self._nodes[sid].dependencies:
                    if dep_id in strategy_ids:
                        adj.setdefault(dep_id, []).append(sid)
                        in_degree[sid] = in_degree.get(sid, 0) + 1
                        in_degree.setdefault(dep_id, 0)

        # Kahn's algorithm
        queue = [sid for sid in strategy_ids if in_degree.get(sid, 0) == 0]
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] = in_degree.get(neighbor, 1) - 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Include any remaining nodes not in dependency chain
        for sid in strategy_ids:
            if sid not in result:
                result.append(sid)

        return result

    async def get_dependents(self, strategy_id: str) -> list[str]:
        """Get all strategies that depend on this one."""
        node = self._nodes.get(strategy_id)
        return node.dependents.copy() if node else []

    async def get_dependencies(self, strategy_id: str) -> list[str]:
        """Get all strategies this one depends on."""
        node = self._nodes.get(strategy_id)
        return node.dependencies.copy() if node else []

    async def validate_dependencies(self, strategy_id: str) -> list[str]:
        """Validate that all dependencies exist and have no cycles."""
        issues: list[str] = []
        node = self._nodes.get(strategy_id)
        if not node:
            return [f"Strategy not found: {strategy_id}"]

        for dep_id in node.dependencies:
            if dep_id not in self._nodes:
                issues.append(f"Missing dependency: {dep_id}")
            else:
                dep_node = self._nodes[dep_id]
                if dep_node.status == DependencyStatus.CYCLIC:
                    issues.append(f"Cyclic dependency detected involving: {dep_id}")

        return issues

    async def get_graph(self) -> Optional[DependencyGraph]:
        """Get the current dependency graph."""
        return self._graph or await self.build_graph()

    # ---- Internal ----

    def _detect_cycles(self) -> list[list[str]]:
        """Detect cycles in the dependency graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self._nodes}
        cycles: list[list[str]] = []

        def dfs(node_id: str, path: list[str]) -> None:
            color[node_id] = GRAY
            path.append(node_id)

            for dep_id in self._nodes[node_id].dependencies:
                if dep_id not in color:
                    continue
                if color[dep_id] == GRAY:
                    # Found cycle
                    cycle_start = path.index(dep_id)
                    cycles.append(path[cycle_start:])
                elif color[dep_id] == WHITE:
                    dfs(dep_id, path)

            path.pop()
            color[node_id] = BLACK

        for nid in list(self._nodes.keys()):
            if color.get(nid) == WHITE:
                dfs(nid, [])

        return cycles
