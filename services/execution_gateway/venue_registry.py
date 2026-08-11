"""Venue Registry — Registration and management of execution venues.

Stores venue configurations including latency profiles, fee schedules,
and execution quality metrics. Provides venue lookup and filtering.

Venue Model::

    Venue(name, type, latency, fees, liquidity, quality, reliability)

Usage::

    registry = VenueRegistry()
    registry.register_venue(Venue("NYSE", ...))
    venues = registry.get_venues_for_symbol("AAPL")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VenueType(str, Enum):
    """Venue type classification."""

    EXCHANGE = "EXCHANGE"
    MTF = "MTF"  # Multilateral Trading Facility
    DARK_POOL = "DARK_POOL"
    SDP = "SDP"  # Systematic Internaliser
    OTC = "OTC"
    ECN = "ECN"  # Electronic Communication Network


class VenueStatus(str, Enum):
    """Venue operational status."""

    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class Venue:
    """Execution venue configuration.

    Represents a single execution venue with its characteristics
    and operational parameters.

    Attributes:
        name: Unique venue identifier
        venue_type: Venue type classification
        broker_name: Associated broker
        status: Current operational status
        avg_latency_ms: Average round-trip latency
        fee_bps: Trading fee in basis points
        liquidity_score: Aggregate liquidity quality (0-1)
        quality_score: Historical execution quality (0-1)
        reliability_score: Connection reliability (0-1)
        symbols: Supported symbols
        market_open: Market open time (HH:MM UTC)
        market_close: Market close time (HH:MM UTC)
        timezone: Venue timezone
        metadata: Additional venue metadata
        registered_at: Registration timestamp
    """

    name: str = ""
    venue_type: VenueType = VenueType.EXCHANGE
    broker_name: str = ""
    status: VenueStatus = VenueStatus.ACTIVE
    avg_latency_ms: float = 10.0
    fee_bps: float = 1.0
    liquidity_score: float = 0.7
    quality_score: float = 0.7
    reliability_score: float = 0.95
    symbols: list[str] = field(default_factory=list)
    market_open: str = "09:30"
    market_close: str = "16:00"
    timezone: str = "America/New_York"
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def supports_symbol(self, symbol: str) -> bool:
        """Check if venue supports a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            True if symbol is supported
        """
        if not self.symbols:
            return True  # All symbols if none specified
        return symbol.upper() in [s.upper() for s in self.symbols]

    def is_active(self) -> bool:
        """Check if venue is currently active.

        Returns:
            True if venue is ACTIVE
        """
        return self.status == VenueStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "venue_type": self.venue_type.value,
            "broker_name": self.broker_name,
            "status": self.status.value,
            "avg_latency_ms": self.avg_latency_ms,
            "fee_bps": self.fee_bps,
            "liquidity_score": self.liquidity_score,
            "quality_score": self.quality_score,
            "reliability_score": self.reliability_score,
            "symbols": self.symbols,
            "market_open": self.market_open,
            "market_close": self.market_close,
            "timezone": self.timezone,
        }


class VenueRegistry:
    """Execution venue registry and manager.

    Stores all registered venues and provides query capabilities
    for venue selection.

    Attributes:
        _venues: Venue name → Venue mapping
        _brokers: Set of registered broker names
        _symbol_index: Symbol → venue names index
    """

    def __init__(self) -> None:
        self._venues: dict[str, Venue] = {}
        self._brokers: set[str] = set()
        self._symbol_index: dict[str, list[str]] = {}

    # ── Registration ───────────────────────────────────────────────

    def register_venue(self, venue: Venue) -> bool:
        """Register a venue.

        Args:
            venue: Venue to register

        Returns:
            True if registered
        """
        self._venues[venue.name] = venue

        if venue.broker_name:
            self._brokers.add(venue.broker_name)

        # Index by symbol
        for symbol in venue.symbols:
            sym = symbol.upper()
            if sym not in self._symbol_index:
                self._symbol_index[sym] = []
            if venue.name not in self._symbol_index[sym]:
                self._symbol_index[sym].append(venue.name)

        logger.info("Venue registered: %s (type=%s)", venue.name, venue.venue_type.value)
        return True

    def register_defaults(self) -> None:
        """Register default venue configurations."""
        defaults = [
            Venue(
                name="NYSE_PRIMARY",
                venue_type=VenueType.EXCHANGE,
                broker_name="PRIMARY",
                avg_latency_ms=5.0,
                fee_bps=0.5,
                liquidity_score=0.9,
                quality_score=0.85,
                reliability_score=0.99,
                symbols=["*"],
            ),
            Venue(
                name="NASDAQ",
                venue_type=VenueType.EXCHANGE,
                broker_name="PRIMARY",
                avg_latency_ms=6.0,
                fee_bps=0.6,
                liquidity_score=0.88,
                quality_score=0.83,
                reliability_score=0.98,
                symbols=["*"],
            ),
            Venue(
                name="ARCA",
                venue_type=VenueType.ECN,
                broker_name="PRIMARY",
                avg_latency_ms=4.0,
                fee_bps=0.3,
                liquidity_score=0.75,
                quality_score=0.78,
                reliability_score=0.97,
                symbols=["*"],
            ),
            Venue(
                name="DARK_POOL_A",
                venue_type=VenueType.DARK_POOL,
                broker_name="DARK",
                avg_latency_ms=8.0,
                fee_bps=0.2,
                liquidity_score=0.60,
                quality_score=0.70,
                reliability_score=0.95,
                symbols=["*"],
            ),
        ]
        for venue in defaults:
            self.register_venue(venue)

    def register_broker(self, name: str) -> None:
        """Register a broker name.

        Args:
            name: Broker identifier
        """
        self._brokers.add(name)

    # ── Query ──────────────────────────────────────────────────────

    def get_venue(self, name: str) -> Optional[Venue]:
        """Get a venue by name.

        Args:
            name: Venue name

        Returns:
            Venue if found, None otherwise
        """
        return self._venues.get(name)

    def get_venues_for_symbol(self, symbol: str) -> list[Venue]:
        """Get active venues supporting a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of active Venue objects
        """
        sym = symbol.upper()
        venue_names = self._symbol_index.get(sym, [])

        if not venue_names:
            # If no specific index, return all active venues
            return [v for v in self._venues.values() if v.is_active()]

        return [
            self._venues[n] for n in venue_names
            if n in self._venues and self._venues[n].is_active()
        ]

    def get_active_venues(self) -> list[Venue]:
        """Get all active venues.

        Returns:
            List of active Venue objects
        """
        return [v for v in self._venues.values() if v.is_active()]

    def get_all_venues(self) -> list[Venue]:
        """Get all registered venues.

        Returns:
            List of all Venue objects
        """
        return list(self._venues.values())

    # ── Status Management ──────────────────────────────────────────

    def mark_degraded(self, venue_name: str) -> None:
        """Mark a venue as degraded.

        Args:
            venue_name: Venue to mark
        """
        venue = self._venues.get(venue_name)
        if venue:
            venue.status = VenueStatus.DEGRADED
            venue.reliability_score = max(0.1, venue.reliability_score - 0.2)
            logger.warning("Venue %s marked DEGRADED", venue_name)

    def mark_active(self, venue_name: str) -> None:
        """Mark a venue as active.

        Args:
            venue_name: Venue to mark
        """
        venue = self._venues.get(venue_name)
        if venue:
            venue.status = VenueStatus.ACTIVE
            venue.reliability_score = min(1.0, venue.reliability_score + 0.1)
            logger.info("Venue %s marked ACTIVE", venue_name)

    def update_latency(self, venue_name: str, latency_ms: float) -> None:
        """Update venue latency with exponential moving average.

        Args:
            venue_name: Venue to update
            latency_ms: Measured latency in ms
        """
        venue = self._venues.get(venue_name)
        if venue:
            alpha = 0.3
            venue.avg_latency_ms = (1 - alpha) * venue.avg_latency_ms + alpha * latency_ms

    # ── Properties ─────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Number of registered venues."""
        return len(self._venues)

    @property
    def brokers(self) -> list[str]:
        """List of registered brokers."""
        return list(self._brokers)

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "venues_count": len(self._venues),
            "active_count": len(self.get_active_venues()),
            "brokers": list(self._brokers),
            "venues": {n: v.to_dict() for n, v in self._venues.items()},
        }
