"""
Strategy Dependency — Inter-Strategy Dependency Graph

Models dependencies between strategies, such as:
- Signal dependency (Strategy B uses Strategy A's output)
- Execution dependency (Strategy B must execute after A)
- Capital dependency (Strategy B's allocation depends on A's performance)
- Risk dependency (Strategy B's risk is contingent on A's state)

Helps prevent circular dependencies and ensures orderly capital flow.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    SIGNAL = "SIGNAL"
    EXECUTION = "EXECUTION"
    CAPITAL = "CAPITAL"
    RISK = "RISK"
    DATA = "DATA"


@dataclass
class DependencyEdge:
    from_strategy: str
    to_strategy: str
    dep_type: DependencyType
    weight: float = 1.0
    critical: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyDependency:
    """
    Manages the inter-strategy dependency graph.

    Detects circular dependencies, computes execution order,
    and ensures capital changes propagate correctly through
    dependent strategies.
    """

    def __init__(
        self,
        dep_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.dep_id = dep_id or f"sd-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._edges: List[DependencyEdge] = []
        self._graph: Dict[str, List[str]] = {}      # from → [to]
        self._rev_graph: Dict[str, List[str]] = {}   # to → [from]

    def add_dependency(
        self,
        from_strategy: str,
        to_strategy: str,
        dep_type: DependencyType = DependencyType.CAPITAL,
        weight: float = 1.0,
        critical: bool = False,
    ) -> DependencyEdge:
        edge = DependencyEdge(
            from_strategy=from_strategy,
            to_strategy=to_strategy,
            dep_type=dep_type,
            weight=weight,
            critical=critical,
        )
        self._edges.append(edge)
        self._graph.setdefault(from_strategy, []).append(to_strategy)
        self._rev_graph.setdefault(to_strategy, []).append(from_strategy)
        return edge

    def get_dependents(self, strategy_id: str) -> List[str]:
        """Strategies that depend on this one."""
        return list(self._rev_graph.get(strategy_id, []))

    def get_dependencies(self, strategy_id: str) -> List[str]:
        """Strategies this one depends on."""
        return list(self._graph.get(strategy_id, []))

    def detect_cycles(self) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
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
                    cycle_start = path.index(neighbor)
                    cycles.append(list(path[cycle_start:]))
            path.pop()
            stack.discard(node)

        for node in self._graph:
            if node not in visited:
                dfs(node)
        return cycles

    def topological_order(self) -> List[str]:
        """Return strategies in dependency order (dependencies first)."""
        in_degree: Dict[str, int] = {}
        for s in self._graph:
            in_degree.setdefault(s, 0)
        for targets in self._graph.values():
            for t in targets:
                in_degree[t] = in_degree.get(t, 0) + 1

        queue = [s for s, d in in_degree.items() if d == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in self._graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def get_affected_by_capital_change(self, strategy_id: str) -> List[str]:
        """When a strategy's capital changes, which dependents are affected?"""
        affected = []
        for edge in self._edges:
            if edge.from_strategy == strategy_id and edge.dep_type in (DependencyType.CAPITAL, DependencyType.RISK):
                if edge.to_strategy not in affected:
                    affected.append(edge.to_strategy)
        return affected

    def get_summary(self) -> Dict[str, Any]:
        return {
            "dep_id": self.dep_id,
            "edge_count": len(self._edges),
            "node_count": len(set(list(self._graph.keys()) + list(self._rev_graph.keys()))),
            "cycles": self.detect_cycles(),
            "order": self.topological_order(),
        }
