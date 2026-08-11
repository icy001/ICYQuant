"""
Signal Registry — Signal type and source registration.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Signal type registration (LONG, SHORT, FLAT variants)
    - Signal source registration (strategy → signal mapping)
    - Multi-version signal type support
    - Discovery of registered signal producers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SignalTypeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    EXPERIMENTAL = "EXPERIMENTAL"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SignalTypeInfo:
    """Metadata for a registered signal type."""
    type_name: str
    version: str = "1.0"
    description: str = ""
    direction: str = "LONG"
    status: SignalTypeStatus = SignalTypeStatus.ACTIVE
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)


@dataclass
class SignalSourceInfo:
    """Metadata for a signal-producing strategy or alpha."""
    source_id: str
    source_type: str  # "strategy", "alpha", "external"
    signal_types: List[str] = field(default_factory=list)
    description: str = ""
    status: SignalTypeStatus = SignalTypeStatus.ACTIVE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal Registry
# ---------------------------------------------------------------------------

class SignalRegistry:
    """Central registry for signal types and their producers.

    Supports:
        - Multi-version signal type coexistence
        - Source discovery for signal dispatch routing
        - Deprecation tracking
    """

    def __init__(self):
        self._signal_types: Dict[str, Dict[str, SignalTypeInfo]] = {}  # type_name → version → info
        self._sources: Dict[str, SignalSourceInfo] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        # Register built-in signal types
        self._register_builtin_types()
        self._initialized = True
        logger.info("SignalRegistry initialized with %d types, %d sources",
                     len(self._signal_types), len(self._sources))

    async def shutdown(self) -> None:
        self._signal_types.clear()
        self._sources.clear()
        self._initialized = False

    def _register_builtin_types(self) -> None:
        """Register the standard signal direction types."""
        builtins = [
            SignalTypeInfo(type_name="LONG", description="Long/buy signal"),
            SignalTypeInfo(type_name="SHORT", description="Short/sell signal"),
            SignalTypeInfo(type_name="FLAT", description="Close/flatten position"),
        ]
        for st in builtins:
            self._signal_types.setdefault(st.type_name, {})[st.version] = st

    # ------------------------------------------------------------------
    # Signal Type Management
    # ------------------------------------------------------------------

    def register_signal_type(self, info: SignalTypeInfo) -> None:
        """Register or update a signal type."""
        if info.type_name not in self._signal_types:
            self._signal_types[info.type_name] = {}
        self._signal_types[info.type_name][info.version] = info
        logger.info("Registered signal type: %s v%s", info.type_name, info.version)

    def get_signal_type(self, type_name: str, version: str = "1.0") -> Optional[SignalTypeInfo]:
        """Retrieve a signal type by name and version."""
        versions = self._signal_types.get(type_name, {})
        return versions.get(version)

    def list_signal_types(self, status: Optional[SignalTypeStatus] = None) -> List[SignalTypeInfo]:
        """List all signal types, optionally filtered by status."""
        result = []
        for versions in self._signal_types.values():
            for info in versions.values():
                if status is None or info.status == status:
                    result.append(info)
        return result

    def deprecate_signal_type(self, type_name: str, version: str = "1.0") -> None:
        """Mark a signal type as deprecated."""
        info = self.get_signal_type(type_name, version)
        if info:
            info.status = SignalTypeStatus.DEPRECATED
            logger.info("Deprecated signal type: %s v%s", type_name, version)

    # ------------------------------------------------------------------
    # Source Management
    # ------------------------------------------------------------------

    def register_source(self, info: SignalSourceInfo) -> None:
        """Register a signal-producing source."""
        self._sources[info.source_id] = info
        logger.info("Registered signal source: %s (type=%s)", info.source_id, info.source_type)

    def unregister_source(self, source_id: str) -> bool:
        """Remove a signal source."""
        if source_id in self._sources:
            del self._sources[source_id]
            logger.info("Unregistered signal source: %s", source_id)
            return True
        return False

    def get_source(self, source_id: str) -> Optional[SignalSourceInfo]:
        """Retrieve a signal source."""
        return self._sources.get(source_id)

    def list_sources(self, source_type: Optional[str] = None) -> List[SignalSourceInfo]:
        """List all sources, optionally filtered by type."""
        if source_type:
            return [s for s in self._sources.values() if s.source_type == source_type]
        return list(self._sources.values())

    def find_sources_for_signal_type(self, type_name: str) -> List[SignalSourceInfo]:
        """Find all sources that produce a given signal type."""
        return [s for s in self._sources.values() if type_name in s.signal_types]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def type_count(self) -> int:
        return sum(len(v) for v in self._signal_types.values())

    @property
    def source_count(self) -> int:
        return len(self._sources)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
