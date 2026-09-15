"""Replay state and audit records (Commit 012 §20 / §24).

State machine (§20)::

                     start()
        IDLE ──────────────────────► RUNNING ◄──────┐
          ▲                            │  │         │ resume()
          │ reset()                    │  │ pause() │
          │                     ┌──────┘  └────► PAUSED
          │                     │                  │
          │              (timeline drained)         │ stop()
          │                     ▼                  ▼
          └──────────────── COMPLETED           STOPPED
                                ▲
                                │ unrecoverable failure (load/provider)
                              ERROR

* ``IDLE``      nothing is being replayed (before start, or after reset)
* ``RUNNING``   events are flowing (or available to ``step()``)
* ``PAUSED``    auto-advance halted; ``step()`` still walks one event
* ``COMPLETED`` the window was drained to the end
* ``STOPPED``   terminated early by the operator
* ``ERROR``     the run failed and cannot continue

``PAUSED`` + ``step()`` is the §7 debug workflow: pause the clock and
walk ``Quote → Signal → Order → Fill`` one line at a time.

§24 Replay audit
----------------

Every run mints a :class:`ReplayRun` carrying ``replay_id``, symbol,
trading date, timeframe, speed, start/end timestamp, event count and
completion, so "which replay produced this fill?" always has an answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReplayState(str, Enum):
    """Lifecycle of a replay run (§20)."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ReplayError(str, Enum):
    """Typed replay block reasons (§17 — never a bare ``False``)."""

    DISABLED = "REPLAY_DISABLED"
    NO_DATA = "REPLAY_NO_DATA"
    UNKNOWN_SYMBOL = "REPLAY_UNKNOWN_SYMBOL"
    INVALID_WINDOW = "REPLAY_INVALID_WINDOW"
    INVALID_SPEED = "REPLAY_INVALID_SPEED"
    NOT_READY = "REPLAY_NOT_READY"
    ALREADY_RUNNING = "REPLAY_ALREADY_RUNNING"
    TERMINATED = "REPLAY_TERMINATED"
    # ── data quarantine reasons (§15 / §16 / §27) ────────────────
    CALENDAR_VIOLATION = "REPLAY_CALENDAR_VIOLATION"
    JUNCTION_VIOLATION = "REPLAY_JUNCTION_VIOLATION"
    INCOMPLETE_BAR = "REPLAY_INCOMPLETE_BAR"
    EXCHANGE_MISMATCH = "REPLAY_EXCHANGE_MISMATCH"
    INVALID_BAR = "REPLAY_INVALID_BAR"
    DUPLICATE_BAR = "REPLAY_DUPLICATE_BAR"
    PROVIDER_FAILED = "REPLAY_PROVIDER_FAILED"


class ReplayBlockedError(RuntimeError):
    """Raised when a replay operation cannot proceed.

    Carries a machine-readable :class:`ReplayError` so the API layer can
    map it onto an HTTP status without string matching.
    """

    def __init__(
        self,
        code: ReplayError | str,
        *,
        detail: Optional[str] = None,
        symbol: Optional[str] = None,
        quarantined: int = 0,
    ) -> None:
        self.code = ReplayError(code) if isinstance(code, str) else code
        self.detail = detail
        self.symbol = symbol
        self.quarantined = quarantined
        message = self.code.value
        if symbol:
            message = f"{message} [{symbol}]"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)

    def as_dict(self) -> dict:
        return {
            "error": self.code.value,
            "symbol": self.symbol,
            "detail": self.detail,
            "quarantined": self.quarantined,
        }


@dataclass(frozen=True)
class ReplayRun:
    """Immutable audit record of one replay (§24).

    Minted by ``load()``/``start()`` with the *plan* (window, digest,
    quarantine findings); the live outcome (``events_processed``,
    ``completed``, ``finished_at``) is filled in by
    :meth:`ReplayEngine.audit` when the run ends.

    ``digest`` is a SHA-1 over the ordered ``bar_id`` list.  Re-running
    the same window must reproduce it exactly — that is what makes
    "deterministic replay" a testable claim rather than a promise (§25).
    """

    replay_id: str
    symbols: list[str] = field(default_factory=list)
    trading_date: Optional[str] = None
    timeframe: str = "1m"
    speed: float = 1.0
    mode: str = "AUTO"
    # ── timeline ─────────────────────────────────────────────────
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    events_total: int = 0
    events_quarantined: int = 0
    duplicates: int = 0
    gaps: int = 0
    session_breaks: int = 0
    # ── audit ────────────────────────────────────────────────────
    loaded_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    events_processed: int = 0
    completed: bool = False
    status: str = ReplayState.IDLE.value
    rejections: list[dict] = field(default_factory=list)
    digest: str = ""

    def as_dict(self) -> dict:
        """Serializable view (§24 example shape)."""
        return {
            "replay_id": self.replay_id,
            "symbols": list(self.symbols),
            "symbol": self.symbols[0] if self.symbols else None,
            "trading_date": self.trading_date,
            "timeframe": self.timeframe,
            "speed": self.speed,
            "mode": self.mode,
            "window_start": (
                self.window_start.isoformat() if self.window_start else None
            ),
            "window_end": (
                self.window_end.isoformat() if self.window_end else None
            ),
            "events_total": self.events_total,
            "events_processed": self.events_processed,
            "events_quarantined": self.events_quarantined,
            "duplicates": self.duplicates,
            "gaps": self.gaps,
            "session_breaks": self.session_breaks,
            "loaded_at": (
                self.loaded_at.isoformat() if self.loaded_at else None
            ),
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "completed": self.completed,
            "status": self.status,
            "rejections": list(self.rejections),
            "digest": self.digest,
        }


__all__ = ["ReplayState", "ReplayError", "ReplayBlockedError", "ReplayRun"]
