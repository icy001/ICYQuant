"""Tests for NAV computation and AUM tracking."""

import pytest
from datetime import date, datetime

from services.fund.models import Fund, CashReserve
from services.fund.nav import NAVEngine, NAVResult
from services.fund.aum import AUMTracker, AUMRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fund():
    """Create a sample fund."""
    return Fund(
        fund_id="TEST_FUND",
        fund_name="Test Fund",
        nav=1.0,
        aum=100_000_000,
        total_shares=100_000_000,
        cash_balance=10_000_000,
    )


@pytest.fixture
def nav_engine():
    return NAVEngine()


@pytest.fixture
def aum_tracker():
    return AUMTracker()


# ---------------------------------------------------------------------------
# NAVEngine
# ---------------------------------------------------------------------------


class TestNAVEngine:
    """Tests for NAV computation."""

    def test_basic_nav_computation(self, fund, nav_engine):
        """NAV = (assets - liabilities) / shares."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
        )

        assert result.nav_per_share == pytest.approx(1.0, rel=1e-6)
        assert result.total_net_asset == 100_000_000
        assert result.total_shares == 100_000_000

    def test_nav_with_liabilities(self, fund, nav_engine):
        """NAV reduced by liabilities."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
            payables=1_000_000,
            borrowed_funds=500_000,
        )

        assert result.total_liabilities == 1_500_000
        assert result.total_net_asset == 98_500_000
        assert result.nav_per_share == pytest.approx(0.985, rel=1e-6)

    def test_nav_with_accrued_fees(self, fund, nav_engine):
        """NAV reflects accrued management and performance fees."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
            accrued_management_fee=20_000,
            accrued_performance_fee=50_000,
        )

        assert result.accrued_management_fee == 20_000
        assert result.accrued_performance_fee == 50_000
        assert result.total_net_asset == 99_930_000

    def test_nav_with_receivables(self, fund, nav_engine):
        """Receivables increase assets."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
            receivables=500_000,
            accrued_dividends=100_000,
            accrued_interest=50_000,
        )

        assert result.total_assets == 100_650_000
        assert result.nav_per_share == pytest.approx(1.0065, rel=1e-6)

    def test_nav_zero_shares(self, nav_engine):
        """Fund with zero shares should not crash (use 1 share)."""
        fund = Fund(fund_id="EMPTY", fund_name="Empty", nav=1.0, total_shares=0.0, aum=0.0)
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=0.0,
            cash_reserve=CashReserve(total=0.0),
        )
        assert result.nav_per_share == 0.0

    def test_quick_nav(self, fund, nav_engine):
        """Quick NAV convenience method."""
        result = nav_engine.quick_nav(fund, portfolio_value=90_000_000, cash=10_000_000)
        assert result.nav_per_share == pytest.approx(1.0, rel=1e-6)

    def test_apply_to_fund(self, fund, nav_engine):
        """NAV result updates fund state."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=95_000_000,
            cash_reserve=CashReserve(total=10_000_000),
        )
        record = nav_engine.apply_to_fund(fund, result)

        assert fund.nav == pytest.approx(1.05, rel=1e-6)
        assert fund.aum == 105_000_000
        assert isinstance(record.date, date)
        assert record.nav == pytest.approx(1.05, rel=1e-6)

    def test_nav_result_to_dict(self, fund, nav_engine):
        """NAVResult serializes correctly."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
        )
        d = result.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert "assets" in d
        assert "liabilities" in d
        assert d["nav_per_share"] == pytest.approx(1.0, rel=1e-6)

    def test_nav_with_other_assets_liabilities(self, fund, nav_engine):
        """Custom asset/liability items."""
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=90_000_000,
            cash_reserve=CashReserve(total=10_000_000),
            other_assets=[("Crypto", 500_000), ("Private Equity", 1_000_000)],
            other_liabilities=[("Deferred Tax", 100_000)],
        )
        assert result.total_assets == 101_500_000
        assert result.total_liabilities == 100_000

    def test_nav_updates_high_water_mark(self, fund, nav_engine):
        """NAV update should track high-water mark."""
        fund.high_water_mark = 1.0
        result = nav_engine.compute(
            fund=fund,
            portfolio_value=120_000_000,
            cash_reserve=CashReserve(total=10_000_000),
        )
        nav_engine.apply_to_fund(fund, result)
        assert fund.high_water_mark == pytest.approx(1.30, rel=1e-6)


