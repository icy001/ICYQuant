"""Relationship Manager – defines and manages financial relationship types."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RelationType(str, Enum):
    """Standard financial relationship types."""

    # Company/Supply Chain
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    PARTNER = "partner"
    PARENT = "parent"
    SUBSIDIARY = "subsidiary"

    # Portfolio/Holding
    HOLDING = "holding"
    BELONGS_TO = "belongs_to"
    OWNS = "owns"
    BENCHMARKS = "benchmarks"

    # Market/Index
    MEMBER_OF = "member_of"
    LISTED_ON = "listed_on"
    TRADES_IN = "trades_in"

    # Macro/Economic
    AFFECTS = "affects"
    DEPENDS_ON = "depends_on"
    CORRELATES_WITH = "correlates_with"
    CAUSES = "causes"
    INFLUENCES = "influences"

    # Factor
    EXPOSED_TO = "exposed_to"
    DRIVEN_BY = "driven_by"

    # Strategy
    GENERATED_BY = "generated_by"
    USES_MODEL = "uses_model"

    # Knowledge
    RELATED_TO = "related_to"
    MENTIONED_IN = "mentioned_in"


class RelationshipManager:
    """Creates and validates typed relationships between entities in the knowledge graph.

    Each relationship is (source, target, relation_type, weight).
    """

    def create(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        """Create a relationship record.

        Args:
            source: source entity id.
            target: target entity id.
            relation: relationship type string.
            weight: relationship strength (0-1 or >0).

        Returns:
            Dict with relationship details.
        """
        return {
            "source": source,
            "target": target,
            "relation": relation,
            "weight": weight,
        }

    def validate_relation(self, relation: str) -> bool:
        """Check if a relation string is a valid RelationType."""
        try:
            RelationType(relation)
            return True
        except ValueError:
            return False

    def is_transitive(self, relation: str) -> bool:
        """Return True if the relation is logically transitive (A→B and B→C implies A→C)."""
        transitive = {
            RelationType.SUPPLIER, RelationType.PARENT, RelationType.SUBSIDIARY,
            RelationType.MEMBER_OF, RelationType.BELONGS_TO, RelationType.CORRELATES_WITH,
        }
        try:
            rt = RelationType(relation)
            return rt in transitive
        except ValueError:
            return False

    def build_supply_chain(
        self,
        company_id: str,
        suppliers: List[str],
        customers: List[str],
    ) -> List[Dict[str, Any]]:
        """Build supply chain relations for a company."""
        relations = []
        for sid in suppliers:
            relations.append(self.create(sid, company_id, RelationType.SUPPLIER.value))
        for cid in customers:
            relations.append(self.create(company_id, cid, RelationType.SUPPLIER.value))
        return relations

    def build_index_membership(
        self,
        index_id: str,
        member_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Build index membership relations."""
        return [self.create(mid, index_id, RelationType.MEMBER_OF.value) for mid in member_ids]

    def build_factor_exposure(
        self,
        asset_id: str,
        factors: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Build factor exposure relations with beta weights."""
        return [
            self.create(asset_id, fid, RelationType.EXPOSED_TO.value, weight=beta)
            for fid, beta in factors.items()
        ]

    def build_causal_chain(
        self,
        nodes: List[str],
        relation: str = "causes",
    ) -> List[Dict[str, Any]]:
        """Build a causal chain A→B→C→..."""
        relations = []
        for i in range(len(nodes) - 1):
            relations.append(self.create(nodes[i], nodes[i + 1], relation))
        return relations
