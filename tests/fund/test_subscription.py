"""Tests for FundService, Rebalance, Accounting, and Models."""

import pytest
from datetime import date, datetime

from services.fund.models import (
    Fund,
    InvestorAccount,
    CashReserve,
    FeeSchedule,
    SubscriptionOrder,
    RedemptionOrder,
    NAVRecord,
    SubscriptionStatus,
    RedemptionType,
    RebalanceTrigger,
    RebalancePlan,
    CrystallizationMode,
)
from services.fund.nav import NAVEngine
from services.fund.rebalance import RebalanceEngine
from services.fund.accounting import AccountingAdapter, AccountingReport
from services.fund.service import FundService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fund():
    return Fund(
        fund_id="TEST_FUND",
        fund_name="Test Fund",
        nav=1.25,
        aum=400_000_000,
        total_shares=320_000_000,
        cash_balance=50_000_000,
        high_water_mark=1.20,
    )


@pytest.fixture
def investor():
    return InvestorAccount(
        fund_id="TEST_FUND",
        investor_name="Test Investor",
        shares=100_000,
        cost_basis=125_000,
    )


@pytest.fixture
def fund_service():
    return FundService()


# ---------------------------------------------------------------------------
# FundService
# ---------------------------------------------------------------------------


class TestFundService:
    """Tests for unified FundService."""

    def test_create_fund(self, fund_service):
        """Create a new fund through service."""
        fund = fund_service.create_fund(
            fund_id="NEW_FUND",
            fund_name="New Fund",
            initial_nav=1.0,
            initial_cash=10_000_000,
        )
        assert fund.fund_id == "NEW_FUND"
        assert fund.nav == 1.0
        assert fund.aum == 10_000_000
        assert fund.cash_balance == 10_000_000

    def test_compute_and_apply_nav(self, fund_service, fund):
        """NAV computation through service."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        result = fund_service.compute_nav(
            fund=fund,
            portfolio_value=350_000_000,
        )
        record = fund_service.apply_nav(fund, result)

        assert record.nav == pytest.approx(1.25, rel=1e-6)
        assert record.aum == 400_000_000

    def test_subscribe_through_service(self, fund_service, fund, investor):
        """Subscription through FundService."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        order = fund_service.subscribe(
            fund=fund, account=investor, amount=1_000_000,
        )
        assert order.status == SubscriptionStatus.SETTLED
        assert order.shares_allocated > 0

    def test_redeem_through_service(self, fund_service, fund, investor):
        """Redemption through FundService."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        fund_service._record_investor(fund.fund_id, investor)

        order = fund_service.redeem(
            fund=fund, account=investor, shares=50_000,
        )
        assert order.status == SubscriptionStatus.CONFIRMED
        assert order.redemption_amount == 62_500

    def test_accrue_daily_fees(self, fund_service, fund):
        """Daily fee accrual."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        fees = fund_service.accrue_daily_fees(fund)
        assert fees["management_fee"] > 0
        assert "performance_fee" in fees

    def test_rebalance_through_service(self, fund_service, fund):
        """Rebalance plan generation."""
        plan = fund_service.rebalance_portfolio(
            fund=fund,
            target_weights={"AI": 0.4, "Macro": 0.3, "Cash": 0.3},
            current_allocations={"AI": 200_000_000, "Macro": 150_000_000, "Cash": 50_000_000},
            new_cash=50_000_000,
            trigger=RebalanceTrigger.INFLOW,
        )
        assert isinstance(plan, RebalancePlan)
        assert plan.trigger == RebalanceTrigger.INFLOW
        assert len(plan.orders) > 0

    def test_check_drift(self, fund_service):
        """Drift detection."""
        result = fund_service.check_drift(
            target_weights={"AI": 0.4, "Cash": 0.6},
            current_weights={"AI": 0.5, "Cash": 0.5},
        )
        assert result["max_drift"] == pytest.approx(0.1, rel=1e-9)
        assert result["needs_rebalance"] is True

    def test_get_fund_snapshot(self, fund_service, fund):
        """Fund snapshot includes all sections."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        snapshot = fund_service.get_fund_snapshot(fund)
        assert "fund" in snapshot
        assert "cash" in snapshot
        assert "aum" in snapshot

    def test_generate_audit_package(self, fund_service, fund):
        """Audit package with NAV history."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)

        # Add NAV record
        result = fund_service.compute_nav(fund=fund, portfolio_value=350_000_000)
        fund_service.apply_nav(fund, result)

        # Add investor
        investor = InvestorAccount(fund_id="TEST_FUND", investor_name="Alice", shares=100_000, cost_basis=125_000)
        fund_service._record_investor(fund.fund_id, investor)

        reports = fund_service.generate_audit_package(
            fund=fund,
            allocations={"AI": 200_000_000, "Cash": 50_000_000},
            period_start=date.today(),
            period_end=date.today(),
        )
        assert len(reports) == 5  # NAV, holdings, cashflow, fees, investors

    def test_get_nav_history(self, fund_service, fund):
        """NAV history retrieval."""
        fund_service.cash.initialize(fund, total_cash=50_000_000)
        result = fund_service.compute_nav(fund=fund, portfolio_value=350_000_000)
        fund_service.apply_nav(fund, result)

        history = fund_service.get_nav_history(fund.fund_id)
        assert len(history) == 1
        assert isinstance(history[0], NAVRecord)


