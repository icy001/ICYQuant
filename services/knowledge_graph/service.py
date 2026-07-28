"""Knowledge Graph Service – orchestrates the full knowledge graph pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .causal import CausalGraphEngine
from .entity import Entity, EntityRegistry
from .factor import FactorGraph
from .graph_builder import GraphBuilder
from .memory import GraphMemory
from .portfolio import PortfolioGraph
from .propagation import EventPropagationEngine
from .query import GraphQueryEngine
from .relationship import RelationshipManager


class KnowledgeGraphService:
    """Central service for the Institutional Knowledge Graph Engine.

    Orchestrates entity registration, graph construction, relationship
    management, query, event propagation, causal analysis, and versioning.
    """

    def __init__(
        self,
        builder: GraphBuilder,
        registry: Optional[EntityRegistry] = None,
        relationship_manager: Optional[RelationshipManager] = None,
        query_engine: Optional[GraphQueryEngine] = None,
        propagation: Optional[EventPropagationEngine] = None,
        causal: Optional[CausalGraphEngine] = None,
        factor_graph: Optional[FactorGraph] = None,
        portfolio_graph: Optional[PortfolioGraph] = None,
        memory: Optional[GraphMemory] = None,
    ) -> None:
        self.builder = builder
        self.registry = registry or EntityRegistry()
        self.relationships = relationship_manager or RelationshipManager()
        self.query_engine = query_engine or GraphQueryEngine()
        self.propagation = propagation or EventPropagationEngine()
        self.causal = causal or CausalGraphEngine()
        self.factor_graph = factor_graph or FactorGraph()
        self.portfolio_graph = portfolio_graph or PortfolioGraph()
        self.memory = memory or GraphMemory()

    def register(self, entity: Entity) -> str:
        """Register an entity and add it as a graph node.

        Args:
            entity: the Entity to register.

        Returns:
            The entity id.
        """
        self.registry.register(entity)
        self.builder.add_node(entity)
        self.memory.record_entity("create", entity.id)
        return entity.id

    def add_relation(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        """Add a relationship edge between two entities.

        Args:
            source: source entity id.
            target: target entity id.
            relation: relationship type.
            weight: edge weight.

        Returns:
            Relationship dict.
        """
        r = self.relationships.create(source, target, relation, weight)
        self.builder.add_edge(source, target, relation, weight)
        self.memory.record_relation("create", source, target, relation)
        return r

    def add_supply_chain(
        self,
        company_id: str,
        suppliers: List[str],
        customers: List[str],
    ) -> List[Dict[str, Any]]:
        """Build supply chain relations for a company."""
        relations = self.relationships.build_supply_chain(company_id, suppliers, customers)
        for r in relations:
            self.builder.add_edge(r["source"], r["target"], r["relation"], r["weight"])
            self.memory.record_relation("create", r["source"], r["target"], r["relation"])
        return relations

    def propagate_event(self, source: str, initial_impact: float = 1.0) -> Dict[str, Any]:
        """Propagate an event through the graph.

        Args:
            source: the source entity id.
            initial_impact: initial impact strength.

        Returns:
            Propagation result dict.
        """
        result = self.propagation.propagate_through_graph(
            self.builder, source, initial_impact
        )
        self.memory.record_event("propagation", {"source": source, "result": result})
        return result

    def causal_analysis(self, cause: str) -> Dict[str, Any]:
        """Analyze downstream effects of a causal event.

        Args:
            cause: cause entity id.

        Returns:
            Dict with downstream effects.
        """
        effects = self.causal.downstream_effects(cause)
        return {
            "cause": cause,
            "effects": effects,
            "effect_count": len(effects),
        }

    def query_neighbors(self, node: str) -> List[str]:
        """Get direct neighbors of a node."""
        return self.query_engine.neighbors(self.builder, node)

    def query_shortest_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find the shortest path between two entities."""
        return self.query_engine.shortest_path(self.builder, source, target)

    def save_snapshot(self) -> str:
        """Save the current graph state as a versioned snapshot."""
        return self.memory.save_snapshot(
            node_count=self.builder.node_count,
            edge_count=self.builder.edge_count,
            metadata={"timestamp": "snapshot"},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export the full graph as a dict."""
        return self.builder.to_dict()
