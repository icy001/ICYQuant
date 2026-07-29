"""Fund Operation Service — Unified entry point.

Aggregates all fund operation components into a single service
that orchestrates the complete fund lifecycle:

    NAV → AUM → Sub/Red → Cash → Fees → Rebalance → Accounting
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from services.fund.aum import AUMTracker, AUMRecord
from services.fund.nav import NAVEngine, NAVResult
from services.fund.subscription import SubscriptionEngine, SubscriptionError
from services.fund.redemption import RedemptionEngine, RedemptionError
from services.fund.cash_manager import CashManager
from services.fund.fee_engine import FeeEngine, FeeReport
from services.fund.rebalance import RebalanceEngine
from services.fund.accounting import AccountingAdapter, AccountingReport

from services.fund.models import (
    CashReserve,
    FeeSchedule,
    Fund,
    InvestorAccount,
    NAVRecord,
    RebalancePlan,
    RebalanceTrigger,
    RedemptionOrder,
    RedemptionType,
    SubscriptionOrder,
)


class FundService:
    """Unified fund operations service.

    Usage::

        service = FundService()
        fund = Fund(fund_id="AI_GROWTH", fund_name="AI Growth Fund", nav=1.0)
        cash = service.cash.initialize(fund, total_cash=100_000_000)

        # Daily NAV
        result = service.compute_nav(fund, portfolio_value=95_000_000, cash_reserve=cash)
        service.apply_nav(fund, result)

        # Subscription
        acct = InvestorAccount(fund_id="AI_GROWTH", investor_name="张三")
        order = service.subscribe(fund, acct, amount=1_000_000, cash=cash)

        # Fees
        service.accrue_daily_fees(fund)

        # Reports
        reports = service.generate_audit_package(fund, allocations, cash, ...)
    """

    def __init__(self) -> None:
        self.nav = NAVEngine()
        self.aum = AUMTracker()
        self.subscription = SubscriptionEngine()
        self.redemption = RedemptionEngine()
        self.cash = CashManager()
        self.fee = FeeEngine()
        self.rebalance = RebalanceEngine()
        self.accounting = AccountingAdapter()

        # Store orders
        self._subscription_orders: Dict[str, List[SubscriptionOrder]] = {}
        self._redemption_orders: Dict[str, List[RedemptionOrder]] = {}
        self._investors: Dict[str, List[InvestorAccount]] = {}
        self._nav_history: Dict[str, List[NAVRecord]] = {}

    # ------------------------------------------------------------------
    # Fund Management
    # ------------------------------------------------------------------

    def create_fund(
        self,
        fund_id: str,
        fund_name: str,
        initial_nav: float = 1.0,
        initial_cash: float = 0.0,
        management_fee_rate: float = 0.015,
        performance_fee_rate: float = 0.20,
        currency: str = "USD",
    ) -> Fund:
        """Create a new fund."""
        fund = Fund(
            fund_id=fund_id,
            fund_name=fund_name,
            nav=initial_nav,
            aum=initial_cash,
            cash_balance=initial_cash,
            management_fee_rate=management_fee_rate,
            performance_fee_rate=performance_fee_rate,
            currency=currency,
        )
        self.cash.initialize(fund, total_cash=initial_cash)
        return fund

    # ------------------------------------------------------------------
    # NAV Operations
    # ------------------------------------------------------------------

    def compute_nav(
        self,
        fund: Fund,
        portfolio_value: float,
        cash_reserve: Optional[CashReserve] = None,
        **kwargs: Any,
    ) -> NAVResult:
        """Compute daily NAV."""
        return self.nav.compute(fund=fund, portfolio_value=portfolio_value, cash_reserve=cash_reserve, **kwargs)

    def apply_nav(self, fund: Fund, result: NAVResult) -> NAVRecord:
        """Apply NAV result to fund and record in history."""
        record = self.nav.apply_to_fund(fund, result)
        if fund.fund_id not in self._nav_history:
            self._nav_history[fund.fund_id] = []
        self._nav_history[fund.fund_id].append(record)
        self.aum.record(fund)
        return record

    def get_nav_history(self, fund_id: str) -> List[NAVRecord]:
        """Get NAV history for a fund."""
        return self._nav_history.get(fund_id, [])

    # ------------------------------------------------------------------
    # AUM Operations
    # ------------------------------------------------------------------

    def record_aum(self, fund: Fund, net_flow: float = 0.0, pnl: float = 0.0) -> AUMRecord:
        """Record a new AUM data point."""
        return self.aum.record(fund, net_flow=net_flow, pnl=pnl)

    def get_aum_summary(self, fund_id: str) -> Dict[str, object]:
        """Get AUM summary."""
        return self.aum.summary(fund_id)

    # ------------------------------------------------------------------
    # Subscription / Redemption
    # ------------------------------------------------------------------

    def subscribe(
        self,
        fund: Fund,
        account: InvestorAccount,
        amount: float,
        cash: Optional[CashReserve] = None,
        fee_schedule: Optional[FeeSchedule] = None,
    ) -> SubscriptionOrder:
        """Process a subscription."""
        cash = cash or self.cash.get(fund.fund_id)
        order = self.subscription.subscribe(
            fund=fund, account=account, amount=amount, cash=cash, fee_schedule=fee_schedule
        )
        self._record_subscription(fund.fund_id, order)
        self._record_investor(fund.fund_id, account)
        self.aum.record(fund, net_flow=amount)
        return order

    def redeem(
        self,
        fund: Fund,
        account: InvestorAccount,
        shares: float,
        cash: Optional[CashReserve] = None,
        fee_schedule: Optional[FeeSchedule] = None,
        redemption_type: RedemptionType = RedemptionType.T1,
    ) -> RedemptionOrder:
        """Process a redemption."""
        cash = cash or self.cash.get(fund.fund_id)
        order = self.redemption.redeem(
            fund=fund, account=account, shares=shares, cash=cash,
            fee_schedule=fee_schedule, redemption_type=redemption_type,
        )
        self._record_redemption(fund.fund_id, order)
        self.aum.record(fund, net_flow=-order.redemption_amount)
        return order

    def settle_redemption(self, order: RedemptionOrder, cash: Optional[CashReserve] = None) -> None:
        """Settle a pending redemption."""
        cash = cash or self.cash.get(order.fund_id)
        self.redemption.settle(order, cash)

    # ------------------------------------------------------------------
    # Cash Operations
    # ------------------------------------------------------------------

    def get_cash_summary(self, fund_id: str) -> Dict[str, object]:
        """Get cash position summary."""
        return self.cash.summary(fund_id)

    def get_investable_cash(self, fund_id: str) -> float:
        """Get investable cash."""
        return self.cash.investable_for(fund_id)

    # ------------------------------------------------------------------
    # Fee Operations
    # ------------------------------------------------------------------

    def accrue_daily_fees(self, fund: Fund, fee_schedule: Optional[FeeSchedule] = None) -> Dict[str, float]:
        """Accrue one day of management + check performance crystallization.

        Returns dict with accrued fee amounts.
        """
        mgmt = self.fee.accrue_management_fee(fund, fee_schedule)
        should, perf = self.fee.should_crystallize(fund, fee_schedule)

        return {
            "management_fee": mgmt.amount,
            "performance_fee": perf,
            "performance_crystallized": should,
        }

    def get_fee_report(
        self, fund_id: str, period_start: date, period_end: date
    ) -> FeeReport:
        """Get aggregated fee report."""
        return self.fee.generate_report(fund_id, period_start, period_end)

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    def rebalance_portfolio(
        self,
        fund: Fund,
        target_weights: Dict[str, float],
        current_allocations: Dict[str, float],
        new_cash: float = 0.0,
        trigger: RebalanceTrigger = RebalanceTrigger.SCHEDULED,
    ) -> RebalancePlan:
        """Generate a rebalance plan."""
        return self.rebalance.rebalance(
            fund=fund,
            target_weights=target_weights,
            current_allocations=current_allocations,
            new_cash=new_cash,
            trigger=trigger,
        )

    def check_drift(
        self,
        target_weights: Dict[str, float],
        current_weights: Dict[str, float],
    ) -> Dict[str, object]:
        """Check portfolio drift."""
        needs, max_drift, drift_map = self.rebalance.check_drift(target_weights, current_weights)
        return {
            "needs_rebalance": needs,
            "max_drift": max_drift,
            "drift_threshold": self.rebalance.drift_threshold,
            "drift_map": drift_map,
        }

    # ------------------------------------------------------------------
    # Accounting
    # ------------------------------------------------------------------

    def generate_audit_package(
        self,
        fund: Fund,
        allocations: Dict[str, float],
        period_start: date,
        period_end: date,
    ) -> List[AccountingReport]:
        """Generate complete audit package."""
        nav_records = self._nav_history.get(fund.fund_id, [])
        cash_reserve = self.cash.get(fund.fund_id)
        accounts = self._investors.get(fund.fund_id, [])
        subs = self._subscription_orders.get(fund.fund_id, [])
        reds = self._redemption_orders.get(fund.fund_id, [])

        fee_accruals = [
            a.to_dict() for a in self.fee.get_accruals(fund.fund_id)
            if period_start <= a.date <= period_end
        ]

        schedule = FeeSchedule(
            management_fee_pct=fund.management_fee_rate * 100,
            performance_fee_pct=fund.performance_fee_rate * 100,
            high_water_mark=fund.high_water_mark,
            hurdle_rate=fund.hurdle_rate,
        )

        return self.accounting.generate_audit_package(
            fund=fund,
            nav_records=nav_records,
            allocations=allocations,
            cash_reserve=cash_reserve,
            accounts=accounts,
            subscriptions=subs,
            redemptions=reds,
            fee_schedule=schedule,
            accrued_fees=fee_accruals,
            period_start=period_start,
            period_end=period_end,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_fund_snapshot(self, fund: Fund) -> Dict[str, object]:
        """Get a complete fund snapshot."""
        cash = self.cash.get(fund.fund_id)
        aum_summary = self.aum.summary(fund.fund_id)
        investors = self._investors.get(fund.fund_id, [])
        nav_records = self._nav_history.get(fund.fund_id, [])

        return {
            "fund": fund.to_dict(),
            "cash": cash.to_dict(),
            "aum": aum_summary,
            "investor_count": len(investors),
            "total_investor_value": sum(
                a.current_value(fund.nav) for a in investors
            ),
            "nav_records": len(nav_records),
            "latest_nav": nav_records[-1].to_dict() if nav_records else None,
            "pending_subscriptions": len([
                s for s in self._subscription_orders.get(fund.fund_id, [])
                if s.status.value == "PENDING"
            ]),
            "pending_redemptions": len([
                r for r in self._redemption_orders.get(fund.fund_id, [])
                if r.status.value == "PENDING"
            ]),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_subscription(self, fund_id: str, order: SubscriptionOrder) -> None:
        if fund_id not in self._subscription_orders:
            self._subscription_orders[fund_id] = []
        self._subscription_orders[fund_id].append(order)

    def _record_redemption(self, fund_id: str, order: RedemptionOrder) -> None:
        if fund_id not in self._redemption_orders:
            self._redemption_orders[fund_id] = []
        self._redemption_orders[fund_id].append(order)

    def _record_investor(self, fund_id: str, account: InvestorAccount) -> None:
        if fund_id not in self._investors:
            self._investors[fund_id] = []
        # Update existing or append
        for i, existing in enumerate(self._investors[fund_id]):
            if existing.account_id == account.account_id:
                self._investors[fund_id][i] = account
                return
        self._investors[fund_id].append(account)
