"""Train / Validation / OOS split for Discovery Lab v1.

The split is the *most important isolation rule* of the Discovery Lab:

    Historical Data -> [Train] -> Strategy Search -> [Validation] -> Robustness
    -> [OOS] -> Candidate

OOS bars are forbidden during parameter selection.  This module exposes the
sealed boundaries (from ``spec.SPLIT_CONFIG``) and pure slicing helpers so no
other module can accidentally leak OOS data into Train/Validation.

Walk-Forward windows are built **inside Train + Validation only** — the final
OOS segment is never touched by walk-forward.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from ..data.bar import Bar
from .spec import SPLIT_CONFIG, IDEAL_SPLIT

# Segment names
SEGMENT_TRAIN = "train"
SEGMENT_VALIDATION = "validation"
SEGMENT_OOS = "oos"


def _to_date(value: str) -> date:
    """'YYYY-MM-DD' -> date (also accepts datetime)."""
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


@dataclass(frozen=True)
class TimeSplit:
    """One sealed train/validation/oos split for a given dataset range."""

    name: str
    train_start: date
    train_end: date
    val_start: date
    val_end: date
    oos_start: date
    oos_end: date
    note: str = ""

    # ------------------------------------------------------------------ #
    @property
    def spans(self) -> dict[str, tuple[date, date]]:
        return {
            SEGMENT_TRAIN: (self.train_start, self.train_end),
            SEGMENT_VALIDATION: (self.val_start, self.val_end),
            SEGMENT_OOS: (self.oos_start, self.oos_end),
        }

    def segment_for(self, ts: datetime | date) -> Optional[str]:
        """Return the segment a timestamp belongs to, or None if out of range."""
        d = ts.date() if isinstance(ts, datetime) else ts
        if self.train_start <= d <= self.train_end:
            return SEGMENT_TRAIN
        if self.val_start <= d <= self.val_end:
            return SEGMENT_VALIDATION
        if self.oos_start <= d <= self.oos_end:
            return SEGMENT_OOS
        return None

    def in_oos(self, ts: datetime | date) -> bool:
        return self.segment_for(ts) == SEGMENT_OOS

    def slice_bars(self, bars: list[Bar], segment: str) -> list[Bar]:
        """Return the subset of bars strictly inside the given segment.

        Bars are timestamped datetimes; a bar whose timestamp falls within
        [start, end] belongs to the segment.
        """
        if not bars:
            return []
        start, end = self.spans[segment]
        out = [b for b in bars
               if start <= b.timestamp.date() <= end]
        # keep chronological order
        out.sort(key=lambda b: b.timestamp)
        return out

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "train": [self.train_start.isoformat(), self.train_end.isoformat()],
            "validation": [self.val_start.isoformat(), self.val_end.isoformat()],
            "oos": [self.oos_start.isoformat(), self.oos_end.isoformat()],
            "note": self.note,
        }


def build_split(cfg: dict[str, dict[str, str]]) -> TimeSplit:
    """Build a TimeSplit from a spec-style config dict."""
    return TimeSplit(
        name=cfg["name"],
        train_start=_to_date(cfg["train"]["start"]),
        train_end=_to_date(cfg["train"]["end"]),
        val_start=_to_date(cfg["validation"]["start"]),
        val_end=_to_date(cfg["validation"]["end"]),
        oos_start=_to_date(cfg["oos"]["start"]),
        oos_end=_to_date(cfg["oos"]["end"]),
        note=cfg.get("note", ""),
    )


# --------------------------------------------------------------------------- #
# Walk-Forward windows (fixed parameters, inside Train + Validation only)      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class WalkForwardWindow:
    """One rolling window: in-sample (fit) + out-of-sample (check).

    v1 uses *fixed* candidate parameters across windows — walk-forward here is a
    regime-stability check, not a re-optimisation loop (no OOS leakage: the
    final OOS segment is never part of any window).
    """

    index: int
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date

    def oos_bars(self, bars: list[Bar]) -> list[Bar]:
        return [b for b in bars if self.oos_start <= b.timestamp.date() <= self.oos_end]


def build_walk_forward_windows(
    split: TimeSplit,
    is_months: int = 6,
    oos_months: int = 2,
    step_months: int = 3,
    max_windows: int = 6,
) -> list[WalkForwardWindow]:
    """Build rolling windows over [train_start, val_end] (OOS excluded).

    Each window has an in-sample fit period (``is_months``) followed by an
    out-of-sample check period (``oos_months``); windows step by
    ``step_months``.  Only windows whose OOS segment is fully inside
    [train_start, val_end] are emitted.
    """
    anchor_start = split.train_start
    anchor_end = split.val_end
    windows: list[WalkForwardWindow] = []

    def _shift(d: date, months: int) -> date:
        idx = d.year * 12 + (d.month - 1) + months
        y, m0 = divmod(idx, 12)
        m = m0 + 1
        day = min(d.day, 28)
        return date(y, m, day)

    start = anchor_start
    while len(windows) < max_windows:
        is_end = _shift(start, is_months)
        oos_end = _shift(is_end, oos_months)
        if oos_end > anchor_end:
            break
        windows.append(WalkForwardWindow(
            index=len(windows) + 1,
            is_start=start,
            is_end=is_end,
            oos_start=_shift(is_end, 1),   # first day after fit period
            oos_end=oos_end,
        ))
        start = _shift(start, step_months)
    return windows


# --------------------------------------------------------------------------- #
# Sealed split registry                                                       #
# --------------------------------------------------------------------------- #
SPLITS: dict[str, TimeSplit] = {
    SPLIT_CONFIG["name"]: build_split(SPLIT_CONFIG),
    IDEAL_SPLIT["name"]: build_split(IDEAL_SPLIT),
}

# Active split for v1 (adapt when the dataset reaches >= 6y).
ACTIVE_SPLIT = SPLITS[SPLIT_CONFIG["name"]]
