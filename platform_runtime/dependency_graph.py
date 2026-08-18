"""
ICYQuant Platform - Dependency Graph

Directed acyclic graph for module dependencies.
Supports topological sorting for startup ordering and cycle detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    OPTIONAL = "optional"


@dataclass
class DependencyNode:
    name: str
    module_type: str = "unknown"
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    level: int = 0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.module_type,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "level": self.level,
        }


class DependencyGraph:
    """
    Directed acyclic graph for module dependencies.

    Computes startup ordering via topological sort.
    Detects circular dependencies and reports them.
    """

    def __init__(self):
        self._nodes: Dict[str, DependencyNode] = {}
        self._dep_types: Dict[Tuple[str, str], DependencyType] = {}

    def add_node(
        self,
        name: str,
        module_type: str = "unknown",
        dependencies: Optional[List[str]] = None,
    ) -> DependencyNode:
        if name not in self._nodes:
            self._nodes[name] = DependencyNode(
                name=name,
                module_type=module_type,
                dependencies=[],
            )
        node = self._nodes[name]
        node.module_type = module_type
        if dependencies:
            for dep in dependencies:
                if dep not in node.dependencies:
                    node.dependencies.append(dep)
                self.add_edge(name, dep)
        return node

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        dep_type: DependencyType = DependencyType.HARD,
    ):
        if from_node not in self._nodes:
            self.add_node(from_node)
        if to_node not in self._nodes:
            self.add_node(to_node)

        if to_node not in self._nodes[from_node].dependencies:
            self._nodes[from_node].dependencies.append(to_node)
        if from_node not in self._nodes[to_node].dependents:
            self._nodes[to_node].dependents.append(from_node)

        self._dep_types[(from_node, to_node)] = dep_type

    def remove_node(self, name: str):
        if name in self._nodes:
            node = self._nodes[name]
            for dep in node.dependencies:
                if name in self._nodes.get(dep, DependencyNode(name)).dependents:
                    self._nodes[dep].dependents.remove(name)
            for dependent in node.dependents:
                if name in self._nodes.get(dependent, DependencyNode(name)).dependencies:
                    self._nodes[dependent].dependencies.remove(name)
            del self._nodes[name]

    def get_node(self, name: str) -> Optional[DependencyNode]:
        return self._nodes.get(name)

    def get_dependencies(self, name: str) -> List[str]:
        node = self._nodes.get(name)
        return node.dependencies if node else []

    def get_dependents(self, name: str) -> List[str]:
        node = self._nodes.get(name)
        return node.dependents if node else []

    def get_all_nodes(self) -> List[DependencyNode]:
        return list(self._nodes.values())

    def detect_cycles(self) -> List[List[str]]:
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node_name: str, path: List[str]):
            visited.add(node_name)
            rec_stack.add(node_name)
            path.append(node_name)

            node = self._nodes.get(node_name)
            if node:
                for dep in node.dependencies:
                    if dep not in visited:
                        dfs(dep, path)
                    elif dep in rec_stack:
                        cycle_start = path.index(dep)
                        cycles.append(path[cycle_start:] + [dep])

            path.pop()
            rec_stack.remove(node_name)

        for name in self._nodes:
            if name not in visited:
                dfs(name, [])

        return cycles

    def has_cycle(self) -> bool:
        return len(self.detect_cycles()) > 0

    def resolve_startup_order(self) -> List[str]:
        cycles = self.detect_cycles()
        if cycles:
            logger.warning(f"Circular dependencies detected: {cycles}")

        in_degree: Dict[str, int] = {}
        for name in self._nodes:
            in_degree[name] = len(self._nodes[name].dependencies)

        queue = [n for n, d in in_degree.items() if d == 0]
        order = []

        while queue:
            node_name = queue.pop(0)
            order.append(node_name)

            for dependent_name in self._nodes[node_name].dependents:
                in_degree[dependent_name] -= 1
                if in_degree[dependent_name] == 0:
                    queue.append(dependent_name)

        for name, node in self._nodes.items():
            node.level = self._compute_level(name, set())

        if len(order) < len(self._nodes):
            remaining = [n for n in self._nodes if n not in order]
            logger.warning(f"Unresolved nodes (possible cycle): {remaining}")
            order.extend(remaining)

        return order

    def _compute_level(self, name: str, visited: Set[str]) -> int:
        if name in visited:
            return 0
        visited.add(name)
        node = self._nodes.get(name)
        if not node or not node.dependencies:
            return 0
        return 1 + max(
            self._compute_level(dep, visited) for dep in node.dependencies
        )

    def get_startup_levels(self) -> Dict[int, List[str]]:
        order = self.resolve_startup_order()
        levels: Dict[int, List[str]] = {}
        for name in order:
            node = self._nodes.get(name)
            level = node.level if node else 0
            if level not in levels:
                levels[level] = []
            levels[level].append(name)
        return levels

    def get_dependency_tree(self, root: str) -> Dict:
        node = self._nodes.get(root)
        if not node:
            return {}
        visited = set()

        def build(name: str) -> Dict:
            if name in visited:
                return {"name": name, "circular": True}
            visited.add(name)
            n = self._nodes.get(name)
            if not n:
                return {"name": name}
            return {
                "name": name,
                "dependencies": [build(d) for d in n.dependencies],
            }

        return build(root)

    def to_dict(self) -> Dict:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "startupOrder": self.resolve_startup_order(),
            "cycles": self.detect_cycles(),
            "hasCycle": self.has_cycle(),
        }
