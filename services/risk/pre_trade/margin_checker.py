"""
Margin Checker — Validates margin requirements for margin-eligible orders.

Supports initial margin, maintenance margin, and stress margin checks
for equity, futures, options, forex, and leveraged products.

Logic::

    Initial Margin → Maintenance Margin → Stress Margin → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide, InstrumentType
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class MarginChecker:
    """
    Validates margin requirements for all order types.

    Supports:
    - Initial margin (for new positions)
    - Maintenance margin (for existing positions)
    - Stress margin (additional buffer for volatile markets)

    Usage::

        checker = MarginChecker()
        await checker.check(ctx)
    """

    def __init__(
        self,
        initial_margin_rates: Optional[dict[str, float]] = None,
        maintenance_margin_rates: Optional[dict[str, float]] = None,
        stress_margin_multiplier: float = 1.5,
    ) -> None:
        self._initial_margin_rates = initial_margin_rates or {
            "equity": 0.50,
            "etf": 0.50,
            "future": 0.10,
            "option": 1.00,
            "forex": 0.02,
            "crypto": 1.00,
            "cfd": 0.20,
        }
        self._maintenance_margin_rates = maintenance_margin_rates or {
            "equity": 0.25,
            "etf": 0.25,
            "future": 0.05,
            "option": 1.00,
            "forex": 0.01,
            "crypto": 0.50,
            "cfd": 0.10,
        }
        self._stress_multiplier = stress_margin_multiplier

    async def check(self, ctx: PreTradeContext) -> None:
        """Check margin requirements for the order."""
        request = ctx.request
        balances = request.account_balances or {}
        positions = request.account_positions or {}
        market = request.market_data or {}

        inst = request.instrument_type.value
        initial_rate = self._initial_margin_rates.get(inst, 0.50)
        maintenance_rate = self._maintenance_margin_rates.get(inst, 0.25)

        instrument_price = market.get("price", request.price or 0.0)
        order_value = request.quantity * instrument_price

        # Available margin
        available_margin = balances.get(
            "available_margin",
            balances.get("excess_liquidity", 0.0),
        )
        nlv = balances.get("net_liquidation_value", available_margin * 2.0)

        # Initial margin required for this order
        if request.side == OrderSide.BUY:
            initial_margin_required = order_value * initial_rate
        else:
            # Selling: margin is on the proceeds or the position value
            current_pos = positions.get(request.symbol, {})
            current_value = current_pos.get("quantity", 0.0) * current_pos.get(
                "avg_price", instrument_price
            )
            initial_margin_required = current_value * initial_rate

        # Total initial margin (existing + new order)
        existing_margin = balances.get("initial_margin", 0.0)
        total_initial_margin = existing_margin + initial_margin_required

        # Maintenance margin
        maintenance_margin_required = order_value * maintenance_rate
        total_maintenance_margin = (
            balances.get("maintenance_margin", 0.0) + maintenance_margin_required
        )

        # Stress margin
        stress_margin_required = initial_margin_required * self._stress_multiplier

        # --- Initial Margin Check ---
        if total_initial_margin > available_margin:
            reason = RiskReason.blocking(
                category=ReasonCategory.MARGIN,
                message=(
                    f"Insufficient margin: need {total_initial_margin:.2f} "
                    f"initial margin, have {available_margin:.2f}"
                ),
                checker="MarginChecker",
                current_value=available_margin,
                limit=total_initial_margin,
                resolution="Reduce order size or add margin collateral.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "MarginChecker", passed=False,
                metadata={
                    "initial_margin_required": total_initial_margin,
                    "available_margin": available_margin,
                },
            )
            return

        # --- Maintenance Margin Check ---
        if nlv > 0 and (total_maintenance_margin / nlv) > (1.0 - maintenance_rate):
            reason = RiskReason.warning(
                category=ReasonCategory.MARGIN,
                message=(
                    f"Maintenance margin approaching limit: "
                    f"{total_maintenance_margin:.2f} / NLV {nlv:.2f}"
                ),
                checker="MarginChecker",
                current_value=total_maintenance_margin,
                limit=nlv * (1.0 - maintenance_rate),
            )
            ctx.add_reason(reason)

        # --- Stress Margin Warning ---
        if stress_margin_required > available_margin * 0.5:
            reason = RiskReason.info(
                category=ReasonCategory.MARGIN,
                message=(
                    f"Stress margin {stress_margin_required:.2f} "
                    f"is significant relative to available margin."
                ),
                checker="MarginChecker",
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "MarginChecker", passed=True,
            metadata={
                "initial_margin": total_initial_margin,
                "maintenance_margin": total_maintenance_margin,
                "stress_margin": stress_margin_required,
                "available_margin": available_margin,
            },
        )
