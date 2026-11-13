# -*- coding: utf-8 -*-
"""FX market calendar (Beijing time) for the live shadow runner.

Rules measured from 26 years of EURUSD feed data (see
tests/research/test_m5_reversal_signal.py for the validation harness):

* Weekend close: NY Friday 17:00 = Saturday 05:00 (EDT) / 06:00 (EST)
  Beijing. Conservative cutoff: Saturday 04:00.
* Weekly reopen: Monday ~06:00 Beijing.
* Recurring halts: Christmas (12-25) and New Year (01-01), with the halt
  treated as starting the prior evening 22:00.

Feed holes shorter than a structural gap are NOT predictable here; the
runner detects them at runtime.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

HOLD_MINUTES = 60          # 12 M5 bars


def is_fx_closed(t: datetime) -> bool:
    """FX market closed at Beijing time t (weekend + recurring halts)."""
    wd, tm = t.weekday(), t.time()
    md = (t.month, t.day)
    if md in ((12, 25), (1, 1)):
        return True
    if md in ((12, 24), (12, 31)) and tm >= dtime(22, 0):
        return True
    if md in ((12, 26), (1, 2)) and tm < dtime(6, 0):
        return True
    if wd == 5 and tm >= dtime(4, 0):
        return True
    if wd == 6:
        return True
    if wd == 0 and tm < dtime(6, 0):
        return True
    return False


def can_hold(signal_ts: datetime, hold_minutes: int = HOLD_MINUTES) -> bool:
    """True iff no closed moment inside [signal_ts, signal_ts + hold + 5min].

    Mirrors the backtest's valid_12 holding-window gate for every
    *predictable* closure (weekend + recurring halts).
    """
    probe = signal_ts
    end = signal_ts + timedelta(minutes=hold_minutes + 5)
    step = timedelta(minutes=5)
    while probe <= end:
        if is_fx_closed(probe):
            return False
        probe += step
    return True
