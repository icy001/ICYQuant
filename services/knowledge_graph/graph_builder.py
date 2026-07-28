"""Graph Builder – constructs the financial knowledge graph from nodes and edges."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .entity import Entity


class GraphBuilder:
    """Constructs a directed, optionally weighted graph from entities and relationships.

    Attributes:
        nodes: entity_id → Entity mapping.
        edges: list of (source_id, target_id, relation, weight) tuples.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Entity] = {}
        self.edges: List[Tuple[str, str, str, float]] = []

    def add_node(self, entity: Entity) -> str:
        """Add a node. Returns the entity id."""
        self.nodes[entity.id] = entity
        return entity.id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
    ) -> Tuple[str, str, str, float]:
        """Add a directed, weighted edge from source to target.

        Args:
            source: source entity id.
            target: target entity id.
            relation: relationship type string.
            weight: edge weight (default 1.0).

        Returns:
            The edge tuple (source, target, relation, weight).
        """
        edge = (source, target, relation, weight)
        self.edges.append(edge)
        return edge

    def add_bidirectional_edge(
        self,
        entity_a: str,
        entity_b: str,
        relation: str,
        weight: float = 1.0,
    ) -> List[Tuple[str, str, str, float]]:
        """Add edges in both directions."""
        return [
            self.add_edge(entity_a, entity_b, relation, weight),
            self.add_edge(entity_b, entity_a, f"reverse_{relation}", weight),
        ]

    def remove_node(self, entity_id: str) -> Optional[Entity]:
        """Remove a node and all its incident edges."""
        entity = self.nodes.pop(entity_id, None)
        if entity:
            self.edges = [e for e in self.edges if e[0] != entity_id and e[1] != entity_id]
        return entity

    def remove_edge(self, source: str, target: str, relation: str) -> bool:
        """Remove the first matching edge. Returns True if found."""
        for i, e in enumerate(self.edges):
            if e[0] == source and e[1] == target and e[2] == relation:
                self.edges.pop(i)
                return True
        return False

    def get_neighbors(self, entity_id: str) -> List[Tuple[str, str, float]]:
        """Return outgoing edges (target, relation, weight) for a node."""
        return [(e[1], e[2], e[3]) for e in self.edges if e[0] == entity_id]

    def get_incoming(self, entity_id: str) -> List[Tuple[str, str, float]]:
        """Return incoming edges (source, relation, weight) for a node."""
        return [(e[0], e[2], e[3]) for e in self.edges if e[1] == entity_id]

    def get_all_relations(self, entity_id: str) -> List[Tuple[str, str, float]]:
        """Return all (outgoing + incoming) relations for a node."""
        return self.get_neighbors(entity_id) + self.get_incoming(entity_id)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def adjacency_list(self) -> Dict[str, List[Tuple[str, str, float]]]:
        """Return adjacency list representation."""
        adj: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        for src, tgt, rel, w in self.edges:
            adj[src].append((tgt, rel, w))
        return dict(adj)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph."""
        return {
            "nodes": {nid: e.to_dict() for nid, e in self.nodes.items()},
            "edges": [
                {"source": s, "target": t, "relation": r, "weight": w}
                for s, t, r, w in self.edges
            ],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }

    def subgraph(self, entity_ids: Set[str]) -> GraphBuilder:
        """Extract a subgraph containing only the given nodes and their edges."""
        sub = GraphBuilder()
        for eid in entity_ids:
            if eid in self.nodes:
                sub.add_node(self.nodes[eid])
        for s, t, r, w in self.edges:
            if s in entity_ids and t in entity_ids:
                sub.edges.append((s, t, r, w))
        return sub
