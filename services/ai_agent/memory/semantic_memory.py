"""
Semantic memory for structured knowledge representation.

Stores facts, concepts, and relationships in a structured graph format.
Provides concept retrieval and relationship traversal.

Responsibility: Structured knowledge and concept relationships.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Semantic Types ──


class RelationType(str, Enum):
    """Types of semantic relationships."""

    IS_A = "is_a"                   # Type hierarchy
    HAS_A = "has_a"                 # Composition
    PART_OF = "part_of"             # Membership
    RELATED_TO = "related_to"       # General association
    CAUSES = "causes"               # Causal relationship
    PRECEDES = "precedes"           # Temporal ordering
    EQUIVALENT_TO = "equivalent_to" # Equivalence
    CONTRADICTS = "contradicts"     # Contradiction
    DEPENDS_ON = "depends_on"       # Dependency


@dataclass
class SemanticNode:
    """A node in the semantic knowledge graph."""

    node_id: str = field(default_factory=lambda: uuid4().hex)
    concept: str = ""
    description: str = ""
    node_type: str = "concept"
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "node_id": self.node_id,
            "concept": self.concept,
            "node_type": self.node_type,
            "attributes_keys": list(self.attributes.keys()),
            "confidence": self.confidence,
        }


@dataclass
class SemanticEdge:
    """A directed edge connecting two semantic nodes."""

    edge_id: str = field(default_factory=lambda: uuid4().hex)
    source_id: str = ""
    target_id: str = ""
    relation: RelationType = RelationType.RELATED_TO
    weight: float = 1.0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary."""
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "weight": self.weight,
            "confidence": self.confidence,
        }


# ── Semantic Memory ──


class SemanticMemory:
    """Structured semantic knowledge graph.

    Stores concepts, facts, and relationships in a graph structure
    with typed relationships and confidence scoring.

    Usage:
        sm = SemanticMemory()
        apple = sm.add_concept("AAPL", node_type="stock", attributes={"sector": "Technology"})
        tech = sm.add_concept("Technology", node_type="sector")
        sm.add_relationship(apple.node_id, tech.node_id, RelationType.PART_OF)
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, SemanticNode] = {}
        self._edges: Dict[str, SemanticEdge] = {}
        self._adjacency: Dict[str, List[str]] = {}  # node_id → connected node_ids
        logger.info("SemanticMemory created")

    # ── Node Operations ──

    def add_concept(
        self,
        concept: str,
        node_type: str = "concept",
        description: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        **metadata: Any,
    ) -> SemanticNode:
        """Add a concept node.

        Args:
            concept: Concept name.
            node_type: Classification of the concept.
            description: Human-readable description.
            attributes: Key-value attributes.
            confidence: Confidence in this knowledge [0.0, 1.0].
            **metadata: Additional metadata.

        Returns:
            The created SemanticNode.
        """
        node = SemanticNode(
            concept=concept,
            node_type=node_type,
            description=description,
            attributes=attributes or {},
            confidence=confidence,
            metadata=dict(metadata),
        )
        self._nodes[node.node_id] = node
        self._adjacency.setdefault(node.node_id, [])
        logger.debug(f"Semantic node added: {concept} [{node.node_id}]")
        return node

    def get_node(self, node_id: str) -> Optional[SemanticNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def find_nodes(self, concept: str) -> List[SemanticNode]:
        """Find nodes by concept name."""
        return [n for n in self._nodes.values() if n.concept.lower() == concept.lower()]

    def search_nodes(self, query: str, limit: int = 10) -> List[SemanticNode]:
        """Search nodes by concept or description."""
        query_lower = query.lower()
        results = []
        for node in self._nodes.values():
            score = 0
            if query_lower in node.concept.lower():
                score += 2
            if query_lower in node.description.lower():
                score += 1
            if score > 0:
                results.append((score, node))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    def update_node(self, node_id: str, **updates: Any) -> bool:
        """Update node attributes."""
        node = self._nodes.get(node_id)
        if not node:
            return False
        for key, value in updates.items():
            if hasattr(node, key):
                setattr(node, key, value)
            else:
                node.attributes[key] = value
        node.updated_at = datetime.now(timezone.utc)
        return True

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        if node_id not in self._nodes:
            return False

        # Remove connected edges
        edges_to_remove = [
            eid for eid, edge in self._edges.items()
            if edge.source_id == node_id or edge.target_id == node_id
        ]
        for eid in edges_to_remove:
            del self._edges[eid]

        # Remove adjacency references
        for adj_list in self._adjacency.values():
            if node_id in adj_list:
                adj_list.remove(node_id)

        del self._nodes[node_id]
        del self._adjacency[node_id]
        return True

    # ── Relationship Operations ──

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType = RelationType.RELATED_TO,
        weight: float = 1.0,
        confidence: float = 1.0,
        **metadata: Any,
    ) -> Optional[SemanticEdge]:
        """Create a directed relationship between two nodes.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.
            relation: Type of relationship.
            weight: Edge weight.
            confidence: Confidence in the relationship.
            **metadata: Additional metadata.

        Returns:
            The created SemanticEdge, or None if nodes missing.
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            logger.warning(f"Cannot create edge: node not found ({source_id} → {target_id})")
            return None

        edge = SemanticEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            confidence=confidence,
            metadata=dict(metadata),
        )
        self._edges[edge.edge_id] = edge
        self._adjacency[source_id].append(target_id)
        logger.debug(f"Semantic edge added: {source_id} --[{relation.value}]--> {target_id}")
        return edge

    def get_relationships(self, node_id: str, direction: str = "out") -> List[SemanticEdge]:
        """Get relationships for a node.

        Args:
            node_id: The node to query.
            direction: "out" for outgoing, "in" for incoming, "both" for all.

        Returns:
            List of matching edges.
        """
        if direction == "out":
            return [e for e in self._edges.values() if e.source_id == node_id]
        elif direction == "in":
            return [e for e in self._edges.values() if e.target_id == node_id]
        else:
            return [
                e for e in self._edges.values()
                if e.source_id == node_id or e.target_id == node_id
            ]

    # ── Traversal ──

    def get_neighbors(self, node_id: str, max_distance: int = 1) -> List[SemanticNode]:
        """Get neighboring nodes up to a certain distance."""
        if max_distance < 1:
            return [self._nodes[node_id]] if node_id in self._nodes else []

        visited: set = {node_id}
        frontier: set = {node_id}
        result: List[SemanticNode] = []

        for _ in range(max_distance):
            next_frontier: set = set()
            for nid in frontier:
                for e in self.get_relationships(nid, direction="both"):
                    neighbor_id = e.target_id if e.source_id == nid else e.source_id
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.add(neighbor_id)
                        if neighbor_id in self._nodes:
                            result.append(self._nodes[neighbor_id])
            frontier = next_frontier

        return result

    # ── Status ──

    @property
    def node_count(self) -> int:
        """Total nodes in the graph."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Total edges in the graph."""
        return len(self._edges)

    def get_summary(self) -> Dict[str, Any]:
        """Get semantic memory summary."""
        type_counts: Dict[str, int] = {}
        for node in self._nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        relation_counts: Dict[str, int] = {}
        for edge in self._edges.values():
            rel = edge.relation.value
            relation_counts[rel] = relation_counts.get(rel, 0) + 1

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "by_type": type_counts,
            "by_relation": relation_counts,
        }
