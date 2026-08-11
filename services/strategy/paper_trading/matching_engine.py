"""
Matching Engine
===============
Price-time priority matching engine for paper trading.

Matches orders against a simulated order book using standard
exchange matching rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MatchStatus(str, Enum):
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


@dataclass
class MatchResult:
    """Result of order matching."""
    match_id: str = field(default_factory=lambda: f"match_{uuid4().hex[:8]}")
    order_id: str = ""
    status: MatchStatus = MatchStatus.PENDING
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    remaining_quantity: float = 0.0
    fills: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MatchingEngine:
    """Price-time priority matching engine for paper trading."""

    def __init__(self):
        self._order_book: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._matches: List[MatchResult] = []
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("MatchingEngine initialized")

    async def match(self, instrument: str, side: str, quantity: float,
                    limit_price: Optional[float] = None,
                    order_type: str = "MARKET",
                    current_price: float = 0.0) -> MatchResult:
        """Match an order against the simulated order book."""
        if current_price <= 0:
            return MatchResult(status=MatchStatus.REJECTED)

        if order_type == "LIMIT" and limit_price is not None:
            opposite_side = "asks" if side == "BUY" else "bids"
            book = self._order_book.get(instrument, {}).get(opposite_side, [])

            matched = [l for l in book if (
                (side == "BUY" and l["price"] <= limit_price) or
                (side == "SELL" and l["price"] >= limit_price)
            )]
            if not matched:
                return MatchResult(status=MatchStatus.PENDING, remaining_quantity=quantity)

            # Simple price-time priority fill
            remaining = quantity
            fills = []
            for level in sorted(matched, key=lambda x: x["price"],
                                reverse=(side == "SELL")):
                if remaining <= 0:
                    break
                fill_qty = min(remaining, level["quantity"])
                fills.append({"price": level["price"], "quantity": fill_qty})
                remaining -= fill_qty

            result = MatchResult(
                status=MatchStatus.FILLED if remaining <= 0 else MatchStatus.PARTIALLY_FILLED,
                filled_quantity=quantity - remaining,
                avg_price=(
                    sum(f["price"] * f["quantity"] for f in fills) / (quantity - remaining)
                    if fills else 0
                ),
                remaining_quantity=remaining,
                fills=fills,
            )
        else:
            # Market order: fill at current price
            result = MatchResult(
                status=MatchStatus.FILLED,
                filled_quantity=quantity,
                avg_price=current_price,
                fills=[{"price": current_price, "quantity": quantity}],
            )

        self._matches.append(result)
        return result

    def add_order_to_book(self, instrument: str, side: str,
                          price: float, quantity: float) -> None:
        """Add a resting order to the order book."""
        side_key = "bids" if side == "BUY" else "asks"
        if instrument not in self._order_book:
            self._order_book[instrument] = {"bids": [], "asks": []}
        self._order_book[instrument][side_key].append({
            "price": price,
            "quantity": quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Sort: bids descending, asks ascending
        reverse = (side == "BUY")
        self._order_book[instrument][side_key].sort(
            key=lambda x: x["price"], reverse=reverse
        )

    def match_count(self) -> int:
        return len(self._matches)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_matches": len(self._matches),
            "instruments_in_book": len(self._order_book),
        }
