"""Tests for Fee Engine and Cash Manager."""

import pytest
from datetime import date, datetime

from services.fund.models import (
    Fund,
    CashReserve,
    FeeSchedule,
    FeeType,
    CrystallizationMode,
)
from services.fund.fee_engine import FeeEngine, FeeAccrual, FeeReport
from services.fund.cash_manager import CashManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fund():
    return Fund(
        fund_id="TEST_FUND",
        fund_name="Test Fund",
        nav=1.50,
        aum=150_000_000,
        total_shares=100_000_000,
        cash_balance=30_000_000,
        management_fee_rate=0.015,
        performance_fee_rate=0.20,
        high_water_mark=1.40,
    )


@pytest.fixture
def fee_schedule():
    return FeeSchedule(
        management_fee_pct=1.5,
        performance_fee_pct=20.0,
        subscription_fee_pct=1.0,
        redemption_fee_pct=0.5,
        high_water_mark=1.40,
        hurdle_rate=0.0,
    )


@pytest.fixture
def fee_engine():
    return FeeEngine()


@pytest.fixture
def cash_manager():
    return CashManager()


# ---------------------------------------------------------------------------
# FeeEngine
# ---------------------------------------------------------------------------


class TestFeeEngine:
    """Tests for fee calculation and accrual."""

    def test_accrue_management_fee(self, fund, fee_engine):
        """Daily management fee = AUM * rate / 365."""
        accrual = fee_engine.accrue_management_fee(fund)
        expected = 150_000_000 * 0.015 / 365.0
        assert accrual.amount == pytest.approx(expected, rel=1e-4)
        assert accrual.fee_type == FeeType.MANAGEMENT
        assert accrual.fund_id == "TEST_FUND"

    def test_management_fee_with_schedule(self, fund, fee_schedule, fee_engine):
        """Management fee using explicit FeeSchedule."""
        accrual = fee_engine.accrue_management_fee(fund, fee_schedule)
        expected = 150_000_000 * 1.5 / 100.0 / 365.0
        assert accrual.amount == pytest.approx(expected, rel=1e-4)

    def test_management_fee_for_period(self, fund, fee_engine):
        """Management fee over multiple days."""
        fee = fee_engine.management_fee_for_period(fund, days=30)
        expected = 150_000_000 * 0.015 * 30 / 365.0
        assert fee == pytest.approx(expected, rel=1e-4)

    def test_performance_fee_above_hwm(self, fund, fee_engine):
        """Performance fee when NAV > HWM."""
        fee = fee_engine.calculate_performance_fee(fund)
        # excess = (1.50 - 1.40) * 100M * 20% = 2,000,000
        expected = 2_000_000
        assert fee == pytest.approx(expected, rel=1e-4)

    def test_performance_fee_below_hwm(self, fund, fee_engine):
        """No performance fee when NAV < HWM."""
        fund.nav = 1.30
        fund.high_water_mark = 1.40
        fee = fee_engine.calculate_performance_fee(fund)
        assert fee == 0.0

    def test_performance_fee_with_hurdle(self, fund, fee_schedule, fee_engine):
        """Performance fee with hurdle rate."""
        fee_schedule.hurdle_rate = 0.05  # 5% hurdle
        # effective HWM = max(1.40, 1.40 * 1.05) = 1.47
        # excess = (1.50 - 1.47) * 100M * 20% = 600,000
        fee = fee_engine.calculate_performance_fee(fund, fee_schedule)
        expected = (1.50 - 1.47) * 100_000_000 * 0.20
        assert fee == pytest.approx(expected, rel=1e-4)

    def test_performance_fee_hurdle_no_excess(self, fund, fee_schedule, fee_engine):
        """Hurdle rate eliminates performance fee."""
        fee_schedule.hurdle_rate = 0.10  # 10% hurdle → effective HWM = 1.54
        fee = fee_engine.calculate_performance_fee(fund, fee_schedule)
        assert fee == 0.0

    def test_should_crystallize_daily(self, fund, fee_engine):
        """Daily crystallization always returns True."""
        fund.crystallization = CrystallizationMode.DAILY
        fund.high_water_mark = 1.0  # ensure excess exists
        should, fee = fee_engine.should_crystallize(fund)
        assert should is True
        assert fee > 0

    def test_should_crystallize_quarterly(self, fund, fee_engine):
        """Quarterly crystallization only on first day of quarter."""
        fund.crystallization = CrystallizationMode.QUARTERLY

        # Test for January 1 (should crystallize)
        from datetime import date
        should, _ = fee_engine.should_crystallize(fund, as_of=date(2026, 1, 1))
        assert should is True

        # Test for February 15 (should NOT crystallize)
        should, _ = fee_engine.should_crystallize(fund, as_of=date(2026, 2, 15))
        assert should is False

    def test_subscription_fee(self, fee_schedule, fee_engine):
        """Subscription fee calculation."""
        fee = fee_engine.subscription_fee(1_000_000, fee_schedule)
        assert fee == 10_000  # 1% of 1M

    def test_redemption_fee(self, fee_schedule, fee_engine):
        """Redemption fee calculation."""
        fee = fee_engine.redemption_fee(1_000_000, fee_schedule)
        assert fee == 5_000  # 0.5% of 1M

    def test_no_subscription_fee_without_schedule(self, fee_engine):
        """Zero fee when no schedule provided."""
        assert fee_engine.subscription_fee(1_000_000) == 0.0

    def test_generate_report(self, fund, fee_engine):
        """Fee report aggregation."""
        # Accrue some fees
        fee_engine.accrue_management_fee(fund)
        fee_engine.accrue_management_fee(fund)
        fee_engine.accrue_management_fee(fund)

        start = date.today()
        end = date.today()
        report = fee_engine.generate_report(fund.fund_id, start, end)

        assert isinstance(report, FeeReport)
        assert report.total_management_fee > 0
        assert report.total_performance_fee == 0  # not crystallized
        assert report.total_fees > 0

    def test_get_accruals_by_type(self, fund, fee_engine):
        """Filter accruals by type."""
        fee_engine.accrue_management_fee(fund)
        mgmt_accruals = fee_engine.get_accruals_by_type(fund.fund_id, FeeType.MANAGEMENT)
        assert len(mgmt_accruals) == 1

    def test_total_accrued(self, fund, fee_engine):
        """Sum of all accrued fees."""
        fee_engine.accrue_management_fee(fund)
        fee_engine.accrue_management_fee(fund)
        total = fee_engine.total_accrued(fund.fund_id)
        assert total > 0

    def test_fee_accrual_to_dict(self, fund, fee_engine):
        """FeeAccrual serialization."""
        accrual = fee_engine.accrue_management_fee(fund)
        d = accrual.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert d["fee_type"] == "MANAGEMENT"
        assert d["amount"] > 0

    def test_fee_report_to_dict(self, fund, fee_engine):
        """FeeReport serialization."""
        fee_engine.accrue_management_fee(fund)
        report = fee_engine.generate_report(fund.fund_id, date.today(), date.today())
        d = report.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert "total_fees" in d

    def test_performance_fee_recorded_on_crystallization(self, fund, fee_engine):
        """Performance fee is recorded when crystallized."""
        fund.crystallization = CrystallizationMode.DAILY
        fund.high_water_mark = 1.0

        should, fee = fee_engine.should_crystallize(fund)
        assert should is True
        assert fee > 0

        perf_accruals = fee_engine.get_accruals_by_type(fund.fund_id, FeeType.PERFORMANCE)
        assert len(perf_accruals) == 1


