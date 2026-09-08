"""1m Bar quality validation (Commit 006).

Not only quotes pass through the Quality Gate — Commit 004's bars
do too.  A structurally valid bar must satisfy::

    High >= max(Open, Close)
    Low  <= min(Open, Close)
    High >= Low
    Volume >= 0

Gap detection itself (which minutes should have had a bar) already
lives in the BarAggregator with the Commit 005 session-aware gap
filter — lunch breaks are never gaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.bar import Bar


@dataclass(frozen=True)
class BarQuality:
    """Quality verdict for one bar."""

    valid: bool
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "reasons": list(self.reasons),
        }


def validate_bar(bar: Bar) -> BarQuality:
    """Structural OHLCV consistency check.  Marks, never modifies."""
    reasons: list[str] = []

    if bar.high < bar.low:
        reasons.append("HIGH_LT_LOW")
    if bar.high < max(bar.open, bar.close):
        reasons.append("HIGH_LT_MAX_OC")
    if bar.low > min(bar.open, bar.close):
        reasons.append("LOW_GT_MIN_OC")
    if bar.volume < 0:
        reasons.append("NEGATIVE_VOLUME")
    if bar.open < 0 or bar.close < 0:
        reasons.append("NEGATIVE_PRICE")
    if bar.turnover < 0:
        reasons.append("NEGATIVE_TURNOVER")

    return BarQuality(valid=not reasons, reasons=reasons)


__all__ = ["BarQuality", "validate_bar"]