# ---------------------------------------------------------------------------
# RebalanceEngine
# ---------------------------------------------------------------------------


class TestRebalanceEngine:
    """Tests for portfolio rebalancing."""

    @pytest.fixture
    def rebalance_engine(self):
        return RebalanceEngine()

    @pytest.fixture
    def fund(self):
        return Fund(
            fund_id="TEST_FUND",
            fund_name="Test Fund",
            nav=1.0,
            aum=100_000_000,
            total_shares=100_000_000,
            cash_balance=10_000_000,
        )

    def test_rebalance_inflow(self, fund, rebalance_engine):
        """Inflow-driven rebalance."""
        plan = rebalance_engine.rebalance(
            fund=fund,
            target_weights={"AI": 0.5, "Cash": 0.5},
            current_allocations={"AI": 50_000_000, "Cash": 50_000_000},
            new_cash=50_000_000,
            trigger=RebalanceTrigger.INFLOW,
        )
        assert len(plan.orders) > 0
        # Should have BUY orders for AI (to deploy new cash)
        buy_orders = [o for o in plan.orders if o["side"] == "BUY"]
        assert len(buy_orders) > 0

    def test_rebalance_invalid_weights(self, fund, rebalance_engine):
        """Reject weights that don't sum to 1."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            rebalance_engine.rebalance(
                fund=fund,
                target_weights={"AI": 0.5},
                current_allocations={"AI": 50_000_000},
            )

    def test_check_drift_below_threshold(self, rebalance_engine):
        """No rebalance needed for small drift."""
        needs, max_drift, _ = rebalance_engine.check_drift(
            target_weights={"AI": 0.40, "Cash": 0.60},
            current_weights={"AI": 0.41, "Cash": 0.59},
        )
        assert needs is False
        assert max_drift == pytest.approx(0.01, rel=1e-9)

    def test_check_drift_above_threshold(self, rebalance_engine):
        """Rebalance needed for large drift."""
        needs, max_drift, _ = rebalance_engine.check_drift(
            target_weights={"AI": 0.40, "Cash": 0.60},
            current_weights={"AI": 0.50, "Cash": 0.50},
        )
        assert needs is True
        assert max_drift == pytest.approx(0.10, rel=1e-9)

    def test_simple_inflow_rebalance(self, fund, rebalance_engine):
        """Convenience method for inflow."""
        plan = rebalance_engine.simple_inflow_rebalance(
            fund=fund,
            target_weights={"AI": 0.5, "Cash": 0.5},
            current_allocations={"AI": 50_000_000, "Cash": 50_000_000},
            inflow_amount=50_000_000,
        )
        assert plan.trigger == RebalanceTrigger.INFLOW
        assert plan.new_cash == 50_000_000

    def test_rebalance_plan_to_dict(self, fund, rebalance_engine):
        """RebalancePlan serialization."""
        plan = rebalance_engine.rebalance(
            fund=fund,
            target_weights={"AI": 0.5, "Cash": 0.5},
            current_allocations={"AI": 50_000_000, "Cash": 50_000_000},
        )
        d = plan.to_dict()
        assert d["fund_id"] == "TEST_FUND"
        assert "target_weights" in d
        assert "orders" in d

    def test_rebalance_with_prices(self, fund, rebalance_engine):
        """Rebalance with price data for quantity calculation."""
        plan = rebalance_engine.rebalance(
            fund=fund,
            target_weights={"AI": 0.5, "Cash": 0.5},
            current_allocations={"AI": 40_000_000, "Cash": 60_000_000},
            new_cash=0,
            prices={"AI": 100.0},
        )
        assert len(plan.orders) > 0


# ---------------------------------------------------------------------------
# AccountingAdapter
# ---------------------------------------------------------------------------


class TestAccounting:
    """Tests for accounting adapter."""

    @pytest.fixture
    def adapter(self):
        return AccountingAdapter()

    @pytest.fixture
    def fund(self):
        return Fund(
            fund_id="TEST_FUND",
            fund_name="Test Fund",
            nav=1.25,
            aum=400_000_000,
        )

    def test_nav_report(self, adapter, fund):
        """Generate NAV report."""
        record = NAVRecord(
            fund_id="TEST_FUND",
            date=date.today(),
            nav=1.25,
            aum=400_000_000,
            total_shares=320_000_000,
            cash_balance=50_000_000,
        )
        report = adapter.generate_nav_report(fund, record)
        assert report.report_type == "NAV_REPORT"
        assert report.data["nav_per_share"] == 1.25

    def test_holdings_report(self, adapter, fund):
        """Generate holdings report."""
        report = adapter.generate_holdings_report(
            fund=fund,
            allocations={"AI": 200_000_000, "Cash": 50_000_000},
        )
        assert report.report_type == "HOLDINGS_REPORT"
        assert len(report.data["holdings"]) == 2

    def test_cashflow_report(self, adapter, fund):
        """Generate cash flow report."""
        cash = CashReserve(fund_id="TEST_FUND", total=50_000_000)
        subs = [SubscriptionOrder(fund_id="TEST_FUND", amount=1_000_000, nav=1.25)]
        subs[0].status = SubscriptionStatus.SETTLED

        report = adapter.generate_cashflow_report(fund, cash, subs, [])
        assert report.report_type == "CASHFLOW_REPORT"
        assert report.data["total_inflows"] > 0

    def test_fee_report(self, adapter, fund):
        """Generate fee report."""
        schedule = FeeSchedule(management_fee_pct=1.5)
        report = adapter.generate_fee_report(
            fund=fund,
            fee_schedule=schedule,
            accrued_fees=[{"amount": 5000, "type": "MANAGEMENT"}],
            period_start=date.today(),
            period_end=date.today(),
        )
        assert report.report_type == "FEE_REPORT"
        assert report.data["total_accrued"] == 5000

    def test_investor_report(self, adapter, fund):
        """Generate investor report."""
        accounts = [
            InvestorAccount(fund_id="TEST_FUND", investor_name="A", shares=100_000, cost_basis=125_000),
            InvestorAccount(fund_id="TEST_FUND", investor_name="B", shares=50_000, cost_basis=60_000),
        ]
        report = adapter.generate_investor_report(fund, accounts)
        assert report.report_type == "INVESTOR_REPORT"
        assert report.data["total_investors"] == 2

    def test_accounting_report_to_dict(self, adapter, fund):
        """AccountingReport serialization."""
        record = NAVRecord(
            fund_id="TEST_FUND", date=date.today(), nav=1.0, aum=100_000_000,
            total_shares=100_000_000, cash_balance=10_000_000,
        )
        report = adapter.generate_nav_report(fund, record)
        d = report.to_dict()
        assert d["report_type"] == "NAV_REPORT"
        assert "data" in d


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestFundModels:
    """Tests for fund domain models."""

    def test_fund_shares_from_amount(self):
        """Convert amount to shares."""
        fund = Fund(fund_id="F", fund_name="F", nav=1.25)
        shares = fund.shares_from_amount(125_000)
        assert shares == 100_000

    def test_fund_amount_from_shares(self):
        """Convert shares to amount."""
        fund = Fund(fund_id="F", fund_name="F", nav=1.25)
        amount = fund.amount_from_shares(100_000)
        assert amount == 125_000

    def test_fund_update_nav(self):
        """Update NAV and HWM."""
        fund = Fund(fund_id="F", fund_name="F", nav=1.0, high_water_mark=1.0)
        fund.update_nav(1.50, new_aum=150_000_000)
        assert fund.nav == 1.50
        assert fund.high_water_mark == 1.50

    def test_fund_to_dict(self):
        """Fund serialization."""
        fund = Fund(fund_id="F", fund_name="Test", nav=1.25)
        d = fund.to_dict()
        assert d["fund_id"] == "F"
        assert d["nav"] == 1.25

    def test_investor_current_value(self):
        """Investor market value."""
        acct = InvestorAccount(fund_id="F", shares=100_000, cost_basis=125_000)
        assert acct.current_value(nav=1.30) == 130_000

    def test_investor_unrealized_pnl(self):
        """Investor P&L."""
        acct = InvestorAccount(fund_id="F", shares=100_000, cost_basis=125_000)
        assert acct.unrealized_pnl(nav=1.30) == 5_000

    def test_investor_add_shares(self):
        """Add shares updates cost basis."""
        acct = InvestorAccount(fund_id="F", shares=100_000, cost_basis=125_000)
        acct.add_shares(shares=50_000, cost=65_000)
        assert acct.shares == 150_000
        assert acct.cost_basis == 190_000

    def test_investor_remove_shares(self):
        """Remove shares reduces cost basis proportionally."""
        acct = InvestorAccount(fund_id="F", shares=100_000, cost_basis=125_000)
        acct.remove_shares(shares=50_000)
        assert acct.shares == 50_000
        assert acct.cost_basis == 62_500

    def test_investor_remove_shares_insufficient(self):
        """Cannot remove more than held."""
        acct = InvestorAccount(fund_id="F", shares=100_000, cost_basis=125_000)
        with pytest.raises(ValueError, match="Insufficient shares"):
            acct.remove_shares(shares=200_000)

    def test_investor_to_dict(self):
        """Investor serialization."""
        acct = InvestorAccount(fund_id="F", investor_name="Alice", shares=100_000, cost_basis=125_000)
        d = acct.to_dict()
        assert d["account_id"] is not None
        assert d["investor_name"] == "Alice"

    def test_subscription_order_post_init(self):
        """Shares calculated in post_init."""
        order = SubscriptionOrder(fund_id="F", amount=125_000, nav=1.25)
        assert order.shares_allocated == 100_000

    def test_redemption_order_amount(self):
        """Redemption amount computed."""
        order = RedemptionOrder(fund_id="F", shares=100_000, nav=1.25)
        assert order.redemption_amount == 125_000

    def test_cash_reserve_available(self):
        """Available cash calculation."""
        reserve = CashReserve(total=30_000_000, frozen=5_000_000, pending_redemption=3_000_000)
        assert reserve.available == 22_000_000
        assert reserve.locked == 8_000_000

    def test_fee_schedule_management_fee(self):
        """Management fee calculation."""
        schedule = FeeSchedule(management_fee_pct=1.5)
        assert schedule.annual_management_fee(100_000_000) == 1_500_000
        assert schedule.daily_management_fee(100_000_000) == pytest.approx(4_109.59, rel=1e-2)

    def test_nav_record_is_frozen(self):
        """NAVRecord is immutable."""
        record = NAVRecord(
            fund_id="F", date=date.today(), nav=1.0, aum=100_000_000,
            total_shares=100_000_000, cash_balance=10_000_000,
        )
        with pytest.raises(Exception):
            record.nav = 2.0  # frozen dataclass

    def test_rebalance_plan_add_order(self):
        """Add order to rebalance plan."""
        plan = RebalancePlan(fund_id="F")
        plan.add_order("AI", "NVDA", "BUY", 1000)
        assert len(plan.orders) == 1
        assert plan.orders[0]["symbol"] == "NVDA"
