"""Replay Engine (Commit 012 §4 / §10 / §17).

Deterministic, auditable re-emission of historical 1m bars through
ICYQuant::

    Historical Market Data (008)
            ↓
        Replay Engine            ← this module: virtual clock + event stream
            ↓
    ReplayEvent (BAR)            ← §8
            ↓
    Quality Gate (006)           ← §15 — never skipped for "just history"
            ↓
    Paper Market Feed (009)      ← §17 — source=LIVE | REPLAY
            ↓
    Strategy / Paper Trading

Replay is **not** backtest.  A backtest reads everything at once and
computes a statistic; replay walks the series one instant at a time and
lets the *existing* pipeline react, which is what makes it possible to
answer "what actually happened at 10:32 on 2026-09-10?" instead of
guessing.

Core interface (§4)::

    start()   pause()   resume()   stop()   seek(ts)   step()   status()

Invariants
----------

§6 / §25 determinism
    The timeline is built once in ``load()`` and sorted by
    ``(timestamp, symbol)``.  Same window + same provider ⇒ same
    ``run.digest`` and same ``(sequence, bar_id)`` list.  Pacing can
    only slow delivery down, never reorder it.

§5 / §26 no wall clock in the replay path
    Only :class:`ReplayClock` knows the wall clock, and it uses it
    exclusively to *pace*.  The engine's own use of real time is
    confined to one place — ``load()`` refusing bars that have not
    happened yet — and is documented where it happens.

§12 / §16 refuse to fabricate
    No tick synthesis, no gap filling.  A missing 10:34 stays missing:
    the next event is 10:35 and it is flagged ``gap_before``.  Bars that
    fail the calendar, the exchange, closure or the 006 quality gate are
    **quarantined** and recorded in ``run.rejections``, never replayed
    silently.

Import surface::

    from services.market_data.replay import replay_engine

    run = replay_engine.start(["159852"], date="2026-09-10", speed=10)
    while (event := replay_engine.step()) is not None:
        print(event.sequence, event.timestamp, event.last)

    replay_engine.status()     # §20 state payload
    replay_engine.audit()      # §24 record
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import replace
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, Optional

from ..calendar.trading_calendar import CST
from ..calendar.trading_calendar import calendar as default_calendar
from ..domain.bar import Bar
from ..quality.bar_quality import validate_bar
from ..universe import universe as default_universe
from .replay_clock import ReplayClock
from .replay_config import ReplayConfig
from .replay_event import ReplayEvent, ReplayEventType
from .replay_state import (
    ReplayBlockedError,
    ReplayError,
    ReplayRun,
    ReplayState,
)

logger = logging.getLogger(__name__)

# Virtual duration of one event, keyed by timeframe (§11 — 1m only).
_EVENT_DELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

# How many quarantine findings a run keeps before truncating (§24 —
# the count stays exact, the sample is bounded).
_MAX_REJECTION_SAMPLES = 50


def _default_provider():
    """Build the default history source lazily (avoids import cycles)."""
    from ..merge.historical_provider import SyntheticHistoricalProvider

    return SyntheticHistoricalProvider()


def _coerce_utc(value: Optional[object]) -> Optional[datetime]:
    """Coerce date / naive datetime / aware datetime into aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, _date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) == 10:  # YYYY-MM-DD
            parsed = _date.fromisoformat(text)
            return datetime(
                parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc
            )
        return _coerce_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    raise ValueError(f"cannot coerce {value!r} into a timestamp")


