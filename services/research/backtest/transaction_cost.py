"""Transaction Cost — unified transaction cost aggregator.

Aggregates all transaction costs including commission, exchange fees,
clearing fees, stamp duty, taxes, and platform fees.

Cost Breakdown::

    Commission + Exchange Fee + Clearing Fee + Stamp Duty + Tax + Platform Fee
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .commission_model import CommissionModel, CommissionType
from .tax_model import TaxModel, TaxType
from .slippage_model import SlippageModel, SlippageMethod

logger = logging.getLogger(__name__)


class Market(str, Enum):
    """Supported trading markets."""

    CN = "cn"  # A-Share
    US = "us"  # US Market
    HK = "hk"  # Hong Kong
    JP = "jp"  # Japan
    UK = "uk"  # UK
    CUSTOM = "custom"


@dataclass
class TransactionCostBreakdown:
    """Detailed breakdown of a transaction's costs."""

    trade_value: float = 0.0
    commission: float = 0.0
    exchange_fee: float = 0.0
    clearing_fee: float = 0.0
    stamp_duty: float = 0.0
    transaction_tax: float = 0.0
    platform_fee: float = 0.0
    slippage_cost: float = 0.0
    borrow_cost: float = 0.0
    total_cost: float = 0.0
    cost_bps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_value": self.trade_value,
            "commission": self.commission,
            "exchange_fee": self.exchange_fee,
            "clearing_fee": self.clearing_fee,
            "stamp_duty": self.stamp_duty,
            "transaction_tax": self.transaction_tax,
            "platform_fee": self.platform_fee,
            "slippage_cost": self.slippage_cost,
            "borrow_cost": self.borrow_cost,
            "total_cost": self.total_cost,
            "cost_bps": self.cost_bps,
        }