# ---------------------------------------------------------------------------
# CashManager
# ---------------------------------------------------------------------------


class TestCashManager:
    """Tests for cash position management."""

    def test_initialize(self, fund, cash_manager):
        """Initialize cash reserve."""
        reserve = cash_manager.initialize(fund, total_cash=30_000_000)
        assert reserve.total == 30_000_000
        assert reserve.available == 30_000_000

    def test_get_auto_initialize(self, cash_manager):
        """Get creates reserve if missing."""
        reserve = cash_manager.get("NEW_FUND")
        assert reserve.total == 0.0

    def test_deposit(self, fund, cash_manager):
        """Deposit adds to cash."""
        cash_manager.initialize(fund, total_cash=10_000_000)
        cash_manager.deposit(fund.fund_id, 5_000_000)
        assert cash_manager.total_cash(fund.fund_id) == 15_000_000

    def test_withdraw(self, fund, cash_manager):
        """Withdraw reduces cash."""
        cash_manager.initialize(fund, total_cash=10_000_000)
        cash_manager.withdraw(fund.fund_id, 3_000_000)
        assert cash_manager.total_cash(fund.fund_id) == 7_000_000

    def test_withdraw_insufficient(self, fund, cash_manager):
        """Cannot withdraw more than available."""
        cash_manager.initialize(fund, total_cash=5_000_000)
        with pytest.raises(ValueError, match="Insufficient"):
            cash_manager.withdraw(fund.fund_id, 10_000_000)

    def test_freeze_unfreeze(self, fund, cash_manager):
        """Freeze and unfreeze cash."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.freeze(fund.fund_id, 5_000_000)
        assert cash_manager.investable_for(fund.fund_id) == 25_000_000
        cash_manager.unfreeze(fund.fund_id, 5_000_000)
        assert cash_manager.investable_for(fund.fund_id) == 30_000_000

    def test_reserve_redemption(self, fund, cash_manager):
        """Reserve cash for redemption."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.reserve_redemption(fund.fund_id, 10_000_000)
        reserve = cash_manager.get(fund.fund_id)
        assert reserve.pending_redemption == 10_000_000
        assert reserve.available == 20_000_000

    def test_pay_redemption(self, fund, cash_manager):
        """Pay redemption releases reserve and reduces total."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.reserve_redemption(fund.fund_id, 10_000_000)
        cash_manager.pay_redemption(fund.fund_id, 10_000_000)
        reserve = cash_manager.get(fund.fund_id)
        assert reserve.total == 20_000_000
        assert reserve.pending_redemption == 0

    def test_reserve_fees(self, fund, cash_manager):
        """Reserve fees from available cash."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.reserve_fees(fund.fund_id, 1_000_000)
        reserve = cash_manager.get(fund.fund_id)
        assert reserve.fee_reserve == 1_000_000

    def test_pay_fees(self, fund, cash_manager):
        """Pay fees reduces total and fee reserve."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.reserve_fees(fund.fund_id, 1_000_000)
        cash_manager.pay_fees(fund.fund_id, 1_000_000)
        reserve = cash_manager.get(fund.fund_id)
        assert reserve.total == 29_000_000
        assert reserve.fee_reserve == 0

    def test_set_margin(self, fund, cash_manager):
        """Set margin requirement."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.set_margin(fund.fund_id, 2_000_000)
        reserve = cash_manager.get(fund.fund_id)
        assert reserve.margin == 2_000_000

    def test_investable(self, fund, cash_manager):
        """Investable = total - all reserves."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.freeze(fund.fund_id, 5_000_000)
        cash_manager.reserve_redemption(fund.fund_id, 3_000_000)
        cash_manager.reserve_fees(fund.fund_id, 1_000_000)
        cash_manager.set_margin(fund.fund_id, 1_000_000)

        # available = 30M - 5M - 3M - 1M - 1M = 20M
        assert cash_manager.investable_for(fund.fund_id) == 20_000_000

    def test_can_allocate(self, fund, cash_manager):
        """Can allocate check."""
        cash_manager.initialize(fund, total_cash=10_000_000)
        ok, msg = cash_manager.can_allocate(fund.fund_id, 5_000_000)
        assert ok is True
        assert msg == "OK"

        ok, msg = cash_manager.can_allocate(fund.fund_id, 15_000_000)
        assert ok is False
        assert "Insufficient" in msg

    def test_summary(self, fund, cash_manager):
        """Cash summary."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        summary = cash_manager.summary(fund.fund_id)
        assert summary["total"] == 30_000_000
        assert summary["available"] == 30_000_000

    def test_audit_trail(self, fund, cash_manager):
        """Audit log records operations."""
        cash_manager.initialize(fund, total_cash=30_000_000)
        cash_manager.freeze(fund.fund_id, 5_000_000)
        cash_manager.unfreeze(fund.fund_id, 5_000_000)

        log = cash_manager.audit_trail(fund.fund_id)
        assert len(log) == 3  # INIT, FREEZE, UNFREEZE
        assert log[0]["operation"] == "INIT"

    def test_freeze_insufficient(self, fund, cash_manager):
        """Cannot freeze more than available."""
        cash_manager.initialize(fund, total_cash=5_000_000)
        with pytest.raises(ValueError, match="Insufficient"):
            cash_manager.freeze(fund.fund_id, 10_000_000)
