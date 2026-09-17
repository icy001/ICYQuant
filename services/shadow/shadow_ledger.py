"""Shadow event ledger — every decision traceable (Commit 016 §19).

The §19 chain::

    SIGNAL → RISK_DECISION → ORDER_INTENT → ORDER_ACCEPTED/REJECTED
          → FILL → POSITION_UPDATE → PNL_UPDATE

is recorded as an append-only event stream, so "why did we buy this
ETF?" is always answerable from the ledger — not just from the final
``BUY 159852``.

Persistence (§14): when a ``persist_path`` is configured the ledger
appends one JSON line per event, so a Redis outage (or a process
restart) can never lose Shadow state.  ``load_and_adopt`` re-reads the
stream so a new session resumes from the same orders / fills /
positions instead of starting from blank capital.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ShadowEventType(str, Enum):
    """The §19 vocabulary — one entry per decision step."""

    SESSION_STARTED = "SESSION_STARTED"
    SESSION_STOPPED = "SESSION_STOPPED"
    SIGNAL = "SIGNAL"
    RISK_DECISION = "RISK_DECISION"
    ORDER_INTENT = "ORDER_INTENT"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    FILL = "FILL"
    POSITION_UPDATE = "POSITION_UPDATE"
    PNL_UPDATE = "PNL_UPDATE"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ShadowEvent:
    """One immutable ledger entry."""

    event_id: str
    type: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


class ShadowEventLedger:
    """In-memory event stream with optional JSONL persistence."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._path = Path(persist_path) if persist_path else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[ShadowEvent] = []
        self._seq = 0

    @property
    def persist_path(self) -> Optional[str]:
        return str(self._path) if self._path else None

    def append(
        self,
        type_: "ShadowEventType | str",
        *,
        payload: Optional[dict] = None,
        timestamp: Optional[datetime] = None,
    ) -> ShadowEvent:
        etype = (
            type_
            if isinstance(type_, ShadowEventType)
            else ShadowEventType(str(type_).upper())
        )
        self._seq += 1
        event = ShadowEvent(
            event_id=f"SHEV-{self._seq:08d}",
            type=etype.value,
            timestamp=timestamp or _utc_now(),
            payload=dict(payload or {}),
        )
        self._events.append(event)
        if self._path is not None:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(
                        json.dumps(
                            event.as_dict(),
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )
            except OSError:
                # Persistence must never break trading; the in-memory
                # stream still holds the event (§14 best-effort).
                logger.exception("shadow ledger persist failed")
        return event

    def load_and_adopt(self) -> list[dict]:
        """Read the persisted stream back and adopt its sequence.

        Returns the raw event dicts for state replay.  When no file
        exists (first run) the ledger stays empty.
        """
        if self._path is None or not self._path.exists():
            return []
        events: list[dict] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("skipping corrupt shadow ledger line")
        self._events = [
            ShadowEvent(
                event_id=ev.get("event_id", ""),
                type=ev.get("type", ""),
                timestamp=_parse_ts(ev.get("timestamp")),
                payload=ev.get("payload", {}),
            )
            for ev in events
        ]
        self._seq = len(self._events)
        return events

    def events(
        self,
        *,
        type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Query view, newest last; ``limit`` keeps the newest tail."""
        rows = [ev.as_dict() for ev in self._events]
        if type:
            rows = [r for r in rows if r["type"] == str(type).upper()]
        if symbol:
            rows = [r for r in rows if r["payload"].get("symbol") == symbol]
        if limit is not None and limit >= 0:
            rows = rows[-limit:] if limit else []
        return rows

    def count(self, type: Optional[str] = None) -> int:
        if not type:
            return len(self._events)
        return sum(1 for ev in self._events if ev.type == str(type).upper())


def _parse_ts(raw) -> datetime:
    if isinstance(raw, datetime):
        return raw
    try:
        parsed = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return _utc_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = ["ShadowEventType", "ShadowEvent", "ShadowEventLedger"]
