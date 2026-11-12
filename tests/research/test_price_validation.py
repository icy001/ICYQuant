"""Tests for price plausibility checks.

These exist because of a real defect: one corrupt bar in the HistData M1
feed (2001-06-08 07:30 Beijing, close=1965.0001 while EURUSD traded
0.82-1.60) satisfied every check that existed at the time. It produced a
single -19.6 million pip "trade" and made a momentum backtest report
-1.27 million pips per year. The first test below pins that exact case.
"""

import pytest

from research.data.exceptions import DataFormatError
from research.data.validators import (
    DEFAULT_PRICE_BOUNDS,
    screen_prices,
    validate_price_jumps,
    validate_price_range,
)

EURUSD_BOUNDS = DEFAULT_PRICE_BOUNDS["EURUSD"]


def test_range_catches_the_real_corrupt_bar():
    """The actual bad value from the live dataset must be rejected."""
    closes = [1.1000, 1.1010, 1965.0001, 1.1020]

    assert validate_price_range(closes, EURUSD_BOUNDS) == [2]


def test_range_accepts_plausible_eurusd_history():
    """Real EURUSD extremes over 2000-2026 must survive the screen."""
    # ~0.82 low (2000) and ~1.60 high (2008)
    closes = [0.8234, 1.0000, 1.6038, 1.0850]

    assert validate_price_range(closes, EURUSD_BOUNDS) == []


def test_range_flags_nan_and_non_numeric():
    closes = [1.1, float("nan"), 1.2, "abc", 1.3]

    assert validate_price_range(closes, EURUSD_BOUNDS) == [1, 3]


def test_range_can_raise_instead_of_returning_indices():
    with pytest.raises(DataFormatError):
        validate_price_range([1965.0001], EURUSD_BOUNDS, raise_on_error=True)


def test_jump_catches_corrupt_bar_even_when_inside_bounds():
    """The key gap: a bad price that still falls inside the sane band.

    Range check cannot see this, jump check can.
    """
    closes = [1.1000, 1.9000, 1.1005]

    assert validate_price_range(closes, EURUSD_BOUNDS) == []
    assert validate_price_jumps(closes, 0.10) == [1, 2]


def test_jump_allows_normal_intraday_moves():
    """Sub-10% moves are ordinary market noise, not data errors."""
    closes = [1.1000, 1.1050, 1.0980, 1.1120]

    assert validate_price_jumps(closes, 0.10) == []


def test_jump_threshold_is_configurable():
    # 3% move: flagged at 1% threshold, fine at 10%
    closes = [1.1000, 1.1330]

    assert validate_price_jumps(closes, 0.01) == [1]
    assert validate_price_jumps(closes, 0.10) == []


def test_jump_rejects_non_positive_threshold():
    with pytest.raises(ValueError):
        validate_price_jumps([1.0, 1.1], 0.0)


def test_jump_handles_single_bar_and_empty():
    assert validate_price_jumps([1.1], 0.10) == []
    assert validate_price_jumps([], 0.10) == []


def test_screen_drops_both_sides_of_a_jump():
    """A jump is ambiguous in direction, so neither endpoint is trusted."""
    closes = [1.1000, 1965.0001, 1.1020]

    keep = screen_prices(closes, EURUSD_BOUNDS)

    assert keep == [False, False, False]


def test_screen_keeps_clean_series_untouched():
    closes = [1.1000, 1.1010, 1.0995, 1.1030]

    assert screen_prices(closes, EURUSD_BOUNDS) == [True] * 4


def test_screen_can_disable_jump_check():
    """Range-only mode is useful for sparse or irregular series."""
    closes = [1.1000, 1.5000, 1.1005]

    keep = screen_prices(closes, EURUSD_BOUNDS, max_jump_pct=None)

    assert keep == [True] * 3