class TransactionCost:
    """Unified transaction cost calculator.

    Aggregates all costs for a trade:
    * Commission (broker-specific)
    * Exchange and clearing fees
    * Stamp duty and taxes (market-specific)
    * Platform fees
    * Slippage cost (via SlippageModel)
    * Borrow cost (for short positions)

    Supports pre-configured market defaults and custom configurations.
    """

    # Default market configurations
    MARKET_DEFAULTS: Dict[str, Dict[str, Any]] = {
        Market.CN.value: {
            "commission_type": CommissionType.PERCENTAGE.value,
            "commission_rate": 0.0003,  # 0.03% (万三)
            "min_commission": 5.0,  # 5 CNY minimum
            "exchange_fee_bps": 0.5,  # 0.005%
            "clearing_fee_bps": 0.2,  # 0.002%
            "stamp_duty_bps": 5.0,  # 0.05% (sell only)
            "platform_fee_bps": 0.0,
        },
        Market.US.value: {
            "commission_type": CommissionType.PERCENTAGE.value,
            "commission_rate": 0.001,  # 0.1%
            "min_commission": 1.0,
            "exchange_fee_bps": 0.3,
            "clearing_fee_bps": 0.0,
            "stamp_duty_bps": 0.0,  # 0% for stocks
            "platform_fee_bps": 0.0,
        },
        Market.HK.value: {
            "commission_type": CommissionType.PERCENTAGE.value,
            "commission_rate": 0.0025,  # 0.25%
            "min_commission": 100.0,  # 100 HKD
            "exchange_fee_bps": 0.5,
            "clearing_fee_bps": 0.2,
            "stamp_duty_bps": 13.0,  # 0.13% (buy + sell)
            "platform_fee_bps": 0.0,
        },
    }

    def __init__(
        self,
        market: str = Market.CN.value,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._market = market
        self._commission_model = CommissionModel()
        self._tax_model = TaxModel()
        self._slippage_model = SlippageModel()
        self._total_cost = 0.0
        self._total_trade_value = 0.0
        self._trade_count = 0

        # Load config
        self._config = self.MARKET_DEFAULTS.get(market, self.MARKET_DEFAULTS[Market.CN.value]).copy()
        if config:
            self._config.update(config)

        self._apply_config()

    # ── calculation ────────────────────────────────────────────────────────

    def calculate(
        self,
        trade_value: float,
        quantity: float,
        price: float,
        side: str = "buy",
        is_short: bool = False,
        hold_days: int = 0,
        slippage_bps: Optional[float] = None,
    ) -> TransactionCostBreakdown:
        """Calculate total transaction cost for a trade.

        Args:
            trade_value: Total trade notional value.
            quantity: Trade quantity.
            price: Executed price.
            side: buy or sell.
            is_short: Whether this is a short position.
            hold_days: Days held (for borrow cost).
            slippage_bps: Optional pre-computed slippage in bps.

        Returns:
            Detailed cost breakdown.
        """
        # Commission
        commission = self._commission_model.calculate(
            trade_value, quantity, side
        )

        # Exchange & clearing fees
        exchange_fee = trade_value * (self._config.get("exchange_fee_bps", 0) / 10000)
        clearing_fee = trade_value * (self._config.get("clearing_fee_bps", 0) / 10000)

        # Stamp duty (market-specific, usually sell-side only)
        stamp_duty = 0.0
        if side == "sell":
            stamp_duty = trade_value * (self._config.get("stamp_duty_bps", 0) / 10000)

        # Transaction tax
        transaction_tax = self._tax_model.calculate(trade_value, quantity, side)

        # Platform fee
        platform_fee = trade_value * (self._config.get("platform_fee_bps", 0) / 10000)

        # Slippage cost
        slippage_cost = 0.0
        if slippage_bps:
            slippage_cost = trade_value * (slippage_bps / 10000)

        # Borrow cost (for short positions)
        borrow_cost = 0.0
        if is_short and hold_days > 0:
            borrow_cost = trade_value * 0.02 * (hold_days / 365)  # 2% annual borrow rate

        total = (
            commission + exchange_fee + clearing_fee + stamp_duty
            + transaction_tax + platform_fee + slippage_cost + borrow_cost
        )
        cost_bps = (total / trade_value * 10000) if trade_value > 0 else 0.0

        self._total_cost += total
        self._total_trade_value += trade_value
        self._trade_count += 1

        return TransactionCostBreakdown(
            trade_value=trade_value,
            commission=commission,
            exchange_fee=exchange_fee,
            clearing_fee=clearing_fee,
            stamp_duty=stamp_duty,
            transaction_tax=transaction_tax,
            platform_fee=platform_fee,
            slippage_cost=slippage_cost,
            borrow_cost=borrow_cost,
            total_cost=total,
            cost_bps=cost_bps,
        )

    def calculate_buy(self, trade_value: float, quantity: float) -> TransactionCostBreakdown:
        """Calculate cost for a buy trade."""
        return self.calculate(trade_value, quantity, trade_value / max(quantity, 1), "buy")

    def calculate_sell(self, trade_value: float, quantity: float) -> TransactionCostBreakdown:
        """Calculate cost for a sell trade."""
        return self.calculate(trade_value, quantity, trade_value / max(quantity, 1), "sell")

    def calculate_roundtrip(
        self,
        trade_value: float,
        quantity: float,
        price: float,
        hold_days: int = 1,
        is_short: bool = False,
    ) -> TransactionCostBreakdown:
        """Calculate round-trip (buy + sell) transaction cost."""
        buy = self.calculate(trade_value, quantity, price, "buy", is_short, hold_days)
        sell = self.calculate(trade_value, quantity, price, "sell", is_short, hold_days)

        return TransactionCostBreakdown(
            trade_value=trade_value,
            commission=buy.commission + sell.commission,
            exchange_fee=buy.exchange_fee + sell.exchange_fee,
            clearing_fee=buy.clearing_fee + sell.clearing_fee,
            stamp_duty=buy.stamp_duty + sell.stamp_duty,
            transaction_tax=buy.transaction_tax + sell.transaction_tax,
            platform_fee=buy.platform_fee + sell.platform_fee,
            slippage_cost=buy.slippage_cost + sell.slippage_cost,
            borrow_cost=buy.borrow_cost + sell.borrow_cost,
            total_cost=buy.total_cost + sell.total_cost,
            cost_bps=buy.cost_bps + sell.cost_bps,
        )

    # ── configuration ──────────────────────────────────────────────────────

    def set_market(self, market: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Switch to a different market configuration."""
        self._market = market
        self._config = self.MARKET_DEFAULTS.get(market, self.MARKET_DEFAULTS[Market.CN.value]).copy()
        if config:
            self._config.update(config)
        self._apply_config()
        logger.info("Transaction cost market set to: %s", market)

    def _apply_config(self) -> None:
        """Apply configuration to sub-models."""
        commission_type = self._config.get("commission_type", "percentage")
        self._commission_model.set_type(CommissionType(commission_type))
        self._commission_model.set_params(
            rate=self._config.get("commission_rate"),
            min_cost=self._config.get("min_commission"),
        )

    # ── query ──────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return cost statistics."""
        return {
            "market": self._market,
            "total_cost": self._total_cost,
            "total_trade_value": self._total_trade_value,
            "trade_count": self._trade_count,
            "avg_cost_bps": (self._total_cost / self._total_trade_value * 10000)
            if self._total_trade_value > 0 else 0,
            "config": self._config,
        }
