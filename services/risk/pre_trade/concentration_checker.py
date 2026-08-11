"""
Concentration Checker — Validates portfolio concentration limits.

Prevents over-concentration in single symbols, sectors, or asset classes.
Ensures diversification requirements are met before order entry.

Logic::

    Symbol Concentration → Sector Concentration → Asset Class Concentration
    → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class ConcentrationChecker:
    """
    Validates portfolio concentration across multiple dimensions.

    Enforces limits on:
    - Single symbol weight in portfolio
    - Single sector weight
    - Single asset class exposure

    Usage::

        checker = ConcentrationChecker(
            max_symbol_pct=20.0,
            max_sector_pct=40.0,
        )
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_symbol_pct: float = 20.0,
        max_sector_pct: float = 40.0,
        max_asset_class_pct: float = 60.0,
        portfolio_value: float = 100_000.0,
    ) -> None:
        self._max_symbol_pct = max_symbol_pct
        self._max_sector_pct = max_sector_pct
        self._max_asset_class_pct = max_asset_class_pct
        self._portfolio_value = portfolio_value

    async def check(self, ctx: PreTradeContext) -> None:
        """Check portfolio concentration against limits."""
        request = ctx.request
        positions = request.account_positions or {}
        market = request.market_data or {}

        portfolio_value = market.get("portfolio_value", self._portfolio_value)
        if portfolio_value <= 0:
            portfolio_value = self._portfolio_value

        instrument_price = market.get("price", request.price or 0.0)
        order_value = request.quantity * instrument_price

        # --- Symbol Concentration ---
        symbol_position = positions.get(request.symbol, {})
        current_symbol_value = (
            abs(symbol_position.get("quantity", 0.0))
            * symbol_position.get("avg_price", instrument_price)
        )
        if request.side == OrderSide.BUY:
            resulting_symbol_value = current_symbol_value + order_value
        else:
            resulting_symbol_value = max(0, current_symbol_value - order_value)

        symbol_pct = (
            (resulting_symbol_value / portfolio_value) * 100.0
            if portfolio_value
            else 0.0
        )
        if symbol_pct > self._max_symbol_pct:
            reason = RiskReason.blocking(
                category=ReasonCategory.CONCENTRATION,
                message=(
                    f"Symbol concentration {symbol_pct:.1f}% exceeds "
                    f"limit {self._max_symbol_pct:.1f}% for {request.symbol}"
                ),
                checker="ConcentrationChecker",
                current_value=symbol_pct,
                limit=self._max_symbol_pct,
                resolution="Reduce position size or diversify into other symbols.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "ConcentrationChecker", passed=False,
                metadata={"symbol_pct": symbol_pct, "symbol": request.symbol},
            )
            return

        # --- Sector Concentration ---
        sector = market.get("sector", "")
        if sector:
            sector_value = self._calculate_sector_value(positions, sector)
            if request.is_buy:
                sector_value += order_value
            sector_pct = (sector_value / portfolio_value * 100.0) if portfolio_value else 0.0
            if sector_pct > self._max_sector_pct:
                reason = RiskReason.warning(
                    category=ReasonCategory.CONCENTRATION,
                    message=(
                        f"Sector `{sector}` concentration {sector_pct:.1f}% "
                        f"exceeds limit {self._max_sector_pct:.1f}%"
                    ),
                    checker="ConcentrationChecker",
                    current_value=sector_pct,
                    limit=self._max_sector_pct,
                    resolution="Reduce sector exposure or diversify.",
                )
                ctx.add_reason(reason)

        # --- Asset Class Concentration ---
        inst_type = request.instrument_type.value
        asset_class_value = self._calculate_asset_class_value(positions, inst_type)
        if request.is_buy:
            asset_class_value += order_value
        asset_class_pct = (
            (asset_class_value / portfolio_value) * 100.0 if portfolio_value else 0.0
        )
        if asset_class_pct > self._max_asset_class_pct:
            reason = RiskReason.warning(
                category=ReasonCategory.CONCENTRATION,
                message=(
                    f"Asset class `{inst_type}` concentration "
                    f"{asset_class_pct:.1f}% exceeds limit "
                    f"{self._max_asset_class_pct:.1f}%"
                ),
                checker="ConcentrationChecker",
                current_value=asset_class_pct,
                limit=self._max_asset_class_pct,
                resolution="Diversify across asset classes.",
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "ConcentrationChecker", passed=True,
            metadata={
                "symbol_pct": symbol_pct,
                "sector_pct": sector_pct if sector else 0.0,
                "asset_class_pct": asset_class_pct,
            },
        )

    @staticmethod
    def _calculate_sector_value(
        positions: dict[str, Any], sector: str
    ) -> float:
        """Calculate total value of positions in a given sector."""
        total = 0.0
        for pos in positions.values():
            if pos.get("sector") == sector:
                qty = abs(pos.get("quantity", 0.0))
                price = pos.get("avg_price", 0.0)
                total += qty * price
        return total

    @staticmethod
    def _calculate_asset_class_value(
        positions: dict[str, Any], asset_class: str
    ) -> float:
        """Calculate total value of positions in a given asset class."""
        total = 0.0
        for pos in positions.values():
            if pos.get("instrument_type") == asset_class:
                qty = abs(pos.get("quantity", 0.0))
                price = pos.get("avg_price", 0.0)
                total += qty * price
        return total
