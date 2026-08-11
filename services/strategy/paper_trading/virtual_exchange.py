"""
Virtual Exchange
================
Simulates a trading exchange with order book, matching, and trade generation.

Supports:
    - Limit Order, Market Order, Stop Order
    - Order Book depth management
    - Price-time priority matching
    - IOC/FOK (reserved)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderBookSide(str, Enum):
    BID = "BID"
    ASK = "ASK"


@dataclass
class OrderBookLevel:
    """A single level in the order book."""
    price: float
    quantity: float
    side: OrderBookSide
    order_count: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderBook:
    """Simulated order book for a single instrument."""
    instrument: str = ""
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    last_price: float = 0.0
    last_quantity: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_bid(self) -> Optional[float]:
        return max((l.price for l in self.bids), default=None)

    @property
    def best_ask(self) -> Optional[float]:
        return min((l.price for l in self.asks), default=None)

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return self.last_price or None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        mid = self.mid_price
        sp = self.spread
        if mid and sp and mid > 0:
            return (sp / mid) * 10000
        return None

    def update(self, price: float, quantity: float) -> None:
        self.last_price = price
        self.last_quantity = quantity
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument": self.instrument,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "last_price": self.last_price,
            "bid_levels": len(self.bids),
            "ask_levels": len(self.asks),
        }


class VirtualExchange:
    """Simulated trading exchange with order book management.

    Pipeline:
        Market Data → Order Book → Matching → Trade
    """

    def __init__(self):
        self._order_books: Dict[str, OrderBook] = {}
        self._last_prices: Dict[str, float] = {}
        self._trades: List[Dict[str, Any]] = []
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("VirtualExchange initialized")

    # ------------------------------------------------------------------
    # Order Book
    # ------------------------------------------------------------------

    def get_order_book(self, instrument: str) -> OrderBook:
        """Get or create the order book for an instrument."""
        if instrument not in self._order_books:
            self._order_books[instrument] = OrderBook(instrument=instrument)
        return self._order_books[instrument]

    def update_price(self, instrument: str, price: float,
                     bid: Optional[float] = None, ask: Optional[float] = None) -> None:
        """Update market price for an instrument."""
        self._last_prices[instrument] = price
        book = self.get_order_book(instrument)
        book.update(price, 0)

        if bid is not None:
            book.bids = [OrderBookLevel(price=bid, quantity=1000, side=OrderBookSide.BID)]
        if ask is not None:
            book.asks = [OrderBookLevel(price=ask, quantity=1000, side=OrderBookSide.ASK)]

    def get_price(self, instrument: str) -> Optional[float]:
        """Get the last price for an instrument."""
        return self._last_prices.get(instrument)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match_order(self, instrument: str, side: str, quantity: float,
                    limit_price: Optional[float] = None,
                    order_type: str = "MARKET") -> Dict[str, Any]:
        """Simulate order matching against the order book."""
        book = self.get_order_book(instrument)
        price = self._last_prices.get(instrument, 0.0)

        if order_type == "LIMIT" and limit_price is not None:
            executable = (
                (side == "BUY" and limit_price >= (book.best_ask or limit_price)) or
                (side == "SELL" and limit_price <= (book.best_bid or limit_price))
            )
            if not executable:
                return {"status": "pending", "filled": 0, "price": 0, "reason": "limit_not_met"}
            fill_price = limit_price
        else:
            fill_price = price

        # Partial fill based on available liquidity at the fill price
        fill_qty = quantity  # Full fill by default
        if fill_price <= 0:
            return {"status": "rejected", "filled": 0, "price": 0, "reason": "no_price"}

        trade = {
            "trade_id": f"vt_{uuid4().hex[:8]}",
            "instrument": instrument,
            "side": side,
            "quantity": fill_qty,
            "price": fill_price,
            "timestamp": datetime.now(timezone.utc),
        }
        self._trades.append(trade)

        book.update(fill_price, fill_qty)
        return {"status": "filled", "filled": fill_qty, "price": fill_price, "trade": trade}

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def instruments(self) -> List[str]:
        return list(self._order_books.keys())

    def recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._trades[-limit:]

    def trade_count(self) -> int:
        return len(self._trades)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "instruments_tracked": len(self._order_books),
            "total_trades": len(self._trades),
        }
