"""
Relation Engine.

Computes and analyzes entity relationships:
- Supplier-customer chains
- Technology dependencies
- Competition networks
- Cross-holding relationships
- Industry value chain mapping
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from services.knowledge.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, EdgeType, NodeType,
)

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class RelationType(str, Enum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    PARTNER = "partner"
    SUBSIDIARY = "subsidiary"
    PARENT = "parent"
    TECHNOLOGY_DEPENDENCY = "technology_dependency"
    SUPPLY_CHAIN = "supply_chain"
    CROSS_HOLDING = "cross_holding"
    JOINT_VENTURE = "joint_venture"
    REGULATORY = "regulatory"
    CORRELATED = "correlated"
    UNKNOWN = "unknown"


class RelationStrength(str, Enum):
    VERY_STRONG = "very_strong"  # > 0.8
    STRONG = "strong"            # 0.6 - 0.8
    MODERATE = "moderate"        # 0.4 - 0.6
    WEAK = "weak"                # 0.2 - 0.4
    VERY_WEAK = "very_weak"      # < 0.2


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class EntityRelation:
    """A computed relationship between two entities."""

    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_a: str = ""  # entity name or node ID
    entity_b: str = ""
    relation_type: RelationType = RelationType.UNKNOWN
    strength: RelationStrength = RelationStrength.MODERATE
    strength_score: float = 0.5  # 0-1

    # Directionality
    is_directed: bool = False
    direction: str = ""  # "A→B", "B→A", "bidirectional"

    # Evidence
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5

    # Graph references
    graph_node_a: Optional[str] = None
    graph_node_b: Optional[str] = None

    # Description
    description: str = ""

    # Timestamp
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "relation_type": self.relation_type.value,
            "strength": self.strength.value,
            "strength_score": self.strength_score,
            "is_directed": self.is_directed,
            "direction": self.direction,
            "confidence": self.confidence,
            "description": self.description,
        }


@dataclass
class RelationConfig:
    """Configuration for relation engine."""

    # Strength thresholds
    very_strong_threshold: float = 0.8
    strong_threshold: float = 0.6
    moderate_threshold: float = 0.4
    weak_threshold: float = 0.2

    # Computation
    max_relations_per_pair: int = 5
    max_path_depth: int = 4

    # Discovery
    enable_transitive_relations: bool = True
    min_transitive_confidence: float = 0.3


# ── Relation Engine ──────────────────────────────────────────────────────────

class RelationEngine:
    """
    Entity relationship computation engine.

    Analyzes relationships between entities in the knowledge graph,
    computes relationship strength, and discovers transitive relationships
    through supply chains and value networks.
    """

    # Type mapping: graph EdgeType → relation RelationType
    EDGE_TO_RELATION: Dict[EdgeType, RelationType] = {
        EdgeType.SUPPLIER_OF: RelationType.SUPPLIER,
        EdgeType.CUSTOMER_OF: RelationType.CUSTOMER,
        EdgeType.COMPETITOR_OF: RelationType.COMPETITOR,
        EdgeType.PARTNER_OF: RelationType.PARTNER,
        EdgeType.SUBSIDIARY_OF: RelationType.SUBSIDIARY,
        EdgeType.OWNS: RelationType.PARENT,
        EdgeType.DEPENDS_ON: RelationType.TECHNOLOGY_DEPENDENCY,
        EdgeType.SUPPLY_CHAIN: RelationType.SUPPLY_CHAIN,
        EdgeType.REGULATES: RelationType.REGULATORY,
        EdgeType.CORRELATED_WITH: RelationType.CORRELATED,
    }

    def __init__(
        self,
        config: Optional[RelationConfig] = None,
        graph: Optional[KnowledgeGraph] = None,
    ):
        self.config = config or RelationConfig()
        self.graph = graph or KnowledgeGraph()
        self._relations: List[EntityRelation] = []

    # ── Relation Computation ─────────────────────────────────────────────────

    def compute_relations(
        self, entity_a: str, entity_b: str
    ) -> List[EntityRelation]:
        """
        Compute all relationships between two entities.

        Args:
            entity_a: Name or node ID of first entity.
            entity_b: Name or node ID of second entity.

        Returns:
            List of relationships found.
        """
        node_a = self.graph.find_node(entity_a) or self.graph.get_node(entity_a)
        node_b = self.graph.find_node(entity_b) or self.graph.get_node(entity_b)

        if not node_a or not node_b:
            return []

        relations: List[EntityRelation] = []

        # Direct relations (edges between nodes)
        direct_edges = self.graph.get_edges_between(node_a.node_id, node_b.node_id)
        direct_edges += self.graph.get_edges_between(node_b.node_id, node_a.node_id)

        for edge in direct_edges:
            rel_type = self.EDGE_TO_RELATION.get(edge.edge_type, RelationType.UNKNOWN)
            relations.append(EntityRelation(
                entity_a=node_a.name,
                entity_b=node_b.name,
                relation_type=rel_type,
                strength=self._score_to_strength(edge.weight),
                strength_score=edge.weight,
                is_directed=True,
                direction=f"{node_a.name}→{node_b.name}" if edge.source_id == node_a.node_id else f"{node_b.name}→{node_a.name}",
                evidence=[edge.description] if edge.description else [],
                confidence=edge.confidence,
                graph_node_a=node_a.node_id,
                graph_node_b=node_b.node_id,
                description=edge.description,
            ))

        # Transitive relations (paths through intermediate nodes)
        if self.config.enable_transitive_relations and not relations:
            transitive = self._find_transitive_relations(node_a, node_b)
            relations.extend(transitive)

        self._relations.extend(relations)
        return relations

    def compute_all_for_entity(self, entity_name: str) -> List[EntityRelation]:
        """Compute relations from one entity to all connected entities."""
        node = self.graph.find_node(entity_name) or self.graph.get_node(entity_name)
        if not node:
            return []

        all_relations: List[EntityRelation] = []

        # Get all neighbors
        neighbors = self.graph.get_neighbors(node.node_id, direction="both")
        for neighbor_node, edge in neighbors:
            rel_type = self.EDGE_TO_RELATION.get(edge.edge_type, RelationType.UNKNOWN)
            all_relations.append(EntityRelation(
                entity_a=node.name,
                entity_b=neighbor_node.name,
                relation_type=rel_type,
                strength=self._score_to_strength(edge.weight),
                strength_score=edge.weight,
                is_directed=True,
                direction=f"{node.name}→{neighbor_node.name}" if edge.source_id == node.node_id else f"{neighbor_node.name}→{node.name}",
                evidence=[edge.description] if edge.description else [],
                confidence=edge.confidence,
                graph_node_a=node.node_id,
                graph_node_b=neighbor_node.node_id,
                description=edge.description,
            ))

        self._relations.extend(all_relations)
        return all_relations

    # ── Transitive Relations ─────────────────────────────────────────────────

    def _find_transitive_relations(
        self, node_a: GraphNode, node_b: GraphNode
    ) -> List[EntityRelation]:
        """Discover relations through intermediate nodes."""
        relations: List[EntityRelation] = []

        # Find paths between nodes
        paths = self.graph.find_paths(
            node_a.node_id, node_b.node_id, self.config.max_path_depth
        )

        if not paths:
            return relations

        for path in paths:
            if len(path) < 3:
                continue

            # Compute aggregate strength as product of edge weights (decays with depth)
            path_nodes = [self.graph.get_node(nid) for nid in path if self.graph.get_node(nid)]
            if not path_nodes:
                continue

            # Collect edge types along path
            edge_types = []
            total_weight = 1.0
            total_confidence = 1.0

            for i in range(len(path) - 1):
                edges = self.graph.get_edges_between(path[i], path[i + 1])
                if edges:
                    edge_types.append(edges[0].edge_type.value)
                    total_weight *= edges[0].weight
                    total_confidence *= edges[0].confidence

            # Decay by path length
            depth_penalty = 1.0 / (len(path) - 1)
            strength = total_weight * depth_penalty
            confidence = total_confidence * depth_penalty

            if confidence < self.config.min_transitive_confidence:
                continue

            # Determine most likely relation type from path
            dominant_type = max(set(edge_types), key=edge_types.count) if edge_types else "unknown"

            relations.append(EntityRelation(
                entity_a=node_a.name,
                entity_b=node_b.name,
                relation_type=RelationType.SUPPLY_CHAIN if "supply" in " ".join(edge_types) else RelationType.UNKNOWN,
                strength=self._score_to_strength(strength),
                strength_score=strength,
                is_directed=True,
                direction=" → ".join(n.name for n in path_nodes if n),
                evidence=[f"Path via: {' → '.join(n.name for n in path_nodes[1:-1] if n)}"],
                confidence=confidence,
                graph_node_a=node_a.node_id,
                graph_node_b=node_b.node_id,
                description=f"Transitive relation via {len(path)-2} intermediate nodes",
            ))

        return relations

    # ── Supply Chain Discovery ───────────────────────────────────────────────

    def discover_supply_chain(
        self, entity_name: str, max_depth: int = 3
    ) -> Dict[str, List[EntityRelation]]:
        """
        Discover the supply chain around an entity.

        Returns:
            Dict with "upstream" (suppliers) and "downstream" (customers).
        """
        node = self.graph.find_node(entity_name)
        if not node:
            return {"upstream": [], "downstream": []}

        result: Dict[str, List[EntityRelation]] = {
            "upstream": [],
            "downstream": [],
        }

        # Upstream: suppliers (incoming edges)
        bfs = self.graph.bfs(
            node.node_id, max_depth,
            [EdgeType.SUPPLIER_OF, EdgeType.SUPPLY_CHAIN, EdgeType.DEPENDS_ON],
            direction="incoming",
        )
        for depth, node_ids in bfs.items():
            if depth == 0:
                continue
            for nid in node_ids:
                n = self.graph.get_node(nid)
                if n:
                    result["upstream"].append(EntityRelation(
                        entity_a=node.name,
                        entity_b=n.name,
                        relation_type=RelationType.SUPPLIER,
                        strength=RelationStrength.WEAK if depth > 1 else RelationStrength.MODERATE,
                        strength_score=1.0 / depth,
                        direction=f"{n.name} → {node.name}",
                        description=f"Upstream supplier at depth {depth}",
                    ))

        # Downstream: customers (outgoing edges)
        bfs = self.graph.bfs(
            node.node_id, max_depth,
            [EdgeType.CUSTOMER_OF, EdgeType.SUPPLY_CHAIN],
            direction="outgoing",
        )
        for depth, node_ids in bfs.items():
            if depth == 0:
                continue
            for nid in node_ids:
                n = self.graph.get_node(nid)
                if n:
                    result["downstream"].append(EntityRelation(
                        entity_a=node.name,
                        entity_b=n.name,
                        relation_type=RelationType.CUSTOMER,
                        strength=RelationStrength.WEAK if depth > 1 else RelationStrength.MODERATE,
                        strength_score=1.0 / depth,
                        direction=f"{node.name} → {n.name}",
                        description=f"Downstream customer at depth {depth}",
                    ))

        return result

    # ── Competition Analysis ─────────────────────────────────────────────────

    def find_competitors(self, entity_name: str) -> List[EntityRelation]:
        """Find competitors of an entity."""
        node = self.graph.find_node(entity_name)
        if not node:
            return []

        competitors = []
        neighbors = self.graph.get_neighbors(
            node.node_id,
            edge_types=[EdgeType.COMPETITOR_OF],
            direction="both",
        )

        for neighbor_node, edge in neighbors:
            competitors.append(EntityRelation(
                entity_a=node.name,
                entity_b=neighbor_node.name,
                relation_type=RelationType.COMPETITOR,
                strength=self._score_to_strength(edge.weight),
                strength_score=edge.weight,
                confidence=edge.confidence,
                description=f"Competitor (same {node.sector or 'sector'})",
            ))

        return competitors

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _score_to_strength(self, score: float) -> RelationStrength:
        """Convert numeric score to RelationStrength."""
        if score >= self.config.very_strong_threshold:
            return RelationStrength.VERY_STRONG
        elif score >= self.config.strong_threshold:
            return RelationStrength.STRONG
        elif score >= self.config.moderate_threshold:
            return RelationStrength.MODERATE
        elif score >= self.config.weak_threshold:
            return RelationStrength.WEAK
        else:
            return RelationStrength.VERY_WEAK

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_relations(
        self,
        entity: Optional[str] = None,
        relation_type: Optional[RelationType] = None,
        min_strength: float = 0.0,
        limit: int = 100,
    ) -> List[EntityRelation]:
        """Query computed relations."""
        results = self._relations

        if entity:
            entity_lower = entity.lower()
            results = [
                r for r in results
                if entity_lower in r.entity_a.lower()
                or entity_lower in r.entity_b.lower()
            ]
        if relation_type:
            results = [r for r in results if r.relation_type == relation_type]
        if min_strength > 0:
            results = [r for r in results if r.strength_score >= min_strength]

        return results[-limit:]

    def get_strongest_relations(
        self, entity: str, limit: int = 10
    ) -> List[EntityRelation]:
        """Get strongest relations for an entity."""
        relations = self.get_relations(entity=entity)
        relations.sort(key=lambda r: r.strength_score, reverse=True)
        return relations[:limit]

    def clear(self) -> None:
        """Clear all computed relations."""
        self._relations.clear()
