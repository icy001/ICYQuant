"""Quarantine — where rejected market data lives on (Commit 006).

Bad data is never silently deleted.  Everything the Quality Gate
rejects (INVALID / QUARANTINED / duplicates) is stored here with its
full context so an operator can later answer:

    "Why did ICYQuant produce no order at 10:31?"

        Quote → Quality Gate → STALE / INVALID → Order blocked
                        ↘ Quarantine (raw payload + reason)

The store is bounded (ring) and thread-safe; it keeps the most
recent rejections plus aggregate statistics.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..domain.quote import MarketQuote
from .quality_result import MarketDataQualityResult


@dataclass(frozen=True)
class QuarantinedItem:
    """One rejected quote with its quality verdict."""

    symbol: str
    quote: dict                      # normalized quote payload
    status: str                      # quality status value
    reasons: list[str]               # failure codes
    action: str                      # gate action
    received_at: Optional[datetime]  # ICYQuant receive time

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quote": self.quote,
            "status": self.status,
            "reasons": list(self.reasons),
            "action": self.action,
            "received_at": (
                self.received_at.isoformat()
                if self.received_at
                else None
            ),
        }


class QuarantineStore:
    """Bounded, thread-safe quarantine for rejected market data."""

    def __init__(self, capacity: int = 500) -> None:
        self._lock = threading.Lock()
        self._items: deque[QuarantinedItem] = deque(maxlen=capacity)
        self._total = 0
        self._by_reason: dict[str, int] = {}
        self._by_status: dict[str, int] = {}

    # ── write path ──────────────────────────────────────────────

    def record(
        self,
        quote: MarketQuote,
        result: MarketDataQualityResult,
    ) -> QuarantinedItem:
        """Store a rejected quote with its verdict.  Returns the item.

        Even payloads that cannot be fully serialized (structurally
        broken data — the very reason they are quarantined) must be
        preserved: fall back to a minimal raw snapshot.
        """
        try:
            payload = quote.as_dict()
        except Exception:
            payload = {
                "symbol": quote.symbol,
                "timestamp": quote.timestamp.isoformat()
                if quote.timestamp
                else None,
                "last": str(quote.last),
                "bid": str(quote.bid),
                "ask": str(quote.ask),
                "volume": quote.volume,
            }
        item = QuarantinedItem(
            symbol=quote.symbol,
            quote=payload,
            status=result.status.value,
            reasons=list(result.reasons),
            action=result.action,
            received_at=quote.received_timestamp
            or datetime.now(timezone.utc),
        )
        with self._lock:
            self._items.append(item)
            self._total += 1
            for reason in result.reasons:
                self._by_reason[reason] = (
                    self._by_reason.get(reason, 0) + 1
                )
            self._by_status[result.status.value] = (
                self._by_status.get(result.status.value, 0) + 1
            )
        return item

    # ── read path ───────────────────────────────────────────────

    def recent(self, limit: int = 50) -> list[dict]:
        """Most recent quarantined items (newest first)."""
        with self._lock:
            items = list(self._items)[-limit:]
        items.reverse()
        return [i.as_dict() for i in items]

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def stats(self) -> dict:
        with self._lock:
            return {
                "total_rejected": self._total,
                "in_store": len(self._items),
                "by_reason": dict(self._by_reason),
                "by_status": dict(self._by_status),
            }

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
            self._total = 0
            self._by_reason.clear()
            self._by_status.clear()


__all__ = ["QuarantineStore", "QuarantinedItem"]
