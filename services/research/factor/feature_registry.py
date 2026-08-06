"""Feature Registry — central schema registry for features.

Maintains schemas, metadata, and type information for all features
used across the factor research platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeatureSchema:
    """Schema definition for a feature."""

    name: str
    feature_type: str
    description: str = ""
    data_type: str = "float64"  # float64, int64, bool, string
    category: str = "technical"  # technical, fundamental, alternative
    source: str = ""  # market_data, fundamental_data, alternative_data
    frequency: str = "daily"  # daily, weekly, monthly, quarterly
    universe: str = "all"  # all, csi300, csi500, custom
    nullable: bool = True
    default_value: Any = None
    params: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "feature_type": self.feature_type,
            "description": self.description,
            "data_type": self.data_type,
            "category": self.category,
            "source": self.source,
            "frequency": self.frequency,
            "universe": self.universe,
            "nullable": self.nullable,
            "default_value": self.default_value,
            "params": self.params,
            "tags": self.tags,
            "owner": self.owner,
            "version": self.version,
        }


class FeatureRegistry:
    """Central schema registry for features.

    Maintains:
    * Feature schema definitions
    * Feature type metadata
    * Cross-feature relationships
    * Deprecation tracking
    """

    def __init__(self) -> None:
        self._schemas: Dict[str, FeatureSchema] = {}
        self._by_type: Dict[str, List[str]] = {}
        self._by_category: Dict[str, List[str]] = {}
        self._deprecated: Dict[str, str] = {}  # name → reason

    def register(self, schema: FeatureSchema) -> None:
        """Register a feature schema."""
        self._schemas[schema.name] = schema
        self._by_type.setdefault(schema.feature_type, []).append(schema.name)
        self._by_category.setdefault(schema.category, []).append(schema.name)
        logger.debug("Registered feature schema: %s", schema.name)

    def register_schema(
        self,
        name: str,
        feature_type: str,
        description: str = "",
        data_type: str = "float64",
        category: str = "technical",
        source: str = "",
        frequency: str = "daily",
        **kwargs,
    ) -> FeatureSchema:
        """Create and register a feature schema."""
        schema = FeatureSchema(
            name=name,
            feature_type=feature_type,
            description=description,
            data_type=data_type,
            category=category,
            source=source,
            frequency=frequency,
            **kwargs,
        )
        self.register(schema)
        return schema

    def get(self, name: str) -> Optional[FeatureSchema]:
        return self._schemas.get(name)

    def list_by_type(self, feature_type: str) -> List[str]:
        return self._by_type.get(feature_type, [])

    def list_by_category(self, category: str) -> List[str]:
        return self._by_category.get(category, [])

    def list_all(self) -> List[str]:
        return list(self._schemas.keys())

    def search(self, query: str) -> List[str]:
        query_lower = query.lower()
        results = []
        for name, schema in self._schemas.items():
            if (query_lower in name.lower() or
                query_lower in schema.description.lower() or
                any(query_lower in t.lower() for t in schema.tags)):
                results.append(name)
        return results

    def deprecate(self, name: str, reason: str = "") -> None:
        """Mark a feature schema as deprecated."""
        self._deprecated[name] = reason
        logger.info("Feature schema deprecated: %s (%s)", name, reason)

    def is_deprecated(self, name: str) -> bool:
        return name in self._deprecated

    def deprecation_reason(self, name: str) -> Optional[str]:
        return self._deprecated.get(name)

    def stats(self) -> Dict[str, Any]:
        return {
            "total_schemas": len(self._schemas),
            "by_type": {k: len(v) for k, v in self._by_type.items()},
            "by_category": {k: len(v) for k, v in self._by_category.items()},
            "deprecated": len(self._deprecated),
        }
