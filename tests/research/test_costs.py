"""Tests for the centralised transaction-cost assumptions.

The numbers here are decisions, not implementation details, so they are
pinned: if someone changes the account cost constant, the tests that
depend on the published break-even analysis must fail loudly rather than
quietly alter a go/no-go conclusion.
"""

import pytest

from research.discovery.cost import DEFAULT_COST_MODEL
from research.discovery.costs import (
    ACCOUNT_EURUSD_RT_PIPS,
    BREAK_EVEN_PIPS,
    KNOWN_MISMATCHES,
    LEGACY_ASSUMED_RT_PIPS,
    bps_to_pips,
    describe_all_mismatches,
    pips_to_bps,
)


def test_account_cost_matches_the_real_account():
    """The account charged 5 USD per lot per side => 1.0 pip round trip."""
    assert ACCOUNT_EURUSD_RT_PIPS == 1.0


def test_legacy_assumption_is_not_silently_equal_to_account():
    """History used 1.5; if these ever converge, the distinction was lost."""
    assert LEGACY_ASSUMED_RT_PIPS == 1.5
    assert LEGACY_ASSUMED_RT_PIPS != ACCOUNT_EURUSD_RT_PIPS


def test_break_even_values_are_recorded():
    assert BREAK_EVEN_PIPS["m5_reversal_h12"] == pytest.approx(0.333)
    assert BREAK_EVEN_PIPS["tp_to_open"] == pytest.approx(4.66)


@pytest.mark.parametrize("pips", [0.1, 1.0, 1.5, 3.24, 10.0])
def test_bps_pip_conversion_round_trips(pips):
    bps = pips_to_bps(pips, 1.08)
    assert bps_to_pips(bps, 1.08) == pytest.approx(pips, rel=1e-12)


def test_one_pip_is_less_than_one_bp_at_eurusd_parity_ish():
    """At price > 1, a pip is worth LESS than 1 bp of notional.

    This is exactly why 3 bps and 3 pips are different and why the
    Discovery-vs-account gap is material.
    """
    assert bps_to_pips(1.0, 1.08) == pytest.approx(1.08, rel=1e-12)
    assert pips_to_bps(1.0, 1.08) == pytest.approx(0.9259, abs=1e-3)


def test_conversion_rejects_non_positive_price():
    with pytest.raises(ValueError):
        bps_to_pips(1.0, 0.0)
    with pytest.raises(ValueError):
        pips_to_bps(1.0, -1.0)


def test_discovery_engine_eurusd_cost_is_three_bps():
    """Pin the engine's convention so a change there is noticed."""
    assert DEFAULT_COST_MODEL.one_way_bps("EURUSD") == pytest.approx(1.5)
    assert DEFAULT_COST_MODEL.round_trip_bps("EURUSD") == pytest.approx(3.0)


def test_known_mismatch_documents_the_3x_gap():
    eurusd = [m for m in KNOWN_MISMATCHES if m.asset == "EURUSD"]
    assert len(eurusd) == 1

    m = eurusd[0]
    assert m.discovery_round_trip_pips == pytest.approx(3.24, abs=0.01)
    assert m.ratio == pytest.approx(3.24, abs=0.02)
    # The Discovery engine is the more conservative of the two.
    assert m.ratio > 1.0


def test_mismatch_description_names_both_denominations():
    text = describe_all_mismatches()[0]

    assert "bps" in text and "pip" in text
    assert "EURUSD" in text
