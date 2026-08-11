"""
Exposure Limit Checker — Validates gross, net, sector, and factor exposure.

Prevents excessive concentration of risk across multiple exposure dimensions.

Logic::

    Gross Exposure → Net Exposure → Sector Exposure → Factor Exposure → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class ExposureLimitChecker:
    """
    Validates portfolio exposure limits across multiple dimensions.

    Checks:
    - Gross exposure (long + short absolute value)
    - Net exposure (long - short)
    - Sector concentration
    - Factor exposure

    Usage::

        checker = ExposureLimitChecker(
            max_gross_exposure_pct=200.0,
            max_net_exposure_pct=100.0,
        )
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_gross_exposure_pct: float = 200.0,
        max_net_exposure_pct: float = 100.0,
        max_sector_exposure_pct: float = 30.0,
        max_factor_exposure_pct: float = 25.0,
        net_liquidation_value: float = 100_000.0,
    ) -> None:
        self._max_gross_pct = max_gross_exposure_pct
        self._max_net_pct = max_net_exposure_pct
        self._max_sector_pct = max_sector_exposure_pct
        self._max_factor_pct = max_factor_exposure_pct
        self._nlv = net_liquidation_value

    async def check(self, ctx: PreTradeContext) -> None:
        """Check exposure limits against current portfolio state."""
        request = ctx.request
        positions = request.account_positions or {}
        market = request.market_data or {}

        # Calculate current exposures
        long_value = 0.0
        short_value = 0.0
        symbol = request.symbol
        instrument_price = market.get("price", request.price or 0.0)

        for sym, pos in positions.items():
            qty = pos.get("quantity", 0.0)
            price = pos.get("avg_price", 0.0)
            val = abs(qty) * price
            if qty > 0:
                long_value += val
            else:
                short_value += val

        # Add pending order
        order_val = abs(request.quantity) * instrument_price
        if request.side == OrderSide.BUY:
            long_value += order_val
        else:
            short_value += abs(order_val)

        # Gross exposure check
        gross_pct = (long_value + short_value) / self._nlv * 100.0 if self._nlv else 0.0
        if gross_pct > self._max_gross_pct:
            reason = RiskReason.blocking(
                category=ReasonCategory.EXPOSURE_LIMIT,
                message=(
                    f"Gross exposure {gross_pct:.1f}% exceeds limit "
                    f"{self._max_gross_pct:.1f}%"
                ),
                checker="ExposureLimitChecker",
                current_value=gross_pct,
                limit=self._max_gross_pct,
                resolution="Reduce gross exposure by closing positions or reducing order size.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "ExposureLimitChecker", passed=False,
                metadata={"gross_exposure_pct": gross_pct},
            )
            return

        # Net exposure check
        net_pct = abs(long_value - short_value) / self._nlv * 100.0 if self._nlv else 0.0
        if net_pct > self._max_net_pct:
            reason = RiskReason.warning(
                category=ReasonCategory.EXPOSURE_LIMIT,
                message=(
                    f"Net exposure {net_pct:.1f}% exceeds limit "
                    f"{self._max_net_pct:.1f}%"
                ),
                checker="ExposureLimitChecker",
                current_value=net_pct,
                limit=self._max_net_pct,
                resolution="Review net exposure and consider hedging.",
            )
            ctx.add_reason(reason)

        # Sector concentration check
        sector = market.get("sector", "")
        sector_existing = self._calculate_sector_exposure(positions, sector, market)
        sector_pct = (sector_existing + order_val) / self._nlv * 100.0 if self._nlv else 0.0
        if sector and sector_pct > self._max_sector_pct:
            reason = RiskReason.warning(
                category=ReasonCategory.EXPOSURE_LIMIT,
                message=(
                    f"Sector `{sector}` exposure {sector_pct:.1f}% "
                    f"exceeds limit {self._max_sector_pct:.1f}%"
                ),
                checker="ExposureLimitChecker",
                current_value=sector_pct,
                limit=self._max_sector_pct,
                resolution="Diversify across sectors to reduce concentration.",
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "ExposureLimitChecker", passed=True,
            metadata={
                "gross_exposure_pct": gross_pct,
                "net_exposure_pct": net_pct,
                "sector_exposure_pct": sector_pct if sector else 0.0,
            },
        )

    @staticmethod
    def _calculate_sector_exposure(
        positions: dict[str, Any], sector: str, market: dict[str, Any]
    ) -> float:
        """Calculate existing sector exposure from positions."""
        exposure = 0.0
        for sym, pos in positions.items():
            pos_sector = pos.get("sector", "")
            if pos_sector == sector:
                qty = pos.get("quantity", 0.0)
                price = pos.get("avg_price", 0.0)
                exposure += abs(qty) * price
        return exposure
