from typing import Dict, Any, Iterable, List, Optional, Sequence, Tuple
from datetime import datetime

from .exceptions import DataFormatError


def validate_bar_data(row: Dict[str, Any], required_columns: set = None) -> None:
    if required_columns is None:
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}

    missing = required_columns - set(row.keys())
    if missing:
        raise DataFormatError(f"Missing columns: {missing}")

    for col in ["open", "high", "low", "close", "volume"]:
        value = row.get(col)
        if value is None:
            raise DataFormatError(f"Missing value for {col}")
        try:
            float(value)
        except (ValueError, TypeError):
            raise DataFormatError(f"Invalid numeric value for {col}: {value}")

    timestamp = row.get("timestamp")
    if timestamp is None:
        raise DataFormatError("Missing timestamp")
    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        raise DataFormatError(f"Invalid timestamp format: {timestamp}")


def validate_ohlc_consistency(open_price: float, high: float, low: float, close: float) -> None:
    if high < low:
        raise DataFormatError(f"High ({high}) cannot be less than low ({low})")
    if open_price < low or open_price > high:
        raise DataFormatError(f"Open ({open_price}) outside range [{low}, {high}]")
    if close < low or close > high:
        raise DataFormatError(f"Close ({close}) outside range [{low}, {high}]")


# ---------------------------------------------------------------------------
# Price plausibility checks
#
# The two checks above are per-bar and only enforce internal consistency.
# A corrupt tick satisfies both: if a whole bar arrives as 1965.0001 for
# EURUSD, then high >= low and open/close sit inside [low, high] -- it is a
# perfectly well-formed bar that happens to be an impossible price.
#
# This actually happened in this repository. A single bar in the HistData
# M1 feed (2001-06-08 07:30, close=1965.0001, while EURUSD traded 0.82-1.60)
# produced one -19.6 million pip "trade" and made a momentum backtest report
# -1.27 million pips per year. One bad value, one fabricated conclusion.
#
# The functions below close that gap. They are deliberately separate from the
# exception-raising checks: when cleaning a dataset you want the list of
# offending rows, not the first one to abort the run.
# ---------------------------------------------------------------------------

# Widely-used sanity bands. Callers should pass explicit bounds for
# instruments whose history genuinely falls outside these, rather than
# loosening the default for everyone.
DEFAULT_PRICE_BOUNDS: dict[str, Tuple[float, float]] = {
    "EURUSD": (0.5, 2.0),
    "GBPUSD": (0.5, 3.0),
    "USDJPY": (50.0, 400.0),
}

# A move this large between adjacent bars is almost always a data error,
# not a market event. Two real moves bracket the choice: the 2015-01-15
# CHF de-peg was about 30% in minutes, and EURUSD has never moved >10%
# intraday. Set per-instrument when a market is genuinely that volatile.
DEFAULT_MAX_JUMP_PCT = 0.10


def validate_price_range(
    prices: Iterable[float],
    bounds: Tuple[float, float] = (0.0, float("inf")),
    *,
    raise_on_error: bool = False,
) -> List[int]:
    """Return positional indices of prices outside ``bounds``.

    ``bounds`` is inclusive. Passing the wrong band silently rejects good
    data, so prefer an instrument-specific band (see DEFAULT_PRICE_BOUNDS)
    over a hard-coded pair.
    """
    lo, hi = bounds
    bad: List[int] = []
    for i, px in enumerate(prices):
        try:
            v = float(px)
        except (TypeError, ValueError):
            bad.append(i)
            continue
        if v != v:  # NaN
            bad.append(i)
            continue
        if v < lo or v > hi:
            bad.append(i)

    if bad and raise_on_error:
        raise DataFormatError(
            f"{len(bad)} price(s) outside [{lo}, {hi}], first at index {bad[0]}"
        )
    return bad


def validate_price_jumps(
    prices: Sequence[float],
    max_jump_pct: float = DEFAULT_MAX_JUMP_PCT,
    *,
    raise_on_error: bool = False,
) -> List[int]:
    """Return indices ``i`` where ``prices[i]`` moves > max_jump_pct from ``prices[i-1]``.

    Catches a corrupt bar even when the corrupt value happens to fall inside
    a generous price band. The index reported is the bar AFTER the move, i.e.
    the suspect bar itself when the previous one is good.
    """
    if max_jump_pct <= 0:
        raise ValueError("max_jump_pct must be positive")

    bad: List[int] = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        try:
            p, c = float(prev), float(cur)
        except (TypeError, ValueError):
            bad.append(i)
            continue
        if p != p or c != c or p == 0:
            bad.append(i)
            continue
        if abs(c - p) / abs(p) > max_jump_pct:
            bad.append(i)

    if bad and raise_on_error:
        raise DataFormatError(
            f"{len(bad)} jump(s) exceeding {max_jump_pct:.1%}, first at index {bad[0]}"
        )
    return bad


def screen_prices(
    prices: Sequence[float],
    bounds: Tuple[float, float],
    max_jump_pct: Optional[float] = DEFAULT_MAX_JUMP_PCT,
) -> List[bool]:
    """Boolean keep-mask combining range and jump checks.

    Returns one flag per input price; ``False`` marks a row to drop. A jump
    flags the later bar, which is the usual convention when the earlier bar
    is known good, but when in doubt drop both endpoints.
    """
    keep = [True] * len(prices)
    for i in validate_price_range(prices, bounds):
        keep[i] = False
    if max_jump_pct is not None:
        for i in validate_price_jumps(prices, max_jump_pct):
            keep[i] = False
            # A jump is a two-sided ambiguity; the prior bar may be the
            # corrupt one. Drop it too rather than trust either.
            if i > 0:
                keep[i - 1] = False
    return keep