# ---------------------------------------------------------------------------
# AUMTracker
# ---------------------------------------------------------------------------


class TestAUMTracker:
    """Tests for AUM tracking."""

    def test_record_aum(self, fund, aum_tracker):
        """Record AUM data points."""
        record = aum_tracker.record(fund, net_flow=1_000_000, pnl=500_000)
        assert record.aum == 100_000_000
        assert record.net_flow == 1_000_000
        assert record.pnl == 500_000

    def test_current_aum(self, fund, aum_tracker):
        """Get latest AUM record."""
        aum_tracker.record(fund)
        current = aum_tracker.current(fund.fund_id)
        assert current is not None
        assert current.aum == 100_000_000

    def test_current_missing(self, aum_tracker):
        """Query missing fund returns None."""
        assert aum_tracker.current("NONEXISTENT") is None

    def test_history(self, fund, aum_tracker):
        """AUM history tracking."""
        aum_tracker.record(fund, net_flow=1_000_000)
        fund.update_nav(1.05, new_aum=105_000_000)
        aum_tracker.record(fund, net_flow=2_000_000)

        history = aum_tracker.history(fund.fund_id)
        assert len(history) == 2
        assert history[0].aum == 100_000_000
        assert history[1].aum == 105_000_000

    def test_growth_rate(self, fund, aum_tracker):
        """AUM growth rate calculation."""
        # Record 30 days apart (approximate with 2 data points)
        from datetime import timedelta

        fund.nav_date = date.today() - timedelta(days=30)
        aum_tracker.record(fund, net_flow=0, pnl=0)

        fund.nav_date = date.today()
        fund.update_nav(1.05, new_aum=105_000_000)
        aum_tracker.record(fund, net_flow=0, pnl=0)

        rate = aum_tracker.growth_rate(fund.fund_id, days=30)
        # 100M -> 105M over ~30 days ≈ 80% annualized
        assert rate > 0

    def test_growth_rate_insufficient_data(self, aum_tracker):
        """Growth rate with < 2 records returns 0."""
        assert aum_tracker.growth_rate("EMPTY", days=30) == 0.0

    def test_total_inflows_outflows(self, fund, aum_tracker):
        """Track cumulative flows."""
        aum_tracker.record(fund, net_flow=5_000_000)
        aum_tracker.record(fund, net_flow=-2_000_000)
        aum_tracker.record(fund, net_flow=3_000_000)

        assert aum_tracker.total_inflows(fund.fund_id) == 8_000_000
        assert aum_tracker.total_outflows(fund.fund_id) == 2_000_000

    def test_summary(self, fund, aum_tracker):
        """AUM summary includes all fields."""
        aum_tracker.record(fund, net_flow=1_000_000, pnl=500_000)
        summary = aum_tracker.summary(fund.fund_id)

        assert summary["fund_id"] == "TEST_FUND"
        assert summary["current_aum"] == 100_000_000
        assert "30d_growth_rate_pct" in summary
        assert summary["total_inflows"] == 1_000_000

    def test_summary_missing(self, aum_tracker):
        """Summary for missing fund."""
        summary = aum_tracker.summary("NONEXISTENT")
        assert "error" in summary

    def test_aum_record_to_dict(self, fund, aum_tracker):
        """AUMRecord serialization."""
        record = aum_tracker.record(fund, net_flow=1_000_000, pnl=500_000)
        d = record.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert d["aum"] == 100_000_000
        assert d["net_flow"] == 1_000_000
