"""Redemption Engine.

Handles investor redemption (outflow) lifecycle:

    Investor → Redeem Shares → Confirm → Pay Cash → Update AUM

Settlement types supported:
    - T+0: same-day settlement
    - T+1: next business day
    - T+2: T+2 settlement
    - T+N: custom N-day settlement
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from services.fund.models import (
    CashReserve,
    FeeSchedule,
    Fund,
    InvestorAccount,
    RedemptionOrder,
    RedemptionType,
    SubscriptionStatus,
)


class RedemptionError(Exception):
    """Raised when redemption validation fails."""


class RedemptionEngine:
    """Manages fund redemption (outflow) lifecycle.

    Usage::

        engine = RedemptionEngine()
        order = engine.redeem(
            fund=fund,
            account=investor,
            shares=500_000,
            cash=reserve,
            fee_schedule=fees,
            redemption_type=RedemptionType.T1,
        )
    """

    def redeem(
        self,
        fund: Fund,
        account: InvestorAccount,
        shares: float,
        cash: CashReserve,
        fee_schedule: Optional[FeeSchedule] = None,
        redemption_type: RedemptionType = RedemptionType.T1,
    ) -> RedemptionOrder:
        """Process a redemption.

        Parameters
        ----------
        fund : Fund
            The target fund.
        account : InvestorAccount
            The investor's account.
        shares : float
            Number of shares to redeem.
        cash : CashReserve
            Fund cash reserve.
        fee_schedule : FeeSchedule, optional
            Fee configuration for redemption fee.
        redemption_type : RedemptionType
            Settlement schedule (T+0, T+1, T+2, T+N).

        Returns
        -------
        RedemptionOrder
        """
        # 1. Validate
        if shares <= 0:
            raise RedemptionError("Redemption shares must be positive")
        if account.shares < shares:
            raise RedemptionError(
                f"Insufficient shares: {account.shares} < {shares}"
            )
        if fund.nav <= 0:
            raise RedemptionError(f"Invalid NAV: {fund.nav}")

        # 2. Calculate redemption amount
        gross_amount = fund.amount_from_shares(shares)

        redemption_fee = 0.0
        if fee_schedule is not None and fee_schedule.redemption_fee_pct > 0:
            redemption_fee = fee_schedule.redemption_fee(gross_amount)

        net_amount = gross_amount - redemption_fee

        # 3. Verify cash availability
        if net_amount > cash.available:
            raise RedemptionError(
                f"Insufficient cash for redemption: {cash.available} < {net_amount}"
            )

        # 4. Calculate settlement date
        settlement_date = self._settlement_date(redemption_type)

        # 5. Create order
        order = RedemptionOrder(
            fund_id=fund.fund_id,
            account_id=account.account_id,
            shares=shares,
            nav=fund.nav,
            redemption_type=redemption_type,
            settlement_date=settlement_date,
        )
        order.metadata["gross_amount"] = gross_amount
        order.metadata["redemption_fee"] = redemption_fee
        order.metadata["net_amount"] = net_amount

        # 6. Reserve cash for redemption
        cash.reserve_redemption(net_amount)

        # 7. Update investor account (remove shares)
        account.remove_shares(shares)

        # 8. Update fund state
        fund.total_shares -= shares
        fund.aum -= gross_amount

        # 9. Confirm
        order.confirm()

        return order

    def settle(self, order: RedemptionOrder, cash: CashReserve) -> None:
        """Settle a confirmed redemption (pay cash)."""
        if order.status != SubscriptionStatus.CONFIRMED:
            raise RedemptionError(f"Cannot settle order in status {order.status}")

        net_amount = order.metadata.get("net_amount", order.redemption_amount)
        cash.release_redemption(net_amount)
        order.settle()

    def _settlement_date(self, redemption_type: RedemptionType) -> date:
        """Calculate settlement date based on redemption type."""
        today = date.today()
        offset_map = {
            RedemptionType.T0: 0,
            RedemptionType.T1: 1,
            RedemptionType.T2: 2,
            RedemptionType.TN: 3,  # default T+3 for TN
        }
        days = offset_map.get(redemption_type, 3)
        return today + timedelta(days=days)

    def validate(
        self,
        account: InvestorAccount,
        fund: Fund,
        shares: float,
        cash: CashReserve,
        max_redemption_ratio: float = 1.0,
    ) -> Dict[str, object]:
        """Validate a redemption request.

        Parameters
        ----------
        max_redemption_ratio : float
            Max fraction of fund shares that can be redeemed at once.
        """
        if shares <= 0:
            return {"valid": False, "reason": "Shares must be positive"}
        if account.shares < shares:
            return {"valid": False, "reason": f"Insufficient shares: {account.shares} < {shares}"}

        # Check max redemption ratio (prevent run on fund)
        if fund.total_shares > 0 and (shares / fund.total_shares) > max_redemption_ratio:
            return {
                "valid": False,
                "reason": f"Redemption exceeds {max_redemption_ratio*100:.0f}% of fund",
            }

        amount = fund.amount_from_shares(shares)
        if amount > cash.available:
            return {
                "valid": False,
                "reason": f"Insufficient fund cash: {cash.available} < {amount}",
            }

        return {"valid": True, "reason": "", "amount": amount}

    def get_pending_settlements(
        self, orders: List[RedemptionOrder], as_of: Optional[date] = None
    ) -> List[RedemptionOrder]:
        """Get redemptions that are confirmed but not yet settled."""
        as_of = as_of or date.today()
        return [
            o
            for o in orders
            if o.status == SubscriptionStatus.CONFIRMED and o.settlement_date <= as_of
        ]

    def get_order_summary(self, order: RedemptionOrder) -> Dict[str, object]:
        return order.to_dict()
