"""
Decision Registry
=================
Registry for decision types, sources, and model configurations
with versioning and discovery support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionTypeInfo:
    """Metadata for a registered decision type."""

    type_name: str
    category: str = "custom"
    description: str = ""
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionSourceInfo:
    """Metadata for a decision source (strategy, alpha, signal origin)."""

    source_id: str
    source_type: str = "strategy"
    description: str = ""
    enabled: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionRegistry:
    """
    Registry for decision types and sources.

    Supports:
    - Decision type registration with versioning
    - Source registration and discovery
    - Category-based lookup
    - Multi-version coexistence
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Type registry: type_name → list of versions
        self._decision_types: Dict[str, List[DecisionTypeInfo]] = {}

        # Source registry: source_id → DecisionSourceInfo
        self._sources: Dict[str, DecisionSourceInfo] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Register built-in decision types
        builtin_types = [
            ("entry", "sizing", "New position entry decision"),
            ("exit", "sizing", "Position exit / liquidation decision"),
            ("rebalance", "allocation", "Portfolio rebalancing decision"),
            ("hedge", "risk", "Hedging decision"),
            ("reduce", "sizing", "Position reduction decision"),
            ("increase", "sizing", "Position increase decision"),
        ]
        for name, cat, desc in builtin_types:
            self.register_type(name, category=cat, description=desc)

        self._initialized = True
        logger.info("DecisionRegistry initialized with %d built-in types", len(builtin_types))

    async def shutdown(self) -> None:
        self._decision_types.clear()
        self._sources.clear()
        self._initialized = False
        logger.info("DecisionRegistry shut down")

    # ------------------------------------------------------------------
    # Type Registration
    # ------------------------------------------------------------------

    def register_type(
        self,
        type_name: str,
        category: str = "custom",
        description: str = "",
        version: str = "1.0.0",
        **metadata: Any,
    ) -> DecisionTypeInfo:
        """Register a decision type."""
        info = DecisionTypeInfo(
            type_name=type_name,
            category=category,
            description=description,
            version=version,
            metadata=metadata,
        )

        if type_name not in self._decision_types:
            self._decision_types[type_name] = []
        self._decision_types[type_name].append(info)

        logger.debug("Decision type registered: %s v%s", type_name, version)
        return info

    def get_type(self, type_name: str, version: Optional[str] = None) -> Optional[DecisionTypeInfo]:
        """Get a decision type by name, optionally filtering by version."""
        versions = self._decision_types.get(type_name, [])
        if not versions:
            return None
        if version:
            for v in versions:
                if v.version == version:
                    return v
            return None
        return versions[-1]  # Latest version

    def list_types(self, category: Optional[str] = None) -> List[DecisionTypeInfo]:
        """List all registered decision types, optionally filtered by category."""
        result = []
        for versions in self._decision_types.values():
            latest = versions[-1]
            if category is None or latest.category == category:
                result.append(latest)
        return result

    def unregister_type(self, type_name: str, version: Optional[str] = None) -> bool:
        """Unregister a decision type."""
        if type_name not in self._decision_types:
            return False
        if version:
            self._decision_types[type_name] = [
                t for t in self._decision_types[type_name] if t.version != version
            ]
            if not self._decision_types[type_name]:
                del self._decision_types[type_name]
        else:
            del self._decision_types[type_name]
        return True

    # ------------------------------------------------------------------
    # Source Registration
    # ------------------------------------------------------------------

    def register_source(
        self,
        source_id: str,
        source_type: str = "strategy",
        description: str = "",
        **metadata: Any,
    ) -> DecisionSourceInfo:
        """Register a decision source."""
        info = DecisionSourceInfo(
            source_id=source_id,
            source_type=source_type,
            description=description,
            metadata=metadata,
        )
        self._sources[source_id] = info
        logger.debug("Decision source registered: %s (%s)", source_id, source_type)
        return info

    def get_source(self, source_id: str) -> Optional[DecisionSourceInfo]:
        return self._sources.get(source_id)

    def list_sources(self, source_type: Optional[str] = None) -> List[DecisionSourceInfo]:
        if source_type:
            return [s for s in self._sources.values() if s.source_type == source_type]
        return list(self._sources.values())

    def unregister_source(self, source_id: str) -> bool:
        if source_id in self._sources:
            del self._sources[source_id]
            return True
        return False

    def enable_source(self, source_id: str) -> bool:
        source = self._sources.get(source_id)
        if source:
            source.enabled = True
            return True
        return False

    def disable_source(self, source_id: str) -> bool:
        source = self._sources.get(source_id)
        if source:
            source.enabled = False
            return True
        return False

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def type_count(self) -> int:
        return sum(len(versions) for versions in self._decision_types.values())

    @property
    def source_count(self) -> int:
        return len(self._sources)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
