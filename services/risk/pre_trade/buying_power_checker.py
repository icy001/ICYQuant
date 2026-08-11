"""
Buying Power Checker — Validates sufficient buying power for order entry.

Ensures the account has enough buying power to cover the order cost
including commissions and buffer requirements.

Logic::

    Available Buying Power ≥ Required Capital → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class BuyingPowerChecker:
    """
    Validates that the account has sufficient buying power for the order.

    Buying power accounts for margin requirements, cash reserves, and
    any holdback buffers configured for the account.

    Usage::

        checker = BuyingPowerChecker(buying_power_buffer_pct=5.0)
        await checker.check(ctx)
    """

    def __init__(
        self,
        buying_power_buffer_pct: float = 5.0,
        commission_rate_bps: float = 1.0,
        min_cash_reserve: float = 0.0,
    ) -> None:
        self._buffer_pct = buying_power_buffer_pct  # Extra buffer as % of order
        self._commission_bps = commission_rate_bps   # Commission in basis points
        self._min_cash_reserve = min_cash_reserve

    async def check(self, ctx: PreTradeContext) -> None:
        """Check buying power adequacy for the order."""
        request = ctx.request

        # Only relevant for BUY orders
        if not request.is_buy:
            ctx.add_checker_result(
                "BuyingPowerChecker", passed=True,
                metadata={"note": "Sell order; no buying power check needed."},
            )
            return

        balances = request.account_balances or {}
        market = request.market_data or {}

        available_buying_power = balances.get(
            "buying_power",
            balances.get("cash", 0.0) * 2.0  # Default: 2x cash for margin accounts
        )

        # Calculate required capital
        instrument_price = market.get("price", request.price or 0.0)
        order_value = request.quantity * instrument_price

        # Add commission
        commission = order_value * (self._commission_bps / 10000.0)

        # Add buffer
        buffer = order_value * (self._buffer_pct / 100.0)

        required_capital = order_value + commission + buffer + self._min_cash_reserve

        if required_capital > available_buying_power:
            shortfall = required_capital - available_buying_power
            reason = RiskReason.blocking(
                category=ReasonCategory.BUYING_POWER,
                message=(
                    f"Insufficient buying power: need "
                    f"{required_capital:.2f}, have {available_buying_power:.2f} "
                    f"(shortfall: {shortfall:.2f})"
                ),
                checker="BuyingPowerChecker",
                current_value=available_buying_power,
                limit=required_capital,
                resolution="Reduce order size or deposit additional funds.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "BuyingPowerChecker", passed=False,
                metadata={
                    "available_buying_power": available_buying_power,
                    "required_capital": required_capital,
                    "shortfall": shortfall,
                },
            )
            return

        # Warning if using >80% of buying power in one order
        usage_pct = (required_capital / available_buying_power * 100) if available_buying_power else 0
        if usage_pct > 80.0:
            reason = RiskReason.warning(
                category=ReasonCategory.BUYING_POWER,
                message=(
                    f"Order uses {usage_pct:.1f}% of available buying power."
                ),
                checker="BuyingPowerChecker",
                current_value=usage_pct,
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "BuyingPowerChecker", passed=True,
            metadata={
                "available_buying_power": available_buying_power,
                "required_capital": required_capital,
                "usage_pct": usage_pct,
            },
        )
