"""Dividend Processor — handles dividend events in backtesting.

Processes cash dividends, stock dividends, and dividend reinvestment
to ensure accurate total return calculations.

Types::

    Cash Dividend → Stock Dividend → Dividend Reinvestment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DividendType(str, Enum):
    """Types of dividend events."""

    CASH = "cash"
    STOCK = "stock"
    SPECIAL = "special"
    RETURN_OF_CAPITAL = "return_of_capital"


@dataclass
class DividendEvent:
    """A dividend distribution event."""

    dividend_id: str
    symbol: str
    dividend_type: DividendType
    ex_date: str
    pay_date: str
    amount: float  # cash: per share; stock: ratio (0.1 = 10%)
    currency: str = "CNY"
    metadata: Dict[str, Any] = field(default_factory=dict)


class DividendProcessor:
    """Processes dividend events during backtesting.

    Responsibilities:
    * Track ex-dividend dates and adjust position cost basis
    * Calculate cash dividend income
    * Handle stock dividend share adjustments
    * Support dividend reinvestment
    """

    def __init__(
        self,
        reinvest: bool = False,
        tax_rate: float = 0.10,  # dividend tax rate
    ) -> None:
        self._reinvest = reinvest
        self._tax_rate = tax_rate
        self._dividends: Dict[str, List[DividendEvent]] = {}
        self._total_dividend_income = 0.0
        self._total_dividend_tax = 0.0

    # ── registration ───────────────────────────────────────────────────────

    def register_dividend(self, event: DividendEvent) -> None:
        """Register a dividend event."""
        key = event.ex_date
        if key not in self._dividends:
            self._dividends[key] = []
        self._dividends[key].append(event)
        logger.debug("Registered %s dividend for %s: %.4f", event.dividend_type.value, event.symbol, event.amount)

    def register_cash_dividend(
        self,
        symbol: str,
        ex_date: str,
        pay_date: str,
        amount: float,
    ) -> None:
        """Register a cash dividend per share."""
        self.register_dividend(DividendEvent(
            dividend_id=f"{symbol}_{ex_date}_cash",
            symbol=symbol,
            dividend_type=DividendType.CASH,
            ex_date=ex_date,
            pay_date=pay_date,
            amount=amount,
        ))

    def register_stock_dividend(
        self,
        symbol: str,
        ex_date: str,
        pay_date: str,
        ratio: float,
    ) -> None:
        """Register a stock dividend (e.g., 0.1 = 10% bonus shares)."""
        self.register_dividend(DividendEvent(
            dividend_id=f"{symbol}_{ex_date}_stock",
            symbol=symbol,
            dividend_type=DividendType.STOCK,
            ex_date=ex_date,
            pay_date=pay_date,
            amount=ratio,
        ))

    # ── processing ─────────────────────────────────────────────────────────

    async def process(
        self, market_event: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process dividend events for a given market event date.

        Args:
            market_event: Market replay event with timestamp.

        Returns:
            List of processed dividend dicts for portfolio/cash adjustment.
        """
        timestamp = market_event.get("timestamp", "")
        date = timestamp[:10]

        divs = self._dividends.get(date, [])
        processed = []
        for div in divs:
            processed.append({
                "symbol": div.symbol,
                "dividend_type": div.dividend_type.value,
                "amount": div.amount,
                "ex_date": div.ex_date,
                "pay_date": div.pay_date,
                "reinvest": self._reinvest,
            })
        return processed

    async def apply(
        self,
        dividend_data: Dict[str, Any],
        portfolio: Dict[str, Dict[str, Any]],
        cash: float,
    ) -> Dict[str, Any]:
        """Apply a dividend to portfolio and cash.

        Args:
            dividend_data: Dividend event data.
            portfolio: Current portfolio positions.
            cash: Current cash balance.

        Returns:
            Dict with adjusted cash and portfolio.
        """
        symbol = dividend_data.get("symbol", "")
        dividend_type = dividend_data.get("dividend_type", "")
        amount = dividend_data.get("amount", 0)

        if symbol not in portfolio:
            return {"cash": cash, "portfolio": portfolio}

        position = portfolio[symbol]
        qty = position.get("quantity", 0)

        if dividend_type == DividendType.CASH.value:
            # Cash dividend
            income = qty * amount
            tax = income * self._tax_rate
            net_income = income - tax
            cash += net_income
            self._total_dividend_income += net_income
            self._total_dividend_tax += tax

            if self._reinvest:
                # Reinvest: buy more shares at current price
                price = position.get("market_value", 0) / max(abs(qty), 1)
                if price > 0:
                    new_shares = net_income / price
                    portfolio[symbol]["quantity"] += new_shares
                    logger.info(
                        "Dividend reinvest: %s +%.0f shares (%.2f CNY)",
                        symbol, new_shares, net_income,
                    )

        elif dividend_type == DividendType.STOCK.value:
            # Stock dividend: bonus shares
            bonus_shares = qty * amount
            portfolio[symbol]["quantity"] += bonus_shares
            cost_basis = position.get("cost_basis", 0) * (qty / (qty + bonus_shares))
            portfolio[symbol]["cost_basis"] = cost_basis
            logger.info("Stock dividend: %s +%.0f bonus shares", symbol, bonus_shares)

        return {"cash": cash, "portfolio": portfolio}

    # ── configuration ──────────────────────────────────────────────────────

    def set_reinvest(self, enabled: bool) -> None:
        """Enable or disable dividend reinvestment."""
        self._reinvest = enabled
        logger.info("Dividend reinvestment: %s", "enabled" if enabled else "disabled")

    def set_tax_rate(self, rate: float) -> None:
        """Set dividend tax rate."""
        self._tax_rate = rate

    # ── query ──────────────────────────────────────────────────────────────

    def get_dividends_for_date(self, date: str) -> List[DividendEvent]:
        """Get all dividends for a specific date."""
        return self._dividends.get(date, [])

    def get_yield(
        self, symbol: str, price: float
    ) -> Optional[float]:
        """Estimate dividend yield for a symbol."""
        total_div = 0.0
        for divs in self._dividends.values():
            for div in divs:
                if div.symbol == symbol and div.dividend_type == DividendType.CASH:
                    total_div += div.amount
        if price <= 0:
            return None
        return total_div / price

    def get_stats(self) -> Dict[str, Any]:
        """Return dividend processor statistics."""
        total_cash = sum(
            1 for divs in self._dividends.values()
            for d in divs if d.dividend_type == DividendType.CASH
        )
        total_stock = sum(
            1 for divs in self._dividends.values()
            for d in divs if d.dividend_type == DividendType.STOCK
        )
        return {
            "total_dates": len(self._dividends),
            "total_events": sum(len(v) for v in self._dividends.values()),
            "cash_dividends": total_cash,
            "stock_dividends": total_stock,
            "total_dividend_income": self._total_dividend_income,
            "total_dividend_tax": self._total_dividend_tax,
            "reinvest": self._reinvest,
            "tax_rate": self._tax_rate,
        }
