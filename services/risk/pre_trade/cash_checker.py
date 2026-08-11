"""
Cash Checker — Validates sufficient cash balance for order execution.

Ensures the account has enough settled cash to cover the order cost.
More conservative than Buying Power (no margin multiplier).

Logic::

    Available Cash ≥ Required Cash → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class CashChecker:
    """
    Validates sufficient cash balance for orders.

    Cash-checked orders require fully settled cash, not margin.
    Used for cash accounts or instruments that require 100% cash
    collateral (e.g., certain options, crypto spot).

    Usage::

        checker = CashChecker(require_cash_account=False)
        await checker.check(ctx)
    """

    def __init__(
        self,
        require_cash_account: bool = False,
        cash_buffer_pct: float = 2.0,
    ) -> None:
        self._require_cash_account = require_cash_account
        self._cash_buffer_pct = cash_buffer_pct

    async def check(self, ctx: PreTradeContext) -> None:
        """Check cash balance adequacy for the order."""
        request = ctx.request
        balances = request.account_balances or {}
        market = request.market_data or {}

        available_cash = balances.get("cash", 0.0)
        settled_cash = balances.get("settled_cash", available_cash)

        # For buy orders
        if request.is_buy:
            cash_needed = request.quantity * (market.get("price", request.price or 0.0))
            # Add buffer
            cash_needed *= (1.0 + self._cash_buffer_pct / 100.0)

            check_cash = settled_cash if self._require_cash_account else available_cash

            if cash_needed > check_cash:
                reason = RiskReason.blocking(
                    category=ReasonCategory.CASH,
                    message=(
                        f"Insufficient cash: need {cash_needed:.2f}, "
                        f"available {check_cash:.2f}"
                    ),
                    checker="CashChecker",
                    current_value=check_cash,
                    limit=cash_needed,
                    resolution="Deposit funds or reduce order size.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "CashChecker", passed=False,
                    metadata={"available_cash": check_cash, "cash_needed": cash_needed},
                )
                return

            ctx.add_checker_result(
                "CashChecker", passed=True,
                metadata={"available_cash": check_cash, "cash_needed": cash_needed},
            )
            return

        # For sell orders — verify we have the shares
        positions = request.account_positions or {}
        symbol_position = positions.get(request.symbol, {})
        held_quantity = symbol_position.get("quantity", 0.0)

        if request.quantity > held_quantity:
            reason = RiskReason.blocking(
                category=ReasonCategory.CASH,
                message=(
                    f"Insufficient shares for sell: have {held_quantity:.0f}, "
                    f"trying to sell {request.quantity:.0f}"
                ),
                checker="CashChecker",
                current_value=held_quantity,
                limit=request.quantity,
                resolution="Reduce sell quantity or acquire more shares.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "CashChecker", passed=False,
                metadata={"held_quantity": held_quantity, "sell_quantity": request.quantity},
            )
            return

        ctx.add_checker_result(
            "CashChecker", passed=True,
            metadata={"held_quantity": held_quantity, "sell_quantity": request.quantity},
        )
