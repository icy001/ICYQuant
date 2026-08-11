"""
ICYQuant Knowledge Graph — entity relationship network for quantitative research.

Models relationships between market entities, research concepts, financial
instruments, economic indicators, and research artifacts as a graph for
traversal, reasoning, and discovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    INSTRUMENT = "instrument"          # Stock, bond, derivative
    EXCHANGE = "exchange"              # Trading venue
    SECTOR = "sector"                  # Industry sector
    INDICATOR = "indicator"            # Economic indicator
    CONCEPT = "concept"                # Research concept
    STRATEGY = "strategy"              # Trading strategy
    FACTOR = "factor"                  # Alpha/beta factor
    EVENT = "event"                    # Market event
    PERSON = "person"                  # Analyst, researcher
    ORGANIZATION = "organization"      # Company, institution
    REPORT = "report"                  # Research report
    DATASET = "dataset"                # Data source


class RelationType(str, Enum):
    BELONGS_TO = "belongs_to"
    CORRELATES_WITH = "correlates_with"
    CAUSES = "causes"
    INFLUENCES = "influences"
    COMPOSED_OF = "composed_of"
    REFERENCES = "references"
    DERIVED_FROM = "derived_from"
    PART_OF = "part_of"
    COMPETES_WITH = "competes_with"
    SUPPLIES = "supplies"


@dataclass
class Entity:
    """A node in the knowledge graph."""
    entity_id: str
    name: str
    entity_type: EntityType
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    """An edge in the knowledge graph."""
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    evidence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """Entity relationship network for quantitative research.

    Supports:
        - Entity registration with type classification
        - Relationship modeling with typed edges
        - Graph traversal (neighbors, paths)
        - Subgraph extraction by domain
        - Centrality and influence scoring
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []
        # Adjacency index for fast lookups
        self._outgoing: dict[str, list[Relation]] = {}
        self._incoming: dict[str, list[Relation]] = {}

    def add_entity(self, entity: Entity) -> str:
        """Register a new entity in the graph."""
        self._entities[entity.entity_id] = entity
        if entity.entity_id not in self._outgoing:
            self._outgoing[entity.entity_id] = []
        if entity.entity_id not in self._incoming:
            self._incoming[entity.entity_id] = []
        return entity.entity_id

    def add_relation(self, relation: Relation) -> None:
        """Add a typed relationship between two entities."""
        if relation.source_id not in self._entities:
            raise ValueError(f"Source entity {relation.source_id} not found")
        if relation.target_id not in self._entities:
            raise ValueError(f"Target entity {relation.target_id} not found")

        self._relations.append(relation)
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: Optional[list[RelationType]] = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get neighboring entities with relationship info."""
        results: list[dict[str, Any]] = []

        if direction in ("outgoing", "both"):
            for rel in self._outgoing.get(entity_id, []):
                if relation_types and rel.relation_type not in relation_types:
                    continue
                target = self._entities.get(rel.target_id)
                if target:
                    results.append({
                        "entity": {"id": target.entity_id, "name": target.name, "type": target.entity_type.value},
                        "relation": rel.relation_type.value,
                        "direction": "outgoing",
                        "weight": rel.weight,
                    })

        if direction in ("incoming", "both"):
            for rel in self._incoming.get(entity_id, []):
                if relation_types and rel.relation_type not in relation_types:
                    continue
                source = self._entities.get(rel.source_id)
                if source:
                    results.append({
                        "entity": {"id": source.entity_id, "name": source.name, "type": source.entity_type.value},
                        "relation": rel.relation_type.value,
                        "direction": "incoming",
                        "weight": rel.weight,
                    })

        return results

    def search_entities(
        self,
        query: str,
        entity_types: Optional[list[EntityType]] = None,
        limit: int = 20,
    ) -> list[Entity]:
        """Search entities by name or alias."""
        query_lower = query.lower()
        results: list[tuple[float, Entity]] = []

        for entity in self._entities.values():
            if entity_types and entity.entity_type not in entity_types:
                continue
            score = 0.0
            if query_lower == entity.name.lower():
                score = 1.0
            elif query_lower in entity.name.lower():
                score = 0.8
            elif any(query_lower in alias.lower() for alias in entity.aliases):
                score = 0.6
            if score > 0:
                results.append((score, entity))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in results[:limit]]

    def get_subgraph(
        self,
        entity_ids: list[str],
        max_depth: int = 2,
    ) -> dict[str, Any]:
        """Extract a subgraph around the given entities."""
        visited: set[str] = set(entity_ids)
        frontier = set(entity_ids)
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for depth in range(max_depth):
            next_frontier: set[str] = set()
            for eid in frontier:
                for rel in self._outgoing.get(eid, []):
                    edges.append({
                        "source": rel.source_id,
                        "target": rel.target_id,
                        "type": rel.relation_type.value,
                        "weight": rel.weight,
                    })
                    if rel.target_id not in visited:
                        visited.add(rel.target_id)
                        next_frontier.add(rel.target_id)
                for rel in self._incoming.get(eid, []):
                    edges.append({
                        "source": rel.source_id,
                        "target": rel.target_id,
                        "type": rel.relation_type.value,
                        "weight": rel.weight,
                    })
                    if rel.source_id not in visited:
                        visited.add(rel.source_id)
                        next_frontier.add(rel.source_id)
            frontier = next_frontier

        for eid in visited:
            entity = self._entities.get(eid)
            if entity:
                nodes.append({
                    "id": entity.entity_id,
                    "name": entity.name,
                    "type": entity.entity_type.value,
                })

        return {"nodes": nodes, "edges": edges}

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)
