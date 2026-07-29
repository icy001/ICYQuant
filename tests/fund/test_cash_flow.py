"""Tests for Cash Flow (Subscription & Redemption) operations."""

import pytest
from datetime import date, datetime

from services.fund.models import (
    Fund,
    InvestorAccount,
    CashReserve,
    FeeSchedule,
    SubscriptionOrder,
    RedemptionOrder,
    SubscriptionStatus,
    RedemptionType,
)
from services.fund.subscription import SubscriptionEngine, SubscriptionError
from services.fund.redemption import RedemptionEngine, RedemptionError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fund():
    return Fund(
        fund_id="TEST_FUND",
        fund_name="Test Fund",
        nav=1.25,
        aum=125_000_000,
        total_shares=100_000_000,
        cash_balance=20_000_000,
    )


@pytest.fixture
def investor():
    return InvestorAccount(
        fund_id="TEST_FUND",
        investor_name="Test Investor",
        shares=100_000.0,
        cost_basis=125_000.0,
    )


@pytest.fixture
def cash():
    return CashReserve(fund_id="TEST_FUND", total=30_000_000)


@pytest.fixture
def fee_schedule():
    return FeeSchedule(
        subscription_fee_pct=1.0,
        redemption_fee_pct=0.5,
    )


@pytest.fixture
def sub_engine():
    return SubscriptionEngine()


@pytest.fixture
def red_engine():
    return RedemptionEngine()


# ---------------------------------------------------------------------------
# SubscriptionEngine
# ---------------------------------------------------------------------------


class TestSubscription:
    """Tests for subscription (inflow) operations."""

    def test_basic_subscription(self, fund, investor, cash, sub_engine):
        """Basic subscription flow."""
        order = sub_engine.subscribe(
            fund=fund, account=investor, amount=1_000_000, cash=cash,
        )
        assert order.status == SubscriptionStatus.SETTLED
        assert order.shares_allocated == pytest.approx(800_000, rel=1e-4)  # 1M / 1.25
        assert fund.total_shares == 100_800_000
        assert fund.aum == 126_000_000
        assert investor.shares == 900_000

    def test_subscription_with_fee(self, fund, investor, cash, fee_schedule, sub_engine):
        """Subscription with entry fee."""
        order = sub_engine.subscribe(
            fund=fund, account=investor, amount=1_000_000, cash=cash,
            fee_schedule=fee_schedule,
        )
        net = 1_000_000 - 10_000  # 1% fee
        expected_shares = net / 1.25
        assert order.shares_allocated == pytest.approx(expected_shares, rel=1e-4)
        assert order.metadata["subscription_fee"] == 10_000

    def test_subscription_zero_amount(self, fund, investor, cash, sub_engine):
        """Reject zero or negative subscription."""
        with pytest.raises(SubscriptionError, match="positive"):
            sub_engine.subscribe(fund=fund, account=investor, amount=0, cash=cash)

    def test_subscription_invalid_nav(self, fund, investor, cash, sub_engine):
        """Reject subscription with invalid NAV."""
        fund.nav = 0.0
        with pytest.raises(SubscriptionError, match="Invalid NAV"):
            sub_engine.subscribe(fund=fund, account=investor, amount=1_000_000, cash=cash)

    def test_validate_subscription(self, fund, sub_engine):
        """Validate subscription request."""
        result = sub_engine.validate(fund, amount=1_000_000)
        assert result["valid"] is True
        assert result["shares"] > 0

    def test_validate_below_minimum(self, fund, sub_engine):
        """Reject below minimum subscription."""
        result = sub_engine.validate(fund, amount=100, min_subscription=10_000)
        assert result["valid"] is False
        assert "Below minimum" in result["reason"]

    def test_validate_above_maximum(self, fund, sub_engine):
        """Reject above maximum subscription."""
        result = sub_engine.validate(fund, amount=10_000_000, max_subscription=5_000_000)
        assert result["valid"] is False
        assert "Above maximum" in result["reason"]

    def test_subscription_updates_cash(self, fund, investor, cash, sub_engine):
        """Subscription increases fund cash."""
        initial_cash = cash.total
        sub_engine.subscribe(fund=fund, account=investor, amount=1_000_000, cash=cash)
        assert cash.total == initial_cash + 1_000_000

    def test_multiple_subscriptions(self, fund, cash, sub_engine):
        """Multiple investors subscribing."""
        inv1 = InvestorAccount(fund_id="TEST_FUND", investor_name="A")
        inv2 = InvestorAccount(fund_id="TEST_FUND", investor_name="B")

        sub_engine.subscribe(fund=fund, account=inv1, amount=500_000, cash=cash)
        sub_engine.subscribe(fund=fund, account=inv2, amount=1_500_000, cash=cash)

        assert inv1.shares == 400_000
        assert inv2.shares == 1_200_000

    def test_order_to_dict(self, fund, investor, cash, sub_engine):
        """Subscription order serialization."""
        order = sub_engine.subscribe(
            fund=fund, account=investor, amount=1_000_000, cash=cash,
        )
        d = order.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert d["amount"] == 1_000_000
        assert d["status"] == "SETTLED"


