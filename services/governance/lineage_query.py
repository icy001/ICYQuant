"""
Lineage Query — structured query interface for lineage graphs.

Supports:
  - UPSTREAM / DOWNSTREAM / FULL direction filtering
  - Entity type, ID, correlation_id filtering
  - Time range, depth limiting
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .lineage_graph import LineageGraph
from .lineage_node import LineageNode, LineageNodeType


class QueryDirection(Enum):
    UPSTREAM = auto()
    DOWNSTREAM = auto()
    FULL = auto()


@dataclass
class LineageQuery:
    """Structured query for the lineage graph."""

    # Entity targeting
    entity_type: str = ""
    entity_id: str = ""
    node_id: str = ""
    correlation_id: str = ""

    # Direction
    direction: QueryDirection = QueryDirection.FULL

    # Filters
    node_types: Optional[List[LineageNodeType]] = None
    time_start: float = 0.0
    time_end: float = field(default_factory=time.time)

    # Limits
    max_depth: int = 20
    max_results: int = 1000

    def execute(self, graph: LineageGraph) -> List[LineageNode]:
        """Execute this query against a lineage graph."""
        # Resolve starting node(s)
        start_nodes: List[LineageNode] = []

        if self.node_id:
            node = graph.get_node(self.node_id)
            if node:
                start_nodes = [node]
        elif self.entity_type and self.entity_id:
            start_nodes = graph.get_nodes_by_entity(self.entity_type, self.entity_id)
        elif self.correlation_id:
            start_nodes = graph.get_nodes_by_correlation(self.correlation_id)
        else:
            return []

        if not start_nodes:
            return []

        # Collect results by direction
        all_results: Dict[str, LineageNode] = {}

        for node in start_nodes:
            if self.direction in (QueryDirection.UPSTREAM, QueryDirection.FULL):
                for n in graph.get_upstream(node.node_id, self.max_depth):
                    all_results[n.node_id] = n

            if self.direction == QueryDirection.FULL:
                all_results[node.node_id] = node

            if self.direction in (QueryDirection.DOWNSTREAM, QueryDirection.FULL):
                for n in graph.get_downstream(node.node_id, self.max_depth):
                    all_results[n.node_id] = n

        results = list(all_results.values())

        # Filter by node type
        if self.node_types:
            type_names = {t for t in self.node_types}
            results = [n for n in results if n.node_type in type_names]

        # Filter by time
        if self.time_start > 0:
            results = [n for n in results if n.timestamp >= self.time_start]
        results = [n for n in results if n.timestamp <= self.time_end]

        # Limit
        return results[:self.max_results]

    def execute_and_format(self, graph: LineageGraph) -> Dict[str, Any]:
        """Execute and format results."""
        nodes = self.execute(graph)
        return {
            "query": {
                "direction": self.direction.name,
                "entity_type": self.entity_type,
                "entity_id": self.entity_id,
                "correlation_id": self.correlation_id,
            },
            "results": [n.to_dict() for n in nodes],
            "count": len(nodes),
        }
