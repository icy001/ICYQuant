"""Fund Accounting Adapter.

Connects the fund operation layer to the ledger/accounting system.

Generates standard fund accounting outputs:
    - NAV report
    - Holdings report
    - Trade / execution report
    - Cash flow statement
    - Fee schedule report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from services.fund.models import (
    CashReserve,
    FeeSchedule,
    Fund,
    InvestorAccount,
    NAVRecord,
    SubscriptionOrder,
    RedemptionOrder,
)


@dataclass
class AccountingReport:
    """Generic fund accounting report container."""

    report_type: str
    fund_id: str
    as_of_date: date
    data: Dict[str, object] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "report_type": self.report_type,
            "fund_id": self.fund_id,
            "as_of_date": self.as_of_date.isoformat(),
            "data": self.data,
            "generated_at": self.generated_at.isoformat(),
        }


class AccountingAdapter:
    """Bridge between Fund Operations and Accounting/Ledger.

    Usage::

        adapter = AccountingAdapter()
        nav_report = adapter.generate_nav_report(fund, nav_record)
        holdings_report = adapter.generate_holdings_report(fund, allocations)
        cashflow_report = adapter.generate_cashflow_report(fund, cash_reserve, subs, reds)
        fee_report = adapter.generate_fee_report(fund, fee_schedule, fee_accruals)
    """

    def generate_nav_report(
        self,
        fund: Fund,
        nav_record: NAVRecord,
    ) -> AccountingReport:
        """Generate a daily NAV report."""
        return AccountingReport(
            report_type="NAV_REPORT",
            fund_id=fund.fund_id,
            as_of_date=nav_record.date,
            data={
                "nav_per_share": nav_record.nav,
                "aum": nav_record.aum,
                "total_shares": nav_record.total_shares,
                "cash_balance": nav_record.cash_balance,
                "management_fee_accrued": nav_record.management_fee_accrued,
                "performance_fee_accrued": nav_record.performance_fee_accrued,
                "fund_name": fund.fund_name,
                "currency": fund.currency,
                "high_water_mark": fund.high_water_mark,
            },
        )

    def generate_holdings_report(
        self,
        fund: Fund,
        allocations: Dict[str, float],
        prices: Optional[Dict[str, float]] = None,
    ) -> AccountingReport:
        """Generate a holdings report."""
        holdings = []
        total_value = sum(allocations.values())

        for strategy, value in allocations.items():
            weight = value / total_value if total_value > 0 else 0.0
            price = prices.get(strategy, None) if prices else None
            holding = {
                "strategy": strategy,
                "notional_value": value,
                "weight_pct": round(weight * 100, 2),
            }
            if price is not None and price > 0:
                holding["price"] = price
                holding["quantity"] = round(value / price, 2)
            holdings.append(holding)

        return AccountingReport(
            report_type="HOLDINGS_REPORT",
            fund_id=fund.fund_id,
            as_of_date=fund.nav_date,
            data={
                "total_value": total_value,
                "holdings": holdings,
                "fund_name": fund.fund_name,
                "currency": fund.currency,
            },
        )

    def generate_cashflow_report(
        self,
        fund: Fund,
        cash_reserve: CashReserve,
        subscriptions: List[SubscriptionOrder],
        redemptions: List[RedemptionOrder],
    ) -> AccountingReport:
        """Generate a cash flow statement."""
        total_inflows = sum(
            s.metadata.get("gross_amount", s.amount)
            for s in subscriptions
            if s.status.value in ("CONFIRMED", "SETTLED")
        )
        total_outflows = sum(
            r.metadata.get("net_amount", r.redemption_amount)
            for r in redemptions
            if r.status.value in ("CONFIRMED", "SETTLED")
        )
        subscription_fees = sum(
            s.metadata.get("subscription_fee", 0.0) for s in subscriptions
        )
        redemption_fees = sum(
            r.metadata.get("redemption_fee", 0.0) for r in redemptions
        )

        return AccountingReport(
            report_type="CASHFLOW_REPORT",
            fund_id=fund.fund_id,
            as_of_date=fund.nav_date,
            data={
                "cash_balance": cash_reserve.total,
                "available_cash": cash_reserve.available,
                "frozen_cash": cash_reserve.frozen,
                "pending_redemption": cash_reserve.pending_redemption,
                "fee_reserve": cash_reserve.fee_reserve,
                "margin": cash_reserve.margin,
                "total_inflows": total_inflows,
                "total_outflows": total_outflows,
                "net_flow": total_inflows - total_outflows,
                "subscription_fees": subscription_fees,
                "redemption_fees": redemption_fees,
                "subscription_count": len(subscriptions),
                "redemption_count": len(redemptions),
                "fund_name": fund.fund_name,
                "currency": fund.currency,
            },
        )

    def generate_fee_report(
        self,
        fund: Fund,
        fee_schedule: FeeSchedule,
        accrued_fees: List[Dict[str, object]],
        period_start: date,
        period_end: date,
    ) -> AccountingReport:
        """Generate a fee schedule and accrual report."""
        total_accrued = sum(f["amount"] for f in accrued_fees)

        return AccountingReport(
            report_type="FEE_REPORT",
            fund_id=fund.fund_id,
            as_of_date=period_end,
            data={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "fee_schedule": fee_schedule.to_dict(),
                "accrued_fees": accrued_fees,
                "total_accrued": total_accrued,
                "fund_name": fund.fund_name,
                "currency": fund.currency,
            },
        )

    def generate_investor_report(
        self,
        fund: Fund,
        accounts: List[InvestorAccount],
    ) -> AccountingReport:
        """Generate investor holdings summary."""
        investors = []
        total_shares = 0.0
        total_value = 0.0

        for acct in accounts:
            value = acct.current_value(fund.nav)
            investors.append({
                "account_id": acct.account_id,
                "investor_name": acct.investor_name,
                "shares": acct.shares,
                "value": value,
                "weight_pct": 0.0,  # will update after total
                "cost_basis": acct.cost_basis,
                "unrealized_pnl": acct.unrealized_pnl(fund.nav),
                "avg_cost_per_share": acct.avg_cost_per_share,
            })
            total_shares += acct.shares
            total_value += value

        # Update weights
        for inv in investors:
            inv["weight_pct"] = round(inv["value"] / total_value * 100, 2) if total_value > 0 else 0.0

        return AccountingReport(
            report_type="INVESTOR_REPORT",
            fund_id=fund.fund_id,
            as_of_date=fund.nav_date,
            data={
                "fund_name": fund.fund_name,
                "nav": fund.nav,
                "total_aum": fund.aum,
                "total_shares": total_shares,
                "total_investors": len(accounts),
                "investors": investors,
                "currency": fund.currency,
            },
        )

    def generate_audit_package(
        self,
        fund: Fund,
        nav_records: List[NAVRecord],
        allocations: Dict[str, float],
        cash_reserve: CashReserve,
        accounts: List[InvestorAccount],
        subscriptions: List[SubscriptionOrder],
        redemptions: List[RedemptionOrder],
        fee_schedule: FeeSchedule,
        accrued_fees: List[Dict[str, object]],
        period_start: date,
        period_end: date,
    ) -> List[AccountingReport]:
        """Generate a complete audit package with all standard reports."""
        latest_nav = nav_records[-1] if nav_records else None
        if latest_nav is None:
            raise ValueError("At least one NAV record required for audit package")

        return [
            self.generate_nav_report(fund, latest_nav),
            self.generate_holdings_report(fund, allocations),
            self.generate_cashflow_report(fund, cash_reserve, subscriptions, redemptions),
            self.generate_fee_report(fund, fee_schedule, accrued_fees, period_start, period_end),
            self.generate_investor_report(fund, accounts),
        ]