def _day_bounds(value: object) -> tuple[datetime, datetime]:
    """``date`` → ``[00:00 CST, next 00:00 CST)`` UTC bounds (§22).

    The window is a *calendar* day in China Standard Time; the trading
    calendar then decides which minutes inside it actually exist, so a
    non-trading date simply yields no events.
    """
    if isinstance(value, str):
        day = _date.fromisoformat(value.strip())
    elif isinstance(value, datetime):
        day = value.date()
    elif isinstance(value, _date):
        day = value
    else:
        raise ValueError(f"cannot read a date from {value!r}")
    start = datetime(day.year, day.month, day.day, tzinfo=CST)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class ReplayEngine:
    """Replays one historical window on a virtual clock (§4).

    Collaborators are injected so the gates can run without sleeping,
    without a network, and without depending on wall-clock time:

    ``provider``           history source (default: 008 synthetic)
    ``trading_calendar``   session / phase authority (005)
    ``config``             resolved :class:`ReplayConfig` (env-driven)
    ``wall_clock``         real time — used **only** at ``load()`` to
                           refuse not-yet-knowable history (§13)
    ``sleeper``            injected by the pacing tests
    ``universe``           Instrument Master (002)
    """

    def __init__(
        self,
        *,
        provider: object = None,
        trading_calendar: object = None,
        config: Optional[ReplayConfig] = None,
        wall_clock: Optional[Callable[[], datetime]] = None,
        sleeper: Optional[Callable[[float], None]] = None,
        universe: object = None,
        autostart: bool = True,
    ) -> None:
        self._cfg = config or ReplayConfig.from_env()
        self._provider = provider or _default_provider()
        self._cal = trading_calendar or default_calendar
        self._instruments = universe or default_universe
        self._wall_clock = wall_clock or (
            lambda: datetime.now(timezone.utc)
        )
        self._clock = ReplayClock(
            speed=self._cfg.default_speed,
            sleeper=sleeper,
            max_sleep_seconds=self._cfg.max_sleep_seconds,
        )
        self._autostart = autostart

        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._events: list[ReplayEvent] = []
        self._cursor = 0
        self._state = ReplayState.IDLE
        self._run: Optional[ReplayRun] = None
        self._thread: Optional[threading.Thread] = None
        self._halt = False
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._load_seq = 0
        self._stats: dict[str, float] = {
            "loads": 0,
            "events_emitted": 0,
            "quarantined": 0,
            "resets": 0,
            "seeks": 0,
            "provider_errors": 0,
        }

    # ── views ────────────────────────────────────────────────────

    @property
    def config(self) -> ReplayConfig:
        return self._cfg

    @property
    def clock(self) -> ReplayClock:
        """The virtual clock (§5) — consumers read ``clock.now``."""
        return self._clock

    @property
    def state(self) -> ReplayState:
        with self._lock:
            return self._state

    @property
    def run(self) -> Optional[ReplayRun]:
        with self._lock:
            return self._run

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    @property
    def now(self) -> Optional[datetime]:
        """Virtual time — the last knowable instant (§5)."""
        return self._clock.now

    @property
    def events_total(self) -> int:
        with self._lock:
            return len(self._events)

    @property
    def events_processed(self) -> int:
        with self._lock:
            return self._cursor

    @property
    def speed(self) -> float:
        return self._clock.speed

    @property
    def manual(self) -> bool:
        """True in the §7 manual/step mode (speed = 0)."""
        return self._clock.manual

    # ── loading (§10 / §11 / §15 / §16) ──────────────────────────

    def load(
        self,
        symbols: Optional[list[str]] = None,
        *,
        limit: Optional[int] = None,
        start: Optional[object] = None,
        end: Optional[object] = None,
        anchor_prices: Optional[dict] = None,
    ) -> ReplayRun:
        """Build the replay timeline and mint its §24 audit record.

        ``symbols`` defaults to the enabled universe (002).  ``limit``
        is per symbol and clamped by ``config.max_limit``.  ``start`` /
        ``end`` bound the window (``end`` is exclusive, so a bar that
        had not closed yet is never replayed with lookahead).
        """
        if not self._cfg.enabled:
            raise ReplayBlockedError(
                ReplayError.DISABLED, detail="MARKET_REPLAY_ENABLED is false"
            )

        with self._lock:
            requested = self._normalise_symbols(symbols)
            resolved_limit = self._cfg.resolve_limit(limit)
            start_utc = _coerce_utc(start)
            end_utc = _coerce_utc(end)
            if start_utc and end_utc and start_utc >= end_utc:
                raise ReplayBlockedError(
                    ReplayError.INVALID_WINDOW,
                    detail="start must be strictly before end",
                )

            delta = self._event_delta()
            # §13 — the ONLY use of real time in the whole commit: a bar
            # whose minute has not finished cannot be replayed, because
            # "what happened after now" is not history yet.
            wall_now = self._wall_clock()
            rejections: list[dict] = []
            duplicates = 0
            events: list[ReplayEvent] = []
            seen_ids: set[str] = set()
            anchors = anchor_prices or {}

            for symbol in requested:
                instrument = self._instruments.get(symbol)
                try:
                    bars = self._provider.bars(
                        symbol,
                        self._cfg.timeframe,
                        resolved_limit,
                        before=end_utc,
                        anchor_price=anchors.get(symbol),
                    )
                except Exception as exc:  # noqa: BLE001 — normalised below
                    self._stats["provider_errors"] += 1
                    self._last_error = str(exc)
                    self._fail(str(exc))
                    raise ReplayBlockedError(
                        ReplayError.PROVIDER_FAILED,
                        symbol=symbol,
                        detail=str(exc),
                    ) from exc

                for bar in bars:
                    if start_utc and bar.timestamp < start_utc:
                        continue
                    if bar.bar_id in seen_ids:
                        # §15 — a duplicate bar is a data finding, not a
                        # second event.  Reported, never replayed twice.
                        duplicates += 1
                        rejections.append(
                            self._rejection(bar, ReplayError.DUPLICATE_BAR)
                        )
                        continue
                    reason = self._quarantine_reason(
                        bar, instrument, delta, wall_now
                    )
                    if reason is not None:
                        detail = self._quality_detail(bar, reason)
                        rejections.append(
                            self._rejection(bar, reason, detail=detail)
                        )
                        continue
                    seen_ids.add(bar.bar_id)
                    events.append(
                        ReplayEvent(
                            timestamp=bar.timestamp + delta,
                            event_type=ReplayEventType.BAR,
                            symbol=symbol,
                            data=bar,
                            phase=self._phase_of(bar.timestamp),
                            tradable=bool(
                                self._cal.is_bar_phase(bar.timestamp)
                            ),
                            quality=self._bar_quality(bar),
                        )
                    )

            if not events:
                detail = f"no replayable events for {requested} in window"
                if rejections:
                    detail = f"{detail} ({len(rejections)} quarantined)"
                raise ReplayBlockedError(
                    ReplayError.NO_DATA,
                    detail=detail,
                    quarantined=len(rejections),
                )

            # §9 — strict ordering: timestamp ASC, then symbol, then the
            # source's own sequence.  Sorting here (once, up front) is
            # what lets every later step be a plain array walk and still
            # be deterministic.
            events.sort(key=lambda e: (e.timestamp, e.symbol))
            events, gaps, breaks = self._annotate(events, delta)

            digest = hashlib.sha1(
                "|".join(e.bar_id for e in events).encode("utf-8")
            ).hexdigest()

            self._load_seq += 1
            run = ReplayRun(
                replay_id=self._replay_id(requested, events[0].timestamp),
                symbols=requested,
                trading_date=self._trading_date(events[0].timestamp),
                timeframe=self._cfg.timeframe,
                speed=self._clock.speed,
                mode=self._mode_label(),
                window_start=events[0].timestamp,
                window_end=events[-1].timestamp,
                events_total=len(events),
                events_quarantined=len(rejections),
                duplicates=duplicates,
                gaps=gaps,
                session_breaks=breaks,
                loaded_at=wall_now,
                status=ReplayState.IDLE.value,
                rejections=rejections[:_MAX_REJECTION_SAMPLES],
                digest=digest,
            )

            self._events = events
            self._cursor = 0
            self._run = run
            self._state = ReplayState.IDLE
            self._halt = False
            self._thread = None
            self._started_at = None
            self._finished_at = None
            self._last_error = None
            self._clock.reset()
            self._stats["loads"] += 1
            self._stats["quarantined"] += len(rejections)

            logger.info(
                "replay %s loaded: %d events (%s), %d quarantined, digest=%s",
                run.replay_id,
                run.events_total,
                ",".join(requested),
                run.events_quarantined,
                run.digest[:12],
            )
            return run

    # ── lifecycle (§4 / §20) ─────────────────────────────────────

    def start(
        self,
        symbols: Optional[list[str]] = None,
        *,
        date: Optional[object] = None,
        limit: Optional[int] = None,
        start: Optional[object] = None,
        end: Optional[object] = None,
        speed: Optional[float] = None,
        anchor_prices: Optional[dict] = None,
    ) -> ReplayRun:
        """Load (when needed) and begin replaying.

        Signatures accepted::

            start(["159852"], date="2026-09-10", speed=10)
            start()                      # resume an already-loaded window

        ``speed=0`` starts the engine in §7 manual mode: the state goes
        to RUNNING but nothing advances until ``step()`` is called.
        """
        if not self._cfg.enabled:
            raise ReplayBlockedError(
                ReplayError.DISABLED, detail="MARKET_REPLAY_ENABLED is false"
            )

        window_start, window_end = _coerce_utc(start), _coerce_utc(end)
        if date is not None:
            window_start, window_end = _day_bounds(date)

        with self._lock:
            reload = bool(
                symbols is not None
                or date is not None
                or start is not None
                or end is not None
                or limit is not None
                or not self._events
            )
            if self._state in (
                ReplayState.RUNNING,
                ReplayState.PAUSED,
            ):
                raise ReplayBlockedError(
                    ReplayError.ALREADY_RUNNING,
                    detail=f"run is {self._state.value}; stop() or pause() first",
                )

        if speed is not None:
            self.set_speed(speed)

        if reload:
            self.load(
                symbols,
                limit=limit,
                start=window_start,
                end=window_end,
                anchor_prices=anchor_prices,
            )

        with self._cond:
            self._halt = False
            self._finished_at = None
            self._state = ReplayState.RUNNING
            self._started_at = self._started_at or self._wall_clock()
            if not self._clock.manual and self._autostart:
                self._ensure_driver_locked()
            self._cond.notify_all()
            return self._run

    def pause(self) -> ReplayState:
        """Halt automatic advance (§4).  ``step()`` still works (§7)."""
        with self._cond:
            if self._state is not ReplayState.RUNNING:
                raise ReplayBlockedError(
                    ReplayError.NOT_READY,
                    detail=f"cannot pause from {self._state.value}",
                )
            self._state = ReplayState.PAUSED
            self._cond.notify_all()
            return self._state

    def resume(self) -> ReplayState:
        """Resume automatic advance."""
        with self._cond:
            if self._state is not ReplayState.PAUSED:
                raise ReplayBlockedError(
                    ReplayError.NOT_READY,
                    detail=f"cannot resume from {self._state.value}",
                )
            self._halt = False
            self._state = ReplayState.RUNNING
            if not self._clock.manual and self._autostart:
                self._ensure_driver_locked()
            self._cond.notify_all()
            return self._state

    def stop(self) -> ReplayState:
        """Terminate the run early (§4).  ``STARTED`` → ``STOPPED``.

        A stopped run is over: ``step()`` yields nothing and only
        ``reset()`` + ``load()`` (or ``seek()`` back) can revive it.
        """
        with self._cond:
            if self._state in (ReplayState.IDLE, ReplayState.COMPLETED):
                raise ReplayBlockedError(
                    ReplayError.NOT_READY,
                    detail=f"cannot stop from {self._state.value}",
                )
            self._halt = True
            self._state = ReplayState.STOPPED
            self._finished_at = self._finished_at or self._wall_clock()
            self._cond.notify_all()
            return self._state

    def reset(self) -> None:
        """Drop the timeline and return to IDLE (§20)."""
        with self._cond:
            self._halt = True
            self._events = []
            self._cursor = 0
            self._state = ReplayState.IDLE
            self._thread = None
            self._started_at = None
            self._finished_at = None
            self._clock.reset()
            self._stats["resets"] += 1
            self._cond.notify_all()

    def set_speed(self, speed: float) -> float:
        """Change the §6 replay speed (0 = manual step mode)."""
        try:
            return self._clock.set_speed(speed)
        except ValueError as exc:
            raise ReplayBlockedError(
                ReplayError.INVALID_SPEED, detail=str(exc)
            ) from exc

    def seek(self, timestamp: object) -> int:
        """Move the playback cursor to the first event at/after ``timestamp``.

        Seeking back into a finished run puts it in ``PAUSED`` rather
        than ``RUNNING``: rewinding is an inspection action, and
        silently restarting a driver after a ``COMPLETED`` run would be a
        surprising way to spend CPU.  Returns the new event index.
        """
        target = _coerce_utc(timestamp)
        if target is None:
            raise ReplayBlockedError(
                ReplayError.INVALID_WINDOW, detail="seek needs a timestamp"
            )
        with self._cond:
            if not self._events:
                raise ReplayBlockedError(
                    ReplayError.NOT_READY, detail="nothing loaded to seek in"
                )
            index = len(self._events)
            for position, event in enumerate(self._events):
                if event.timestamp >= target:
                    index = position
                    break
            self._cursor = index
            anchor = (
                self._events[index].timestamp
                if index < len(self._events)
                else self._events[-1].timestamp
            )
            self._clock.set_now(anchor)
            self._finished_at = None
            if self._state in (ReplayState.COMPLETED, ReplayState.STOPPED):
                self._halt = True
                self._state = ReplayState.PAUSED
            self._stats["seeks"] += 1
            self._cond.notify_all()
            return index

    # ── stepping (§4 / §7) ───────────────────────────────────────

    def step(self) -> Optional[ReplayEvent]:
        """Emit the next event, or ``None`` once the run is over.

        Works in RUNNING *and* PAUSED — pausing stops the *automatic*
        driver, it does not forbid manual inspection (§7).  Pacing is
        applied, so a single ``step()`` in 10x mode waits the equivalent
        of one minute per ten.
        """
        with self._lock:
            if not self._events:
                raise ReplayBlockedError(
                    ReplayError.NOT_READY, detail="call load()/start() first"
                )
            if self._state is ReplayState.ERROR:
                raise ReplayBlockedError(
                    ReplayError.TERMINATED,
                    detail=self._last_error or "run is in ERROR",
                )
            event = self._emit_locked()
            if event is None:
                return None
            self._started_at = self._started_at or self._wall_clock()
            delay = self._clock.advance_to(event.timestamp)

        # Pace outside the lock: holding it across the wait would make
        # status()/pause() unresponsive for the length of the wait (§4).
        self._clock.sleep(delay)
        return event

    def frames(self) -> Iterator[ReplayEvent]:
        """Yield events in order, honouring pacing (§6)."""
        while True:
            event = self.step()
            if event is None:
                return
            yield event

    def drain(self) -> list[ReplayEvent]:
        """Emit everything remaining, **unpaced**.

        This is the deterministic driver used by the test gate and the
        §28 E2E: pacing is a delivery concern, and a gate that had to
        sleep would be a gate nobody runs.
        """
        out: list[ReplayEvent] = []
        with self._lock:
            if not self._events:
                raise ReplayBlockedError(
                    ReplayError.NOT_READY, detail="call load()/start() first"
                )
            while True:
                event = self._emit_locked()
                if event is None:
                    break
                self._clock.set_now(event.timestamp)
                out.append(event)
            self._started_at = self._started_at or self._wall_clock()
        return out

    def current(self, symbol: Optional[str] = None) -> Optional[ReplayEvent]:
        """The most recently emitted event (§17 — Paper's "latest").

        This is what a replay-backed market feed answers ``latest()``
        with: the newest instant the system is allowed to know about.
        It never looks past the cursor, so it cannot leak the next
        minute into a decision (§26).
        """
        with self._lock:
            for index in range(self._cursor - 1, -1, -1):
                event = self._events[index]
                if symbol is None or event.symbol == symbol:
                    return event
            return None

    def emitted(
        self, symbol: Optional[str] = None, limit: Optional[int] = None
    ) -> list[ReplayEvent]:
        """Events already emitted (oldest first), optionally one symbol.

        This is the replay-backed bar view: it answers Paper Trading's
        ``bars()`` without ever exposing an instant the replay has not
        reached, because the cursor *is* the lookahead boundary (§26).
        """
        with self._lock:
            out = [
                event
                for event in self._events[: self._cursor]
                if symbol is None or event.symbol == symbol
            ]
        if limit is not None and limit > 0:
            return out[-int(limit):]
        return out

    # ── serialisation (§20 / §21 / §24) ──────────────────────────
    def status(self) -> dict:
        """§20 state payload — what the Dashboard renders (§21)."""
        with self._lock:
            run = self._run
            total = len(self._events)
            processed = self._cursor
            current = self._clock.now
            return {
                "state": self._state.value,
                "replay_id": run.replay_id if run else None,
                "trading_date": (
                    self._trading_date(current)
                    if current is not None
                    else (run.trading_date if run else None)
                ),
                "current_timestamp": (
                    current.isoformat() if current is not None else None
                ),
                "speed": self._clock.speed,
                "mode": self._mode_label(),
                "manual": self._clock.manual,
                "events_processed": processed,
                "events_total": total,
                "progress_pct": (
                    round(processed / total * 100, 2) if total else 0.0
                ),
                "symbols": list(run.symbols) if run else [],
                "timeframe": self._cfg.timeframe,
                "window_start": (
                    run.window_start.isoformat()
                    if run and run.window_start
                    else None
                ),
                "window_end": (
                    run.window_end.isoformat()
                    if run and run.window_end
                    else None
                ),
                "events_quarantined": run.events_quarantined if run else 0,
                "duplicates": run.duplicates if run else 0,
                "gaps": run.gaps if run else 0,
                "session_breaks": run.session_breaks if run else 0,
                "digest": run.digest if run else "",
                "clock_slept_s": round(self._clock.slept_seconds, 3),
                "clock_skipped_s": round(self._clock.skipped_seconds, 3),
                "last_error": self._last_error,
                "config": self._cfg.as_dict(),
                "run": run.as_dict() if run else None,
            }

    def audit(self) -> Optional[dict]:
        """§24 replay audit record (plan + outcome)."""
        with self._lock:
            if self._run is None:
                return None
            record = replace(
                self._run,
                events_processed=self._cursor,
                completed=self._state is ReplayState.COMPLETED,
                status=self._state.value,
                started_at=self._started_at,
                finished_at=self._finished_at,
                speed=self._clock.speed,
                mode=self._mode_label(),
            )
            return record.as_dict()

    def events(self, limit: Optional[int] = None) -> list[dict]:
        """Loaded timeline as plain dicts (capped) for API/UI previews."""
        cap = limit or self._cfg.max_limit
        with self._lock:
            return [e.as_dict() for e in self._events[: max(1, cap)]]

    def stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def as_dict(self) -> dict:
        """Full snapshot: §20 status + audit + counters."""
        return {
            "status": self.status(),
            "audit": self.audit(),
            "stats": self.stats(),
        }

    # ── internals ────────────────────────────────────────────────

    def _emit_locked(self) -> Optional[ReplayEvent]:
        """Advance the cursor by one.  Caller holds the lock.

        ``IDLE`` is allowed to emit: §20 has no separate "loaded but not
        started" state, so a freshly loaded window is IDLE and the §7
        manual workflow (``load`` → ``step`` → ``step``…) must work
        without a ``start()`` in between.  The "is there anything to
        replay" question is answered by the callers, which check
        ``_events`` before calling in.
        """
        if self._state in (
            ReplayState.COMPLETED,
            ReplayState.STOPPED,
            ReplayState.ERROR,
        ):
            return None
        if self._cursor >= len(self._events):
            self._complete_locked()
            return None

        event = self._events[self._cursor]
        self._cursor += 1
        # Promote IDLE → RUNNING on the first emit, but never downgrade
        # PAUSED: a manual step() taken while paused is an inspection
        # action, and flipping to RUNNING would silently let the driver
        # thread resume a run the operator deliberately halted.
        if self._state is ReplayState.IDLE:
            self._state = ReplayState.RUNNING
        self._stats["events_emitted"] += 1
        if self._cursor >= len(self._events):
            self._complete_locked()
        return event

    def _complete_locked(self) -> None:
        self._state = ReplayState.COMPLETED
        self._finished_at = self._finished_at or self._wall_clock()
        self._halt = True
        self._cond.notify_all()

    def _fail(self, detail: str) -> None:
        self._state = ReplayState.ERROR
        self._last_error = detail
        self._halt = True

    def _ensure_driver_locked(self) -> None:
        """Start the background pacing thread (auto modes only)."""
        if self._thread is not None and self._thread.is_alive():
            return
        thread = threading.Thread(
            target=self._drive,
            name="replay-driver",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def _drive(self) -> None:
        """Background loop: emit + pace until paused, stopped or done."""
        while True:
            with self._cond:
                while (
                    self._state is ReplayState.PAUSED and not self._halt
                ):
                    self._cond.wait(timeout=0.2)
                if self._halt or self._state is not ReplayState.RUNNING:
                    return
            try:
                if self.step() is None:
                    return
            except ReplayBlockedError:
                logger.exception("replay driver stopped on a block")
                return
            except Exception as exc:  # noqa: BLE001 — never die silently
                with self._lock:
                    self._fail(str(exc))
                logger.exception("replay driver failed")
                return

    def _event_delta(self) -> timedelta:
        return _EVENT_DELTA.get(self._cfg.timeframe, timedelta(minutes=1))

    def _mode_label(self) -> str:
        return "MANUAL" if self._clock.manual else "AUTO"

    def _replay_id(self, symbols: list[str], first: datetime) -> str:
        """``replay-20260910-159852-001`` (§24)."""
        scope = symbols[0] if len(symbols) == 1 else "multi"
        return f"replay-{first:%Y%m%d}-{scope}-{self._load_seq:03d}"

    def _trading_date(self, ts: Optional[datetime]) -> Optional[str]:
        if ts is None:
            return None
        try:
            return self._cal.trading_date_of(ts).isoformat()
        except Exception:  # noqa: BLE001 — decoration, not a gate
            return None

    def _phase_of(self, ts: datetime) -> str:
        try:
            return self._cal.get_phase(ts).value
        except Exception:  # noqa: BLE001
            return ""

    def _bar_quality(self, bar: Bar) -> dict:
        """006 verdict, carried on the event so consumers see the gate."""
        if not self._cfg.enforce_quality:
            return {}
        try:
            return validate_bar(bar).as_dict()
        except Exception:  # noqa: BLE001
            return {}

    def _normalise_symbols(
        self, symbols: Optional[list[str]]
    ) -> list[str]:
        """De-duplicate (order-preserving) and gate unknown symbols."""
        if symbols is None:
            raw = [i.symbol for i in self._instruments.enabled()]
            if not raw:
                raw = list(self._instruments.symbols())
        elif isinstance(symbols, str):
            raw = [symbols]
        else:
            raw = [str(s) for s in symbols]

        ordered: list[str] = []
        seen: set[str] = set()
        for symbol in raw:
            code = str(symbol).strip()
            if not code or code in seen:
                continue
            if not self._cfg.allow_unknown and not self._instruments.contains(
                code
            ):
                raise ReplayBlockedError(
                    ReplayError.UNKNOWN_SYMBOL,
                    symbol=code,
                    detail="not in the instrument master (Commit 002)",
                )
            seen.add(code)
            ordered.append(code)

        if not ordered:
            raise ReplayBlockedError(
                ReplayError.NO_DATA, detail="no symbols requested"
            )
        return ordered

    def _quarantine_reason(
        self,
        bar: Bar,
        instrument: object,
        delta: timedelta,
        wall_now: datetime,
    ) -> Optional[ReplayError]:
        """§15 quarantine rules — returns the reason, or ``None`` to replay.

        Ordered cheapest-and-most-fundamental first so the reported
        reason is the *root* cause, not a downstream symptom.
        """
        if not bar.is_closed:
            return ReplayError.INCOMPLETE_BAR
        if instrument is not None:
            exchange = getattr(instrument, "exchange", None)
            if exchange is not None and bar.exchange != exchange:
                return ReplayError.EXCHANGE_MISMATCH
        if self._cfg.enforce_calendar and not self._cal.is_bar_phase(
            bar.timestamp
        ):
            return ReplayError.CALENDAR_VIOLATION
        if self._cfg.strict_junction and (bar.timestamp + delta) > wall_now:
            return ReplayError.JUNCTION_VIOLATION
        if self._cfg.enforce_quality:
            try:
                verdict = validate_bar(bar)
            except Exception:  # noqa: BLE001 — a broken check is a finding
                return ReplayError.INVALID_BAR
            if not verdict.valid:
                return ReplayError.INVALID_BAR
        return None

    @staticmethod
    def _quality_detail(bar: Bar, reason: ReplayError) -> str:
        if reason is not ReplayError.INVALID_BAR:
            return ""
        try:
            return ",".join(validate_bar(bar).reasons)
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _rejection(
        bar: Bar, reason: ReplayError, *, detail: str = ""
    ) -> dict:
        return {
            "symbol": bar.symbol,
            "bar_id": bar.bar_id,
            "timestamp": bar.timestamp.isoformat(),
            "reason": reason.value,
            "detail": detail,
        }

    def _annotate(
        self, events: list[ReplayEvent], delta: timedelta
    ) -> tuple[list[ReplayEvent], int, int]:
        """Assign ``sequence`` and flag discontinuities (§9 / §14 / §16).

        A discontinuity is a **session break** when the previous event's
        boundary is not itself a bar phase (lunch, overnight); otherwise
        it is a genuine **data gap**.  Both are flagged, neither is
        filled — replaying a fabricated 10:34 would stop this from being
        a replay at all.
        """
        gaps = 0
        breaks = 0
        previous: Optional[ReplayEvent] = None
        out: list[ReplayEvent] = []

        for index, event in enumerate(events):
            gap_before = False
            crosses = False
            if previous is not None and previous.symbol == event.symbol:
                if event.data.timestamp != previous.timestamp:
                    gap_before = True
                    if self._cal.is_bar_phase(previous.timestamp):
                        gaps += 1
                    else:
                        crosses = True
                        breaks += 1
            out.append(
                replace(
                    event,
                    sequence=index,
                    gap_before=gap_before,
                    crosses_session=crosses,
                )
            )
            previous = out[-1]

        return out, gaps, breaks


# ── Singleton ─────────────────────────────────────────────────────
replay_engine = ReplayEngine()

__all__ = ["ReplayEngine", "replay_engine"]
