"""Tax Model — market-specific transaction tax calculation.

Supports stamp duty, transaction tax, and regional tax across
different markets with configurable rates.

Tax Types::

    Stamp Duty → Transaction Tax → Regional Tax
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaxType(str, Enum):
    """Tax categories."""

    STAMP_DUTY = "stamp_duty"
    TRANSACTION_TAX = "transaction_tax"
    REGIONAL_TAX = "regional_tax"
    NONE = "none"


class TaxModel:
    """Market-specific tax calculator.

    Different markets have different tax structures:
    * CN A-Share: 0.05% stamp duty on sell, no capital gains tax
    * US: No stamp duty, capital gains tax (not modeled here)
    * HK: 0.13% stamp duty (combined buy+sell)

    Usage::

        tax_model = TaxModel(stamp_duty_bps=5.0, applies_to="sell")
        tax = tax_model.calculate(trade_value=100000, quantity=1000, side="sell")
    """

    def __init__(
        self,
        stamp_duty_bps: float = 5.0,
        transaction_tax_bps: float = 0.0,
        regional_tax_bps: float = 0.0,
        applies_to: str = "sell",  # "buy", "sell", or "both"
    ) -> None:
        self._stamp_duty_bps = stamp_duty_bps
        self._transaction_tax_bps = transaction_tax_bps
        self._regional_tax_bps = regional_tax_bps
        self._applies_to = applies_to

        # Tracking
        self._total_stamp_duty = 0.0
        self._total_transaction_tax = 0.0
        self._total_regional_tax = 0.0
        self._total_trades = 0

    # ── calculation ────────────────────────────────────────────────────────

    def calculate(
        self,
        trade_value: float,
        quantity: float,
        side: str = "buy",
    ) -> float:
        """Calculate total transaction taxes.

        Args:
            trade_value: Trade notional value.
            quantity: Number of shares/units.
            side: buy or sell.

        Returns:
            Total tax cost.
        """
        if self._applies_to not in (side, "both"):
            return 0.0

        stamp_duty = trade_value * (self._stamp_duty_bps / 10000)
        transaction_tax = trade_value * (self._transaction_tax_bps / 10000)
        regional_tax = trade_value * (self._regional_tax_bps / 10000)

        self._total_stamp_duty += stamp_duty
        self._total_transaction_tax += transaction_tax
        self._total_regional_tax += regional_tax
        self._total_trades += 1

        return stamp_duty + transaction_tax + regional_tax

    def calculate_stamp_duty(self, trade_value: float, side: str = "buy") -> float:
        """Calculate only stamp duty."""
        if self._applies_to not in (side, "both"):
            return 0.0
        duty = trade_value * (self._stamp_duty_bps / 10000)
        self._total_stamp_duty += duty
        return duty

    def stamps_only(self) -> bool:
        """Check if only stamp duty (no other taxes) applies."""
        return (
            self._transaction_tax_bps == 0.0
            and self._regional_tax_bps == 0.0
        )

    # ── configuration ──────────────────────────────────────────────────────

    def set_market(
        self,
        market: str,
        stamp_duty_bps: Optional[float] = None,
        applies_to: Optional[str] = None,
    ) -> None:
        """Configure for a specific market."""
        market_configs = {
            "cn": {"stamp_duty_bps": 5.0, "applies_to": "sell"},
            "us": {"stamp_duty_bps": 0.0, "applies_to": "none"},
            "hk": {"stamp_duty_bps": 13.0, "applies_to": "both"},
            "jp": {"stamp_duty_bps": 0.0, "applies_to": "none"},
            "uk": {"stamp_duty_bps": 50.0, "applies_to": "buy"},
        }
        config = market_configs.get(market, market_configs["cn"])
        self._stamp_duty_bps = stamp_duty_bps or config["stamp_duty_bps"]
        self._applies_to = applies_to or config["applies_to"]
        logger.info("Tax model configured for market: %s", market)

    def get_stats(self) -> Dict[str, Any]:
        """Return tax model statistics."""
        return {
            "stamp_duty_bps": self._stamp_duty_bps,
            "applies_to": self._applies_to,
            "total_stamp_duty": self._total_stamp_duty,
            "total_tax": self._total_stamp_duty + self._total_transaction_tax + self._total_regional_tax,
            "total_trades": self._total_trades,
        }
