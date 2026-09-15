"""Replay clock — the virtual trading clock (Commit 012 §5 / §6 / §7).

The single most important rule in Commit 012:

    **Replay time and real time must be completely separated.**

Nothing inside a replay may consult ``datetime.now()``.  If it did, the
same window would replay differently on every run and the whole
determinism guarantee (§25) would evaporate.

So this module is the *only* place that knows about both clocks::

    virtual clock  ──  ReplayClock.now      ── what the system believes
    wall clock     ──  ReplayClock.advance_to ── how long to wait (pace)

``now`` returns the timestamp of the last event the engine made
knowable, and never touches the wall clock.  ``advance_to`` is the only
method that calls the injected sleeper, and it exists purely to *pace*
delivery (§6) — it can slow a replay down, never change its content.

Speed semantics (§6 / §7)::

    speed = 0     manual / step mode — no automatic advance at all
    speed = 1     real time (1 historical second per real second)
    speed = 10    10 historical seconds per real second
    speed = 100   100 historical seconds per real second

``0`` being *manual* rather than *infinitely fast* is deliberate: §7
wants a debug mode where one STEP yields exactly one event, which is how
you walk ``Quote → Signal → Order → Fill`` one line at a time.

§14 session boundary
--------------------

A replayed series jumps 11:30 → 13:00.  Realtime pacing would then sleep
through the lunch break.  ``max_sleep_seconds`` clamps a single sleep so
an API thread cannot block for hours; the skipped time is *counted* in
``skipped_seconds`` and surfaced in ``status()``, so the distortion is
visible rather than silent.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional


class ReplayClock:
    """Virtual clock with wall-clock pacing (§5)."""

    # §6 — the speeds the engine accepts.  A whitelist, not a range:
    # "10.37x" is not a replay speed anyone asked to support.
    ALLOWED_SPEEDS: tuple[float, ...] = (0.0, 0.1, 1.0, 2.0, 10.0, 50.0, 100.0)

    def __init__(
        self,
        *,
        speed: float = 1.0,
        sleeper: Optional[Callable[[float], None]] = None,
        max_sleep_seconds: float = 60.0,
    ) -> None:
        self._sleeper = sleeper or time.sleep
        self._max_sleep = max(0.0, float(max_sleep_seconds))
        self._now: Optional[datetime] = None
        self._skipped = 0.0
        self._paced = 0.0
        self._speed = 1.0
        self.set_speed(speed)

    # ── speed (§6 / §7) ──────────────────────────────────────────

    @classmethod
    def allowed_speeds(cls) -> tuple[float, ...]:
        return cls.ALLOWED_SPEEDS

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def manual(self) -> bool:
        """True in STEP mode — the clock never advances on its own (§7)."""
        return self._speed == 0.0

    def set_speed(self, speed: float) -> float:
        """Set the replay speed; returns the resolved value.

        Raises ``ValueError`` for anything outside
        :attr:`ALLOWED_SPEEDS` so a typo cannot silently become a
        1000x replay.
        """
        value = float(speed)
        if value not in self.ALLOWED_SPEEDS:
            raise ValueError(
                f"unsupported replay speed {value!r}; "
                f"allowed: {list(self.ALLOWED_SPEEDS)}"
            )
        self._speed = value
        return value

    # ── virtual time (§5) ────────────────────────────────────────

    @property
    def now(self) -> Optional[datetime]:
        """Virtual time — the last knowable instant (never wall clock)."""
        return self._now

    @property
    def running(self) -> bool:
        return self._now is not None

    @property
    def slept_seconds(self) -> float:
        """Real seconds actually spent pacing."""
        return self._paced

    @property
    def skipped_seconds(self) -> float:
        """Real seconds a clamp avoided sleeping (§14 honesty)."""
        return self._skipped

    def set_now(self, timestamp: datetime) -> None:
        """Jump the virtual clock (``seek``) without pacing."""
        self._now = timestamp

    def reset(self) -> None:
        self._now = None
        self._paced = 0.0
        self._skipped = 0.0

    def advance_to(self, timestamp: datetime) -> float:
        """Move the virtual clock and return the real seconds to wait.

        Deliberately **does not sleep**: the engine calls this while
        holding its state lock (so ``status()`` / ``pause()`` always see
        a consistent virtual time) and then sleeps *outside* the lock.
        Holding a lock across a paced wait would make ``pause()``
        unresponsive for as long as the wait lasts.

        Returns 0.0 in manual mode, and on the first call — replaying to
        the very first event is instantaneous because no virtual time
        has elapsed yet.
        """
        previous = self._now
        self._now = timestamp
        if previous is None or self.manual:
            return 0.0

        virtual = (timestamp - previous).total_seconds()
        if virtual <= 0:
            return 0.0

        delay = virtual / self._speed
        if delay <= 0:
            return 0.0
        if self._max_sleep and delay > self._max_sleep:
            # §14 — a session break (or an overnight gap) must not pin a
            # thread for hours; we skip the wait and record the loss.
            self._skipped += delay - self._max_sleep
            delay = self._max_sleep
        return delay

    def sleep(self, seconds: float) -> float:
        """Actually wait ``seconds`` on the injected sleeper."""
        if seconds <= 0:
            return 0.0
        self._sleeper(seconds)
        self._paced += seconds
        return seconds

    def pace_to(self, timestamp: datetime) -> float:
        """:meth:`advance_to` + :meth:`sleep` (single-threaded callers)."""
        return self.sleep(self.advance_to(timestamp))


__all__ = ["ReplayClock"]
