"""Paper feed state, block codes and decision records (Commit 009).

PaperFeedState — the honest answer to "can Paper Trading act right
now?" (§12)::

    READY      market open, data fresh, cache healthy  → orders allowed
    DEGRADED   cache backend failing                   → new orders BLOCKED
    BLOCKED    session closed / gate refusing          → no fills
    OFFLINE    no feed / no subscriptions              → nothing to trade

Redis is *only* a cache — but a failing cache must never let Paper
Trading keep trading blindly (§12), so a degraded cache blocks new
orders instead of silently degrading into a guess.

FillPriceSource (§5) — every simulated fill records where its price
came from, so Paper Trading fill quality stays analysable later::

    BUY  → ASK  (fallback LAST when no book)
    SELL → BID  (fallback LAST when no book)

PaperFeedError (§17) — every block leaves a machine-readable reason,
never a bare ``False``::

    PAPER_MARKET_DATA_UNAVAILABLE / _STALE / _INVALID / _WARNING
    PAPER_MARKET_SESSION_BLOCKED
    PAPER_LOOKAHEAD_VIOLATION
    PAPER_INVALID_LOT_SIZE
    PAPER_QUOTE_UNAVAILABLE
    PAPER_FEED_DEGRADED

``PAPER_MARKET_DATA_WARNING`` extends the spec's §17 list by one code:
§10 gives WARNING its own gate ("default: no new orders"), so folding
it into STALE or INVALID would make a WARNING block indistinguishable
from a genuinely stale / corrupt quote in the audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class PaperFeedState(str, Enum):
    """Feed-level readiness (§12)."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    OFFLINE = "OFFLINE"


class FillPriceSource(str, Enum):
    """Where a simulated fill price came from (§5)."""

    ASK = "ASK"
    BID = "BID"
    LAST = "LAST"


class PaperFeedError(str, Enum):
    """Machine-readable Paper block / failure codes (§17)."""

    MARKET_DATA_UNAVAILABLE = "PAPER_MARKET_DATA_UNAVAILABLE"
    MARKET_DATA_WARNING = "PAPER_MARKET_DATA_WARNING"
    MARKET_DATA_STALE = "PAPER_MARKET_DATA_STALE"
    MARKET_DATA_INVALID = "PAPER_MARKET_DATA_INVALID"
    SESSION_BLOCKED = "PAPER_MARKET_SESSION_BLOCKED"
    LOOKAHEAD_VIOLATION = "PAPER_LOOKAHEAD_VIOLATION"
    INVALID_LOT_SIZE = "PAPER_INVALID_LOT_SIZE"
    QUOTE_UNAVAILABLE = "PAPER_QUOTE_UNAVAILABLE"
    FEED_DEGRADED = "PAPER_FEED_DEGRADED"


class PaperBlockedError(RuntimeError):
    """Raised when a Paper data request cannot be honoured.

    Carries the same code the decision path would report so callers
    never have to string-match an error message.
    """

    def __init__(
        self,
        code: PaperFeedError,
        symbol: str = "",
        detail: str = "",
    ) -> None:
        self.code = code
        self.symbol = symbol
        self.detail = detail
        super().__init__(
            f"{code.value}: {symbol or '-'}"
            + (f" ({detail})" if detail else "")
        )


@dataclass(frozen=True)
class PaperOrderDecision:
    """The single "may this Paper order proceed?" verdict.

    A blocked verdict is a first-class result, not an exception —
    §17 requires every block to leave its reason behind::

        PaperOrderDecision(
            allowed=False,
            reason="PAPER_MARKET_DATA_STALE",
            symbol="159852",
            quote_age_ms=4210,
        )
    """

    allowed: bool
    reason: Optional[str] = None
    symbol: str = ""
    detail: str = ""
    quote_age_ms: Optional[int] = None
    phase: Optional[str] = None
    quality: Optional[str] = None
    fill_price: Optional[Decimal] = None
    fill_price_source: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "symbol": self.symbol,
            "detail": self.detail,
            "quote_age_ms": self.quote_age_ms,
            "phase": self.phase,
            "quality": self.quality,
            "fill_price": (
                str(self.fill_price) if self.fill_price is not None else None
            ),
            "fill_price_source": self.fill_price_source,
        }


@dataclass(frozen=True)
class PaperFill:
    """A simulated fill — real market price, imaginary money (§9)."""

    symbol: str
    side: str
    quantity: int
    price: Decimal
    price_source: str
    slippage_bps: float
    quote_timestamp: datetime
    fill_timestamp: datetime
    order_timestamp: Optional[datetime] = None
    quality: Optional[str] = None
    phase: Optional[str] = None

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": str(self.price),
            "price_source": self.price_source,
            "slippage_bps": self.slippage_bps,
            "notional": str(self.notional),
            "quote_timestamp": self.quote_timestamp.isoformat(),
            "fill_timestamp": self.fill_timestamp.isoformat(),
            "order_timestamp": (
                self.order_timestamp.isoformat()
                if self.order_timestamp
                else None
            ),
            "quality": self.quality,
            "phase": self.phase,
        }



__all__ = [
    "PaperFeedState",
    "FillPriceSource",
    "PaperFeedError",
    "PaperBlockedError",
    "PaperOrderDecision",
    "PaperFill",
]
