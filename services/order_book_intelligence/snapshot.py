"""Order Book Snapshot — real-time Level 1/2/3 order book state.

Maintains multi-level order book snapshots with bid/ask depth,
spread tracking, and order book dynamics over time windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BookLevel(str, Enum):
    """Order book depth levels."""

    LEVEL_1 = "level_1"  # Best bid/ask only
    LEVEL_2 = "level_2"  # Aggregated price levels
    LEVEL_3 = "level_3"  # Individual order granularity


class BookSide(str, Enum):
    """Order book side."""

    BID = "bid"
    ASK = "ask"


class BookEvent(str, Enum):
    """Order book event types."""

    ADD = "add"
    MODIFY = "modify"
    CANCEL = "cancel"
    EXECUTE = "execute"
    SNAPSHOT = "snapshot"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PriceLevel:
    """Single price level in the order book.

    Attributes:
        price: Price at this level.
        volume: Total volume at this level.
        order_count: Number of orders at this level.
    """

    price: float
    volume: float
    order_count: int = 1

    @property
    def notional(self) -> float:
        """Notional value = price × volume."""
        return self.price * self.volume


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot at a point in time.

    Attributes:
        symbol: Trading symbol.
        bids: Bid-side price levels sorted descending by price.
        asks: Ask-side price levels sorted ascending by price.
        timestamp: Unix timestamp or datetime.
        level: Book depth level.
        last_price: Last traded price.
        last_volume: Last traded volume.
    """

    symbol: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: BookLevel = BookLevel.LEVEL_2
    last_price: float = 0.0
    last_volume: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def best_bid(self) -> Optional[PriceLevel]:
        """Highest bid price."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[PriceLevel]:
        """Lowest ask price."""
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float:
        """Mid price = (best_bid + best_ask) / 2."""
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return (bb.price + ba.price) / 2.0
        return self.last_price

    @property
    def spread(self) -> float:
        """Absolute spread = best_ask - best_bid."""
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return ba.price - bb.price
        return 0.0

    @property
    def spread_bps(self) -> float:
        """Spread in basis points relative to mid."""
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 10000
        return 0.0

    @property
    def bid_volume_total(self) -> float:
        """Total bid-side volume across all levels."""
        return sum(b.volume for b in self.bids)

    @property
    def ask_volume_total(self) -> float:
        """Total ask-side volume across all levels."""
        return sum(a.volume for a in self.asks)

    @property
    def total_depth(self) -> float:
        """Total order book depth (both sides)."""
        return self.bid_volume_total + self.ask_volume_total

    @property
    def depth_ratio(self) -> float:
        """Bid depth / Ask depth ratio."""
        ask_vol = self.ask_volume_total
        if ask_vol == 0:
            return float("inf") if self.bid_volume_total > 0 else 1.0
        return self.bid_volume_total / ask_vol

    def depth_at(self, levels: int, side: BookSide) -> float:
        """Cumulative volume at top N levels on a given side.

        Args:
            levels: Number of price levels to aggregate.
            side: BID or ASK.

        Returns:
            Cumulative volume at top N levels.
        """
        book = self.bids if side == BookSide.BID else self.asks
        return sum(l.volume for l in book[:levels])

    def weighted_price(self, volume: float, side: BookSide) -> Optional[float]:
        """VWAP for given volume on one side (market impact estimate).

        Args:
            volume: Target volume to execute.
            side: BID or ASK.

        Returns:
            Volume-weighted average execution price, or None if insufficient depth.
        """
        book = self.bids if side == BookSide.BID else self.asks
        remaining = volume
        total_cost = 0.0
        for level in book:
            fill = min(level.volume, remaining)
            total_cost += fill * level.price
            remaining -= fill
            if remaining <= 0:
                break
        if remaining > 0:
            return None  # Insufficient depth
        return total_cost / volume

    def imbalance(self, depth_levels: int = 5) -> float:
        """Order imbalance at top N levels: (bid_vol - ask_vol) / total.

        Args:
            depth_levels: Number of levels to include.

        Returns:
            Imbalance score from -1.0 (heavy sell) to +1.0 (heavy buy).
        """
        bid_vol = self.depth_at(depth_levels, BookSide.BID)
        ask_vol = self.depth_at(depth_levels, BookSide.ASK)
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "best_bid": self.best_bid.price if self.best_bid else None,
            "best_ask": self.best_ask.price if self.best_ask else None,
            "mid_price": round(self.mid_price, 4),
            "spread_bps": round(self.spread_bps, 2),
            "bid_depth_5": round(self.depth_at(5, BookSide.BID), 2),
            "ask_depth_5": round(self.depth_at(5, BookSide.ASK), 2),
            "imbalance": round(self.imbalance(), 4),
            "bids": [(l.price, l.volume) for l in self.bids[:10]],
            "asks": [(l.price, l.volume) for l in self.asks[:10]],
        }


# ---------------------------------------------------------------------------
# OrderBookBuilder
# ---------------------------------------------------------------------------


class OrderBookBuilder:
    """Builds and maintains order book snapshots from streaming events.

    Attributes:
        symbol: Trading symbol.
        max_levels: Maximum depth levels to maintain per side.
        history: List of snapshots over time.
        max_history: Maximum snapshots to retain.
    """

    def __init__(
        self,
        symbol: str = "",
        max_levels: int = 50,
        max_history: int = 1000,
    ) -> None:
        """Initialize the order book builder.

        Args:
            symbol: Trading symbol.
            max_levels: Maximum price levels per side.
            max_history: Maximum snapshots in history buffer.
        """
        self.symbol = symbol
        self.max_levels = max_levels
        self.max_history = max_history
        self.bids: dict[float, float] = {}  # price → volume
        self.asks: dict[float, float] = {}
        self.last_price: float = 0.0
        self.last_volume: float = 0.0
        self.history: list[OrderBookSnapshot] = []

    def update(
        self,
        side: BookSide,
        price: float,
        volume: float,
        event: BookEvent = BookEvent.ADD,
    ) -> None:
        """Apply a single order book update event.

        Args:
            side: BID or ASK.
            price: Price level.
            volume: New volume (0 = remove level).
            event: Type of book event.
        """
        book = self.bids if side == BookSide.BID else self.asks

        if event == BookEvent.EXECUTE:
            # Execution: reduce existing volume
            if price in book:
                book[price] = max(0.0, book[price] - volume)
                if book[price] <= 0:
                    del book[price]
        elif event == BookEvent.CANCEL:
            if price in book:
                book[price] = max(0.0, book[price] - volume)
                if book[price] <= 0:
                    del book[price]
        elif volume <= 0:
            if price in book:
                del book[price]
        else:
            book[price] = volume

        # Prune to max levels
        self._prune()

    def apply_snapshot(
        self,
        bids: dict[float, float],
        asks: dict[float, float],
        last_price: float = 0.0,
        last_volume: float = 0.0,
    ) -> None:
        """Replace entire book with a full snapshot.

        Args:
            bids: Bid price → volume mapping.
            asks: Ask price → volume mapping.
            last_price: Last traded price.
            last_volume: Last traded volume.
        """
        self.bids = bids.copy()
        self.asks = asks.copy()
        self.last_price = last_price
        self.last_volume = last_volume
        self._prune()

    def snapshot(self, level: BookLevel = BookLevel.LEVEL_2) -> OrderBookSnapshot:
        """Generate current order book snapshot.

        Args:
            level: Depth level for the snapshot.

        Returns:
            OrderBookSnapshot with current state.
        """
        bid_levels = [
            PriceLevel(price=p, volume=v)
            for p, v in sorted(self.bids.items(), reverse=True)[:self.max_levels]
        ]
        ask_levels = [
            PriceLevel(price=p, volume=v)
            for p, v in sorted(self.asks.items())[:self.max_levels]
        ]

        snap = OrderBookSnapshot(
            symbol=self.symbol,
            bids=bid_levels,
            asks=ask_levels,
            level=level,
            last_price=self.last_price,
            last_volume=self.last_volume,
        )

        self.history.append(snap)
        while len(self.history) > self.max_history:
            self.history.pop(0)

        return snap

    def _prune(self) -> None:
        """Keep only top max_levels levels per side."""
        if len(self.bids) > self.max_levels:
            sorted_bids = sorted(self.bids.items(), reverse=True)
            self.bids = dict(sorted_bids[:self.max_levels])
        if len(self.asks) > self.max_levels:
            sorted_asks = sorted(self.asks.items())
            self.asks = dict(sorted_asks[:self.max_levels])

    def clear(self) -> None:
        """Reset order book state."""
        self.bids.clear()
        self.asks.clear()
        self.history.clear()
        self.last_price = 0.0
        self.last_volume = 0.0
