"""Market Data Adapter — connects the Scheduler to market data events.

The :class:`MarketDataAdapter` enables market-driven scheduling:
* Market open/close triggers
* Settlement event scheduling
* Daily batch job triggering
* Exchange calendar integration

Pipeline::

    Market Events ──→ MarketDataAdapter ──→ Scheduler
                          │
              Open / Close / Settlement / Holidays
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketEventType(enum.Enum):
    """Market event types that can trigger schedules."""

    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    PRE_OPEN = "pre_open"
    POST_CLOSE = "post_close"
    SETTLEMENT_START = "settlement_start"
    SETTLEMENT_END = "settlement_end"
    AUCTION_START = "auction_start"
    AUCTION_END = "auction_end"
    CIRCUIT_BREAKER = "circuit_breaker"
    HOLIDAY = "holiday"


class MarketDataAdapter:
    """Adapter for market data event integration.

    Responsibilities:
    * Subscribe to market events (open, close, settlement)
    * Trigger scheduled jobs on market events
    * Manage trading calendar awareness
    * Handle holiday and half-day schedules

    Usage::

        adapter = MarketDataAdapter()
        await adapter.connect()
        await adapter.on_market_open("daily_research_pipeline")
    """

    def __init__(self, market_data_service: Any = None) -> None:
        self._service = market_data_service
        self._lock = threading.Lock()
        self._connected = False
        self._event_handlers: Dict[MarketEventType, List[str]] = {et: [] for et in MarketEventType}
        self._event_count: int = 0
        self._last_event: Optional[Dict[str, Any]] = None
        self._markets: List[str] = ["SSE", "SZSE", "HKEX", "NYSE", "NASDAQ", "LSE"]

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def last_event(self) -> Optional[Dict[str, Any]]:
        return self._last_event

    @property
    def markets(self) -> List[str]:
        return list(self._markets)

    async def connect(self) -> None:
        logger.info("MarketDataAdapter: connecting")
        if self._service and hasattr(self._service, "connect"):
            await self._service.connect()
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        self._event_handlers = {et: [] for et in MarketEventType}
        logger.info("MarketDataAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        return {"connected": self._connected, "event_count": self._event_count}

    # ------------------------------------------------------------------
    # Event Registration
    # ------------------------------------------------------------------

    async def on_market_open(self, schedule_id: str, market: Optional[str] = None) -> Dict[str, Any]:
        """Trigger a schedule on market open."""
        self._event_handlers[MarketEventType.MARKET_OPEN].append(schedule_id)
        return {"schedule_id": schedule_id, "event": "market_open", "market": market or "all", "status": "registered"}

    async def on_market_close(self, schedule_id: str, market: Optional[str] = None) -> Dict[str, Any]:
        """Trigger a schedule on market close."""
        self._event_handlers[MarketEventType.MARKET_CLOSE].append(schedule_id)
        return {"schedule_id": schedule_id, "event": "market_close", "market": market or "all", "status": "registered"}

    async def on_settlement(self, schedule_id: str) -> Dict[str, Any]:
        """Trigger a schedule on settlement start."""
        self._event_handlers[MarketEventType.SETTLEMENT_START].append(schedule_id)
        return {"schedule_id": schedule_id, "event": "settlement_start", "status": "registered"}

    async def on_circuit_breaker(self, schedule_id: str) -> Dict[str, Any]:
        """Trigger a schedule on circuit breaker event."""
        self._event_handlers[MarketEventType.CIRCUIT_BREAKER].append(schedule_id)
        return {"schedule_id": schedule_id, "event": "circuit_breaker", "status": "registered"}

    # ------------------------------------------------------------------
    # Event Dispatch
    # ------------------------------------------------------------------

    async def dispatch_event(self, event_type: MarketEventType, market: str = "", details: Optional[Dict[str, Any]] = None) -> List[str]:
        """Dispatch a market event to registered schedules.

        Returns the list of schedule IDs that were triggered.
        """
        self._event_count += 1
        self._last_event = {
            "type": event_type.value, "market": market,
            "details": details or {}, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        schedules = self._event_handlers.get(event_type, [])
        logger.info("MarketDataAdapter: dispatched %s → %d schedules", event_type.value, len(schedules))
        return schedules

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    async def is_trading_day(self, market: str = "SSE", date: Optional[datetime] = None) -> bool:
        """Check if a given date is a trading day for the market."""
        # Stub: in production, queries the trading calendar
        return True

    async def next_trading_day(self, market: str = "SSE") -> datetime:
        """Get the next trading day."""
        return datetime.now(timezone.utc)

    def add_market(self, market: str) -> None:
        """Register a market for event tracking."""
        if market not in self._markets:
            self._markets.append(market)
