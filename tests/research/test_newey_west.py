"""Tests for the shared Newey-West HAC t-statistic.

The same HAC routine had been copied into four experiment scripts before
this. The equivalence test below locks the shared implementation to the
behaviour those scripts relied on, so refactoring them onto it later
cannot silently change any published number.
"""

import math

import pytest

from research.analytics.metrics import calculate_newey_west_t


def _reference_hac(xs, lag):
    """The implementation previously copy-pasted across experiment scripts."""
    n = len(xs)
    mu = sum(xs) / n
    e = [v - mu for v in xs]
    gamma0 = sum(v * v for v in e) / n
    var = gamma0
    for L in range(1, lag + 1):
        g = sum(e[L + i] * e[i] for i in range(n - L)) / n
        w = 1.0 - L / (lag + 1.0)
        var += 2.0 * w * g
    var = max(var, 1e-18)
    return mu / math.sqrt(var / n)


def test_lag_zero_equals_naive_t():
    """With no autocovariance terms, HAC reduces to mean / (sd/sqrt(n)).

    The two differ only by the divisor: HAC divides the sum of squares by n,
    the naive t by n-1. So the exact relationship is
    t_hac = t_naive * sqrt(n / (n-1)); assert that rather than a loose
    tolerance, so a real regression cannot hide inside the slack.
    """
    xs = [((i * 37) % 101 - 50) / 100.0 for i in range(500)]

    n = len(xs)
    mean = sum(xs) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in xs) / (n - 1))
    naive = mean / (sd / math.sqrt(n))

    got = calculate_newey_west_t(xs, lag=0)

    assert got == pytest.approx(naive * math.sqrt(n / (n - 1)), rel=1e-12)


@pytest.mark.parametrize("lag", [1, 5, 10, 20])
def test_matches_previous_implementation(lag):
    xs = [math.sin(i / 7.0) * 0.01 + 0.0005 for i in range(2000)]

    got = calculate_newey_west_t(xs, lag=lag)
    want = _reference_hac(xs, lag)

    assert got == pytest.approx(want, rel=1e-12)


def test_positive_autocorrelation_reduces_t():
    """HAC must penalise serially correlated data, that is the whole point."""
    xs = [0.01 * i for i in range(300)]

    t_iid = calculate_newey_west_t(xs, lag=0)
    t_hac = calculate_newey_west_t(xs, lag=30)

    assert t_hac < t_iid


def test_constant_series_returns_nan():
    assert math.isnan(calculate_newey_west_t([1.0] * 100))


def test_too_short_returns_nan():
    assert math.isnan(calculate_newey_west_t([1.0, 2.0, 3.0]))


def test_empty_returns_nan():
    assert math.isnan(calculate_newey_west_t([]))


def test_auto_lag_runs_and_is_finite():
    xs = [math.cos(i / 5.0) * 0.02 for i in range(1000)]

    got = calculate_newey_west_t(xs, auto_lag=True)

    assert not math.isnan(got)


def test_lag_larger_than_sample_is_clamped():
    """A too-large lag must not raise; it clamps to n-1."""
    xs = [0.001 * (i % 7) for i in range(12)]

    got = calculate_newey_west_t(xs, lag=999)

    assert not math.isnan(got)


def test_negative_lag_treated_as_zero():
    xs = [0.01, -0.02, 0.03, 0.005, -0.004] * 10

    assert calculate_newey_west_t(xs, lag=-5) == pytest.approx(
        calculate_newey_west_t(xs, lag=0), rel=1e-12
    )
