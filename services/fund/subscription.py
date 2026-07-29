"""Subscription Engine.

Handles investor subscription (inflow) lifecycle:

    Investor → Subscribe → Confirm Shares → Update AUM

Flow
----
1. Validate subscription amount
2. Calculate shares at current NAV
3. Freeze cash reserve
4. Confirm order
5. Update fund shares / AUM
6. Settle
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from services.fund.models import (
    CashReserve,
    FeeSchedule,
    Fund,
    InvestorAccount,
    SubscriptionOrder,
    SubscriptionStatus,
)


class SubscriptionError(Exception):
    """Raised when subscription validation fails."""


class SubscriptionEngine:
    """Manages fund subscription (inflow) lifecycle.

    Usage::

        engine = SubscriptionEngine()
        order = engine.subscribe(
            fund=fund,
            account=investor,
            amount=1_000_000,
            cash=reserve,
            fee_schedule=fees,
        )
    """

    def subscribe(
        self,
        fund: Fund,
        account: InvestorAccount,
        amount: float,
        cash: CashReserve,
        fee_schedule: Optional[FeeSchedule] = None,
        settlement_date: Optional[date] = None,
    ) -> SubscriptionOrder:
        """Process a subscription.

        Parameters
        ----------
        fund : Fund
            The target fund.
        account : InvestorAccount
            The investor's account.
        amount : float
            Subscription amount in fund currency.
        cash : CashReserve
            Fund cash reserve.
        fee_schedule : FeeSchedule, optional
            Fee configuration for subscription fee.
        settlement_date : date, optional
            Settlement date (defaults to today).

        Returns
        -------
        SubscriptionOrder
        """
        # 1. Validate
        if amount <= 0:
            raise SubscriptionError("Subscription amount must be positive")
        if fund.nav <= 0:
            raise SubscriptionError(f"Invalid NAV: {fund.nav}")

        # 2. Apply subscription fee if configured
        net_amount = amount
        subscription_fee = 0.0
        if fee_schedule is not None and fee_schedule.subscription_fee_pct > 0:
            subscription_fee = fee_schedule.subscription_fee(amount)
            net_amount = amount - subscription_fee

        # 3. Calculate shares
        shares = fund.shares_from_amount(net_amount)

        # 4. Create order
        order = SubscriptionOrder(
            fund_id=fund.fund_id,
            account_id=account.account_id,
            amount=net_amount,
            nav=fund.nav,
            settlement_date=settlement_date or date.today(),
        )
        order.metadata["gross_amount"] = amount
        order.metadata["subscription_fee"] = subscription_fee

        # 5. Confirm
        order.confirm()

        # 6. Update fund state
        fund.total_shares += shares
        fund.aum += net_amount
        fund.cash_balance += net_amount

        # 7. Update investor account
        account.add_shares(shares=shares, cost=net_amount)

        # 8. Update cash reserve
        cash.total += net_amount

        # 9. Settle
        order.settle()

        return order

    def validate(
        self,
        fund: Fund,
        amount: float,
        min_subscription: float = 0.0,
        max_subscription: Optional[float] = None,
    ) -> Dict[str, object]:
        """Validate a subscription request before processing.

        Returns
        -------
        dict with keys: valid (bool), reason (str), shares (float)
        """
        if amount <= 0:
            return {"valid": False, "reason": "Amount must be positive", "shares": 0}
        if amount < min_subscription:
            return {
                "valid": False,
                "reason": f"Below minimum subscription: {min_subscription}",
                "shares": 0,
            }
        if max_subscription is not None and amount > max_subscription:
            return {
                "valid": False,
                "reason": f"Above maximum subscription: {max_subscription}",
                "shares": 0,
            }
        if fund.nav <= 0:
            return {"valid": False, "reason": "Invalid NAV", "shares": 0}

        shares = fund.shares_from_amount(amount)
        return {"valid": True, "reason": "", "shares": shares}

    def get_pending_orders(
        self, orders: List[SubscriptionOrder], account_id: Optional[str] = None
    ) -> List[SubscriptionOrder]:
        """Filter pending subscription orders."""
        result = [o for o in orders if o.status == SubscriptionStatus.PENDING]
        if account_id:
            result = [o for o in result if o.account_id == account_id]
        return result

    def get_order_summary(self, order: SubscriptionOrder) -> Dict[str, object]:
        return order.to_dict()
