"""Slippage Model — realistic trade execution slippage simulation.

Models the difference between expected and actual execution price,
supporting multiple slippage estimation methods.

Methods::

    Fixed → Percentage → Volatility Based → Liquidity Based → Market Impact
"""

from __future__ import annotations

import logging
import math
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SlippageMethod(str, Enum):
    """Slippage estimation methods."""

    FIXED = "fixed"
    PERCENTAGE = "percentage"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    MARKET_IMPACT = "market_impact"


class SlippageModel:
    """Multi-method slippage estimation for trade execution.

    Supports five estimation methods from simple fixed to
    sophisticated market impact models.

    Usage::

        model = SlippageModel(method=SlippageMethod.MARKET_IMPACT, base_bps=5.0)
        slippage = model.compute(symbol="000001.SZ", quantity=10000,
                                 market_price=50.0, market_data=bar)
    """

    def __init__(
        self,
        method: SlippageMethod = SlippageMethod.PERCENTAGE,
        base_bps: float = 5.0,
        fixed_cost: float = 0.01,
        volatility_scalar: float = 1.0,
        impact_exponent: float = 0.5,
    ) -> None:
        self._method = method
        self._base_bps = base_bps
        self._fixed_cost = fixed_cost
        self._volatility_scalar = volatility_scalar
        self._impact_exponent = impact_exponent

    def get_method(self) -> SlippageMethod:
        return self._method

    def compute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Compute the slippage in price units.

        Args:
            symbol: Ticker symbol.
            side: buy or sell.
            quantity: Order quantity.
            market_price: Current market price.
            market_data: Optional OHLCV data with volume, volatility, etc.

        Returns:
            Slippage in price units (positive = adverse for buyer).
        """
        if market_price <= 0:
            return 0.0

        if self._method == SlippageMethod.FIXED:
            return self._fixed_slippage(quantity)

        elif self._method == SlippageMethod.PERCENTAGE:
            return self._percentage_slippage(market_price)

        elif self._method == SlippageMethod.VOLATILITY:
            return self._volatility_slippage(market_price, market_data)

        elif self._method == SlippageMethod.LIQUIDITY:
            return self._liquidity_slippage(market_price, quantity, market_data)

        elif self._method == SlippageMethod.MARKET_IMPACT:
            return self._market_impact_slippage(market_price, quantity, market_data)

        return 0.0

    def compute_bps(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Compute slippage in basis points (1 bp = 0.01%)."""
        slippage = self.compute(symbol, side, quantity, market_price, market_data)
        if market_price <= 0:
            return 0.0
        return (slippage / market_price) * 10000

    # ── calculation methods ────────────────────────────────────────────────

    def _fixed_slippage(self, quantity: float) -> float:
        """Fixed cost per unit."""
        return self._fixed_cost

    def _percentage_slippage(self, market_price: float) -> float:
        """Percentage-based slippage."""
        return market_price * (self._base_bps / 10000)

    def _volatility_slippage(
        self,
        market_price: float,
        market_data: Optional[Dict[str, Any]],
    ) -> float:
        """Volatility-based slippage model.

        Higher volatility → higher slippage.
        """
        volatility = 0.01  # default 1% daily vol
        if market_data:
            # Estimate from high-low range or explicit volatility
            high = market_data.get("high", market_price)
            low = market_data.get("low", market_price)
            close = market_data.get("close", market_price)
            if high > 0 and low > 0 and close > 0:
                # Parkinson volatility estimator (simplified)
                volatility = (high - low) / close

        return market_price * volatility * (self._base_bps / 10000) * self._volatility_scalar

    def _liquidity_slippage(
        self,
        market_price: float,
        quantity: float,
        market_data: Optional[Dict[str, Any]],
    ) -> float:
        """Liquidity-based slippage.

        Larger orders relative to volume → higher slippage.
        """
        volume = 1_000_000  # default
        if market_data:
            volume = market_data.get("volume", volume)

        # Order size relative to volume
        participation = quantity / max(volume, 1)
        # Logarithmic impact model
        impact = math.log1p(participation * 100) * (self._base_bps / 10000)

        return market_price * impact

    def _market_impact_slippage(
        self,
        market_price: float,
        quantity: float,
        market_data: Optional[Dict[str, Any]],
    ) -> float:
        """Square-root market impact model (Almgren-Chriss style).

        Impact ∝ sqrt(order_size / volume) * volatility
        """
        volume = 1_000_000
        volatility = 0.01

        if market_data:
            volume = market_data.get("volume", volume)
            high = market_data.get("high", market_price)
            low = market_data.get("low", market_price)
            close = market_data.get("close", market_price)
            if high > 0 and close > 0:
                volatility = max((high - low) / close, 0.001)

        participation = quantity / max(volume, 1)
        # Square-root impact function
        impact = math.sqrt(participation) * volatility * self._base_bps / 10000

        return market_price * impact * self._impact_exponent

    # ── configuration ──────────────────────────────────────────────────────

    def set_method(self, method: SlippageMethod) -> None:
        """Change the slippage estimation method."""
        self._method = method
        logger.info("Slippage method changed to: %s", method.value)

    def set_params(
        self,
        base_bps: Optional[float] = None,
        fixed_cost: Optional[float] = None,
        volatility_scalar: Optional[float] = None,
        impact_exponent: Optional[float] = None,
    ) -> None:
        """Update model parameters."""
        if base_bps is not None:
            self._base_bps = base_bps
        if fixed_cost is not None:
            self._fixed_cost = fixed_cost
        if volatility_scalar is not None:
            self._volatility_scalar = volatility_scalar
        if impact_exponent is not None:
            self._impact_exponent = impact_exponent

    def get_params(self) -> Dict[str, Any]:
        """Return current model parameters."""
        return {
            "method": self._method.value,
            "base_bps": self._base_bps,
            "fixed_cost": self._fixed_cost,
            "volatility_scalar": self._volatility_scalar,
            "impact_exponent": self._impact_exponent,
        }
