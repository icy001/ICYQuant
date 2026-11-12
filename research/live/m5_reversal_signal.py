# -*- coding: utf-8 -*-
"""M5 reversal signal generator — bit-exact replica of the canonical
exp04 H12_down machinery, for live shadow trading.

Canonical mechanics (from exp04_breakout_continuation.py, traded as
reversal per exp07/exp14b):

    signal bar i (completed M5, Beijing time):
        down breakout := close[i] < min(low[i-12 .. i-1])   (strict <)
    entry  : open of bar i+1          (the NEXT bar)
    exit   : close of bar i+12        (H = 12 bars = 1 hour)
    trade  : LONG (opposite of the down breakout; gross = -ret_12)
    nonoverlap: greedy — next signal only at bar_i >= last_signal + 12

Gap rules (identical to the backtest):
    * lookback window [i-12, i] must contain no time gap
    * if a gap occurs inside the holding window live, the trade is flagged
      (in the backtest such trades were excluded a priori; live you must
      decide — flagging is honest, hiding is not)

Validated bit-exact against artifacts/research/eurusd_breakout/
exp04_events.csv (see tests/research/test_m5_reversal_signal.py).

The class is pure: feed it completed M5 bars one at a time, it emits
Signal objects. No IO, no clock, no broker dependency.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

LOOKBACK = 12          # bars, excluding the signal bar itself
HOLD = 12              # bars = 1 hour at M5
BAR_MINUTES = 5


@dataclass(frozen=True)
class Bar:
    """One completed M5 bar, timestamps in Beijing time."""
    ts: datetime       # bar open time (Beijing)
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Signal:
    """A live tradable signal (H12_down: long after a down breakout)."""
    signal_bar_ts: datetime   # Beijing time of the signal bar (bar open)
    direction: str            # always "long" for the canonical config
    reason: str


class M5ReversalSignal:
    """Bar-by-bar replica of exp04 H12_down nonoverlap selection."""

    def __init__(self, can_hold=None) -> None:
        """can_hold(signal_bar_ts) -> bool, optional.

        The backtest drops any trade whose 12-bar holding window contains a
        gap (valid_12). Live you cannot know a gap in advance, but the
        dominant gap — the weekend close — is predictable. Pass a callback
        returning False when the holding window would cross the weekend
        close (or any scheduled halt) to mirror the backtest gate.
        """
        self._bars: deque[Bar] = deque(maxlen=LOOKBACK)
        self._last_signal_bar_index: int = -10**9
        self._bar_index: int = -1
        self._prev_ts: Optional[datetime] = None
        self._can_hold = can_hold

    # ------------------------------------------------------------------
    def _gap_before(self, ts: datetime) -> bool:
        """True if the step from the previous bar to ts is not 5 minutes."""
        if self._prev_ts is None:
            return False
        delta = (ts - self._prev_ts).total_seconds()
        return abs(delta - BAR_MINUTES * 60) > 1e-9

    def update(self, bar: Bar) -> Optional[Signal]:
        """Feed one completed M5 bar (Beijing time). Returns a Signal if the
        canonical down-breakout + nonoverlap conditions are met, else None.

        Gaps reset state: a lookback window containing a gap is invalid in
        the backtest, so after any gap the deque restarts from scratch.
        """
        self._bar_index += 1
        if self._gap_before(bar.ts):
            self._bars.clear()                      # gap -> window invalid
            # backtest also required [i, i+H] gap-free; signalled trades
            # spanning the gap are flagged downstream, not suppressed here
        self._prev_ts = bar.ts

        if len(self._bars) < LOOKBACK:
            self._bars.append(bar)
            return None

        # exp04: close[i] < min(low[i-12 .. i-1]), strictly
        boundary = min(b.low for b in self._bars)
        nonoverlap_ok = (self._bar_index >=
                         self._last_signal_bar_index + HOLD)
        holdable = self._can_hold(bar.ts) if self._can_hold else True
        sig = None
        if bar.close < boundary and nonoverlap_ok and holdable:
            sig = Signal(signal_bar_ts=bar.ts, direction="long",
                         reason=(f"close {bar.close:.5f} < "
                                 f"12-bar low {boundary:.5f}"))
            self._last_signal_bar_index = self._bar_index

        self._bars.append(bar)
        return sig