# ---------------------------------------------------------------------------
# RedemptionEngine
# ---------------------------------------------------------------------------


class TestRedemption:
    """Tests for redemption (outflow) operations."""

    def test_basic_redemption(self, fund, investor, cash, red_engine):
        """Basic redemption flow."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
            redemption_type=RedemptionType.T0,
        )
        assert order.status == SubscriptionStatus.CONFIRMED
        assert order.redemption_amount == 62_500  # 50k * 1.25
        assert investor.shares == 50_000
        assert fund.total_shares == 99_950_000

    def test_redemption_insufficient_shares(self, fund, investor, cash, red_engine):
        """Reject redemption exceeding holdings."""
        with pytest.raises(RedemptionError, match="Insufficient shares"):
            red_engine.redeem(fund=fund, account=investor, shares=200_000, cash=cash)

    def test_redemption_with_fee(self, fund, investor, cash, fee_schedule, red_engine):
        """Redemption with exit fee."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
            fee_schedule=fee_schedule,
        )
        assert order.metadata["redemption_fee"] == 312.50  # 0.5% of 62,500

    def test_settle_redemption(self, fund, investor, cash, red_engine):
        """Settle a confirmed redemption."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
        )
        initial_cash = cash.total
        red_engine.settle(order, cash)
        assert order.status == SubscriptionStatus.SETTLED
        assert cash.total == initial_cash - order.redemption_amount

    def test_redemption_insufficient_fund_cash(self, fund, investor, red_engine):
        """Reject redemption if fund lacks cash."""
        small_cash = CashReserve(fund_id="TEST_FUND", total=1_000)
        with pytest.raises(RedemptionError, match="Insufficient cash"):
            red_engine.redeem(
                fund=fund, account=investor, shares=50_000, cash=small_cash,
            )

    def test_settlement_dates(self, fund, investor, cash, red_engine):
        """Different settlement schedules."""
        from datetime import timedelta

        t0 = red_engine.redeem(
            fund=fund, account=investor, shares=10_000, cash=cash,
            redemption_type=RedemptionType.T0,
        )
        assert t0.settlement_date == date.today()

        investor.shares += 10_000  # restore
        cash.pending_redemption -= 12_500  # clean up
        t1 = red_engine.redeem(
            fund=fund, account=investor, shares=10_000, cash=cash,
            redemption_type=RedemptionType.T1,
        )
        assert t1.settlement_date == date.today() + timedelta(days=1)

    def test_validate_redemption(self, fund, investor, cash, red_engine):
        """Validate redemption request."""
        result = red_engine.validate(investor, fund, shares=10_000, cash=cash)
        assert result["valid"] is True
        assert result["amount"] == 12_500

    def test_validate_exceeds_ratio(self, fund, investor, cash, red_engine):
        """Reject if redemption exceeds max ratio."""
        result = red_engine.validate(
            investor, fund, shares=50_000, cash=cash, max_redemption_ratio=0.0001,
        )
        assert result["valid"] is False
        assert "exceeds" in result["reason"].lower() or "Redemption exceeds" in result["reason"]

    def test_get_pending_settlements(self, fund, investor, cash, red_engine):
        """Find redemptions ready for settlement."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
            redemption_type=RedemptionType.T0,
        )
        pending = red_engine.get_pending_settlements([order])
        assert len(pending) == 1

    def test_order_to_dict(self, fund, investor, cash, red_engine):
        """Redemption order serialization."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
        )
        d = order.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert d["shares"] == 50_000
        assert d["status"] == "CONFIRMED"

    def test_cannot_settle_twice(self, fund, investor, cash, red_engine):
        """Cannot settle an already-settled redemption."""
        order = red_engine.redeem(
            fund=fund, account=investor, shares=50_000, cash=cash,
        )
        red_engine.settle(order, cash)
        with pytest.raises(RedemptionError, match="Cannot settle"):
            red_engine.settle(order, cash)
