"""
Strategy Dependency — Signal & Execution Dependency Graph

Models: Signal dependency (B uses A's output), Execution dependency
(B must execute after A), Capital dependency (B's allocation depends on A).
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DepType(str, Enum):
    SIGNAL = "SIGNAL"
    EXECUTION = "EXECUTION"
    CAPITAL = "CAPITAL"
    DATA = "DATA"


@dataclass
class Dependency:
    from_strategy: str
    to_strategy: str
    dep_type: DepType
    weight: float = 1.0


class StrategyDependency:
    """
    Manages inter-strategy dependency graph for portfolio orchestration.
    Detects circular dependencies; provides execution ordering.
    """

    def __init__(
        self,
        dep_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.dep_id = dep_id or f"sdep-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._graph: Dict[str, List[str]] = {}
        self._deps: List[Dependency] = []

    def add(self, from_s: str, to_s: str, dep_type: DepType = DepType.SIGNAL) -> Dependency:
        dep = Dependency(from_strategy=from_s, to_strategy=to_s, dep_type=dep_type)
        self._deps.append(dep)
        self._graph.setdefault(from_s, []).append(to_s)
        return dep

    def get_dependents(self, strategy_id: str) -> List[str]:
        return [d.to_strategy for d in self._deps if d.from_strategy == strategy_id]

    def get_dependencies(self, strategy_id: str) -> List[str]:
        return [d.from_strategy for d in self._deps if d.to_strategy == strategy_id]

    def detect_cycles(self) -> List[List[str]]:
        cycles = []
        visited: Set[str] = set()
        stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            stack.add(node)
            path.append(node)
            for neighbor in self._graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in stack:
                    idx = path.index(neighbor)
                    cycles.append(list(path[idx:]))
            path.pop()
            stack.discard(node)

        for node in self._graph:
            if node not in visited:
                dfs(node)
        return cycles

    def topological_order(self) -> List[str]:
        in_degree: Dict[str, int] = {}
        all_nodes = set(self._graph.keys())
        for targets in self._graph.values():
            all_nodes.update(targets)
        for n in all_nodes:
            in_degree[n] = in_degree.get(n, 0)
        for targets in self._graph.values():
            for t in targets:
                in_degree[t] = in_degree.get(t, 0) + 1

        queue = [n for n, d in in_degree.items() if d == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in self._graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        return order
