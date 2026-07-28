"""Financial Entity Registry – unified node types for all market entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EntityType(str, Enum):
    """Standard financial entity types."""
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    SECTOR = "sector"
    COUNTRY = "country"
    CURRENCY = "currency"
    COMMODITY = "commodity"
    BOND = "bond"
    FACTOR = "factor"
    STRATEGY = "strategy"
    MACRO_EVENT = "macro_event"
    PORTFOLIO = "portfolio"
    EXCHANGE = "exchange"
    COMPANY = "company"
    NEWS_SOURCE = "news_source"


@dataclass
class Entity:
    """A node in the financial knowledge graph.

    Attributes:
        id: unique identifier (e.g. "NVDA", "US10Y", "Momentum").
        name: human-readable name (e.g. "NVIDIA Corp").
        entity_type: classification of this entity.
        ticker: optional trading ticker.
        sector: optional sector classification.
        country: optional country code.
        currency: optional currency code.
        metadata: arbitrary key-value data.
        created_at: creation timestamp.
    """

    id: str
    name: str
    entity_type: EntityType

    # Optional rich fields
    ticker: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_financial_instrument(self) -> bool:
        """Whether this entity is a tradable instrument."""
        return self.entity_type in (
            EntityType.STOCK, EntityType.ETF, EntityType.BOND,
            EntityType.COMMODITY, EntityType.CURRENCY,
        )

    @property
    def is_market_indicator(self) -> bool:
        """Whether this entity represents a market indicator."""
        return self.entity_type in (
            EntityType.INDEX, EntityType.SECTOR, EntityType.FACTOR,
            EntityType.MACRO_EVENT,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "ticker": self.ticker,
            "sector": self.sector,
            "country": self.country,
            "currency": self.currency,
            "metadata": self.metadata,
        }


class EntityRegistry:
    """Global financial entity registry.

    Maintains unique entity IDs and provides lookup, search, and validation.
    """

    def __init__(self) -> None:
        self._entities: Dict[str, Entity] = {}
        self._by_type: Dict[EntityType, List[str]] = {t: [] for t in EntityType}

    def register(self, entity: Entity) -> str:
        """Register an entity. Returns its id."""
        self._entities[entity.id] = entity
        self._by_type[entity.entity_type].append(entity.id)
        return entity.id

    def unregister(self, entity_id: str) -> Optional[Entity]:
        """Remove entity by id."""
        entity = self._entities.pop(entity_id, None)
        if entity:
            self._by_type[entity.entity_type].remove(entity_id)
        return entity

    def get(self, entity_id: str) -> Optional[Entity]:
        """Look up entity by id."""
        return self._entities.get(entity_id)

    def get_by_type(self, entity_type: EntityType) -> List[Entity]:
        """Return all entities of a given type."""
        return [self._entities[eid] for eid in self._by_type.get(entity_type, []) if eid in self._entities]

    def search(self, keyword: str) -> List[Entity]:
        """Case-insensitive search by id or name."""
        kw = keyword.lower()
        return [e for e in self._entities.values() if kw in e.id.lower() or kw in e.name.lower()]

    def exists(self, entity_id: str) -> bool:
        return entity_id in self._entities

    @property
    def entity_count(self) -> int:
        return len(self._entities)
