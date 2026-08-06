"""Matching Engine — price-time priority order matching.

Matches buy and sell orders following exchange-like rules with
price-time priority, supporting both backtesting and future
paper trading scenarios.

Matching Rules:
* Price-time priority (best price first, then earliest order)
* Full or partial fills
* Volume constraints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


class MatchingResult(str, Enum):
    """Matching outcome."""

    FULL = "full"
    PARTIAL = "partial"
    NO_MATCH = "no_match"


@dataclass
class OrderBookEntry:
    """A single order in the order book."""

    order_id: str
    symbol: str
    side: str  # buy or sell
    price: float
    quantity: float
    remaining: float
    order_type: str = "limit"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    """Result of a matching operation."""

    match_id: str = field(default_factory=lambda: str(uuid4()))
    buy_order_id: str = ""
    sell_order_id: str = ""
    symbol: str = ""
    price: float = 0.0
    quantity: float = 0.0
    result: MatchingResult = MatchingResult.NO_MATCH
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MatchingEngine:
    """Price-time priority order matching engine.

    Maintains separate bid (buy) and ask (sell) books, matching
    orders when prices cross. Buy orders with higher prices and
    sell orders with lower prices get priority.

    Can be used for:
    * Backtesting (simulate exchange matching)
    * Paper trading (realistic fill simulation)
    * Market making strategy testing
    """

    def __init__(self) -> None:
        # Buy orders: sorted by price descending, then timestamp ascending
        self._buy_book: List[OrderBookEntry] = []
        # Sell orders: sorted by price ascending, then timestamp ascending
        self._sell_book: List[OrderBookEntry] = []
        self._matches: List[MatchResult] = []

    # ── order placement ────────────────────────────────────────────────────

    def place_order(self, entry: OrderBookEntry) -> None:
        """Place an order in the order book."""
        if entry.side == "buy":
            self._buy_book.append(entry)
            self._buy_book.sort(key=lambda e: (-e.price, e.timestamp))
        elif entry.side == "sell":
            self._sell_book.append(entry)
            self._sell_book.sort(key=lambda e: (e.price, e.timestamp))
        else:
            raise ValueError(f"Invalid side: {entry.side}")

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookEntry:
        """Place a limit order and attempt to match.

        Returns:
            The placed order book entry.
        """
        entry = OrderBookEntry(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            remaining=quantity,
            metadata=metadata or {},
        )
        self.place_order(entry)
        return entry

    # ── matching ───────────────────────────────────────────────────────────

    def match_all(self) -> List[MatchResult]:
        """Match all crossing orders in the book.

        Returns:
            List of match results.
        """
        new_matches = []

        while True:
            result = self._try_match()
            if result.result == MatchingResult.NO_MATCH:
                break
            new_matches.append(result)
            self._matches.append(result)

        return new_matches

    def _try_match(self) -> MatchResult:
        """Attempt to match the best buy and sell orders."""
        if not self._buy_book or not self._sell_book:
            return MatchResult(result=MatchingResult.NO_MATCH)

        best_buy = self._buy_book[0]
        best_sell = self._sell_book[0]

        # Match condition: best buy price >= best sell price
        if best_buy.price < best_sell.price:
            return MatchResult(result=MatchingResult.NO_MATCH)

        # Match at the resting order's price (price-time priority)
        match_price = best_sell.price  # earlier order sets price
        match_qty = min(best_buy.remaining, best_sell.remaining)

        # Update remaining quantities
        best_buy.remaining -= match_qty
        best_sell.remaining -= match_qty

        # Remove fully filled orders
        if best_buy.remaining <= 0:
            self._buy_book.pop(0)
        if best_sell.remaining <= 0:
            self._sell_book.pop(0)

        result_type = MatchingResult.FULL
        if best_buy.remaining > 0 or best_sell.remaining > 0:
            result_type = MatchingResult.PARTIAL

        logger.debug(
            "Match: %s x%.0f @%.2f (%s → %s)",
            best_buy.symbol, match_qty, match_price,
            best_buy.order_id[:6], best_sell.order_id[:6],
        )

        return MatchResult(
            buy_order_id=best_buy.order_id,
            sell_order_id=best_sell.order_id,
            symbol=best_buy.symbol,
            price=match_price,
            quantity=match_qty,
            result=result_type,
        )

    # ── market order matching ──────────────────────────────────────────────

    def match_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Tuple[List[MatchResult], float, float]:
        """Match a market order against the order book.

        Args:
            symbol: Ticker symbol.
            side: buy (crosses sell book) or sell (crosses buy book).
            quantity: Total quantity to fill.

        Returns:
            Tuple of (matches list, total cost, avg price).
        """
        matches: List[MatchResult] = []
        remaining = quantity
        total_cost = 0.0

        book = self._sell_book if side == "buy" else self._buy_book
        i = 0

        while remaining > 0 and i < len(book):
            entry = book[i]
            if entry.symbol != symbol:
                i += 1
                continue

            fill_qty = min(remaining, entry.remaining)
            fill_price = entry.price

            entry.remaining -= fill_qty
            remaining -= fill_qty
            total_cost += fill_qty * fill_price

            match = MatchResult(
                order_id="market" if side == "buy" else entry.order_id,
                buy_order_id=str(uuid4()) if side == "buy" else entry.order_id,
                symbol=symbol,
                price=fill_price,
                quantity=fill_qty,
                result=MatchingResult.FULL if entry.remaining <= 0 else MatchingResult.PARTIAL,
            )
            matches.append(match)
            self._matches.append(match)

            if entry.remaining <= 0:
                book.pop(i)
            else:
                i += 1

        avg_price = total_cost / (quantity - remaining) if (quantity - remaining) > 0 else 0.0
        return matches, total_cost, avg_price

    # ── cancel ─────────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID.

        Returns:
            True if found and cancelled.
        """
        for book in (self._buy_book, self._sell_book):
            for i, entry in enumerate(book):
                if entry.order_id == order_id:
                    book.pop(i)
                    logger.debug("Order cancelled: %s", order_id[:8])
                    return True
        return False

    def cancel_all(self, symbol: Optional[str] = None) -> int:
        """Cancel all orders, optionally filtered by symbol."""
        count = 0
        for book in (self._buy_book, self._sell_book):
            if symbol:
                before = len(book)
                book[:] = [e for e in book if e.symbol != symbol]
                count += before - len(book)
            else:
                count += len(book)
                book.clear()
        logger.info("Cancelled %d orders", count)
        return count

    # ── query ──────────────────────────────────────────────────────────────

    def get_order_book(self, symbol: str) -> Dict[str, Any]:
        """Get the order book for a symbol."""
        buys = [e for e in self._buy_book if e.symbol == symbol]
        sells = [e for e in self._sell_book if e.symbol == symbol]
        return {
            "symbol": symbol,
            "bids": [{"price": e.price, "quantity": e.remaining} for e in buys],
            "asks": [{"price": e.price, "quantity": e.remaining} for e in sells],
            "best_bid": buys[0].price if buys else None,
            "best_ask": sells[0].price if sells else None,
            "spread": (sells[0].price - buys[0].price) if buys and sells else None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return matching engine statistics."""
        return {
            "buy_orders": len(self._buy_book),
            "sell_orders": len(self._sell_book),
            "total_orders": len(self._buy_book) + len(self._sell_book),
            "total_matches": len(self._matches),
            "buy_volume": sum(e.remaining for e in self._buy_book),
            "sell_volume": sum(e.remaining for e in self._sell_book),
        }
