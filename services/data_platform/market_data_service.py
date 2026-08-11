"""
ICYQuant Market Data Service.

Commit 16 Part 1.5 — Unified service for real-time market data access.
Combines connectivity and normalization to deliver canonical market data
to all downstream consumers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class SubscriptionMode(str, Enum):
    """Market data subscription mode."""
    SNAPSHOT = "snapshot"
    STREAMING = "streaming"
    SNAPSHOT_THEN_STREAMING = "snapshot_then_streaming"


@dataclass
class MarketDataSubscription:
    """A market data subscription."""
    subscription_id: str = ""
    instruments: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    mode: SubscriptionMode = SubscriptionMode.STREAMING
    created_at: Optional[datetime] = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketDataSnapshot:
    """A snapshot of current market data."""
    instrument_id: str = ""
    timestamp: int = 0
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    exchange_id: str = ""
    asset_class: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MarketDataService:
    """Unified market data service.

    Provides:
      - Real-time market data subscriptions
      - Current market snapshots
      - Multi-instrument batch queries
      - Symbol resolution and mapping
    """

    def __init__(
        self,
        connectivity: Any = None,
        normalization: Any = None,
    ) -> None:
        self._connectivity = connectivity
        self._normalization = normalization
        self._subscriptions: dict[str, MarketDataSubscription] = {}
        self._snapshots: dict[str, MarketDataSnapshot] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        instruments: list[str],
        fields: Optional[list[str]] = None,
        mode: SubscriptionMode = SubscriptionMode.STREAMING,
    ) -> MarketDataSubscription:
        """Create a market data subscription."""
        sub = MarketDataSubscription(
            subscription_id=f"md-{len(self._subscriptions):08d}",
            instruments=instruments,
            fields=fields or [],
            mode=mode,
            created_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._subscriptions[sub.subscription_id] = sub
        logger.info("MarketData subscription created: %s for %d instruments",
                    sub.subscription_id, len(instruments))
        return sub

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel a market data subscription."""
        async with self._lock:
            sub = self._subscriptions.pop(subscription_id, None)
            if sub:
                sub.active = False
                return True
            return False

    async def get_subscription(self, subscription_id: str) -> Optional[MarketDataSubscription]:
        """Get subscription details."""
        return self._subscriptions.get(subscription_id)

    # ------------------------------------------------------------------
    # Market Data Access
    # ------------------------------------------------------------------

    async def get_snapshot(self, instrument_id: str) -> Optional[MarketDataSnapshot]:
        """Get the latest market data snapshot for an instrument."""
        return self._snapshots.get(instrument_id)

    async def get_snapshots(self, instruments: list[str]) -> dict[str, Optional[MarketDataSnapshot]]:
        """Get snapshots for multiple instruments."""
        return {inst: self._snapshots.get(inst) for inst in instruments}

    async def stream(
        self, subscription_id: str,
    ) -> AsyncIterator[MarketDataSnapshot]:
        """Stream real-time market data for a subscription."""
        sub = self._subscriptions.get(subscription_id)
        if not sub or not sub.active:
            return

        if self._connectivity:
            for inst in sub.instruments:
                async for raw in self._connectivity.subscribe_market_data("", [inst]):
                    if self._normalization:
                        result = await self._normalization.normalize([raw], "equity")
                    yield MarketDataSnapshot(instrument_id=inst)

    # ------------------------------------------------------------------
    # Symbol Resolution
    # ------------------------------------------------------------------

    async def resolve_symbol(self, symbol: str, exchange: str = "") -> str:
        """Resolve a symbol to canonical instrument ID."""
        if self._normalization:
            return await self._normalization.map_symbol(symbol, exchange)
        return symbol

    async def resolve_symbols(self, symbols: list[str], exchange: str = "") -> dict[str, str]:
        """Resolve multiple symbols."""
        results = {}
        for sym in symbols:
            results[sym] = await self.resolve_symbol(sym, exchange)
        return results

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active_subscription_count(self) -> int:
        return sum(1 for s in self._subscriptions.values() if s.active)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)
