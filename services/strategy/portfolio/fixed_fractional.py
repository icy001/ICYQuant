"""
Fixed Fractional Position Sizing
================================
Implements fixed fractional position sizing model.

Formula:
    Position = (Account Equity * Risk Fraction) / Trade Risk

Where Trade Risk = |Entry - Stop Loss| (or ATR-based estimate)

Supports:
- Risk per trade as % of equity
- ATR-based stop distance
- Configurable risk fraction
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.strategy.portfolio.sizing_models import BaseSizingModel

logger = logging.getLogger(__name__)


@dataclass
class FixedFractionalParams:
    """Parameters for fixed fractional sizing."""

    risk_per_trade_pct: float = 0.02  # 2% risk per trade
    atr_multiplier: float = 2.0  # Stop distance = ATR * multiplier
    max_position_pct: float = 0.20  # Cap on position weight


class FixedFractionalModel(BaseSizingModel):
    """
    Fixed Fractional position sizing model.

    The simplest and most widely used institutional sizing model.
    Risks a fixed percentage of equity per trade, with stop-loss
    distance determining position size.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._name = "FixedFractional"
        self._version = "1.0.0"

        self._default_risk_pct = self._config.get("risk_per_trade_pct", 0.02)
        self._default_atr_mult = self._config.get("atr_multiplier", 2.0)
        self._default_max_position_pct = self._config.get("max_position_pct", 0.20)
        self._default_min_stop_pct = self._config.get("min_stop_pct", 0.005)  # 0.5% minimum stop

    def _estimate_stop_distance(self, params: Dict[str, Any]) -> float:
        """
        Estimate stop-loss distance.

        Uses ATR if available, otherwise defaults to a percentage of price.
        """
        price = params.get("current_price", 0.0)
        atr = params.get("atr", 0.0)
        atr_multiplier = params.get("atr_multiplier", self._default_atr_mult)

        if atr > 0:
            return atr * atr_multiplier

        # Fallback: use annualized volatility to estimate daily range
        annual_vol = params.get("annualized_volatility", 0.0)
        if annual_vol > 0:
            # Approximate daily volatility
            daily_vol = annual_vol / (252 ** 0.5)
            return price * daily_vol * atr_multiplier

        # Absolute fallback: 1% of price
        return max(price * 0.01, price * self._default_min_stop_pct)

    async def compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute fixed fractional position size.

        Required params:
            account_equity, current_price
        Optional:
            risk_per_trade_pct, atr, annualized_volatility,
            max_position_pct, risk_budget, confidence
        """
        errors = self.validate_params(params)
        if errors:
            logger.warning("Fixed fractional validation errors: %s", errors)
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": f"Validation failed: {'; '.join(errors)}",
            }

        equity = params["account_equity"]
        price = params["current_price"]
        risk_pct = params.get("risk_per_trade_pct", params.get("max_risk_per_trade_pct", self._default_risk_pct))
        max_position_pct = params.get("max_position_pct", self._default_max_position_pct)
        confidence = params.get("confidence", 1.0)
        signal_strength = params.get("signal_strength", 1.0)

        # Risk amount in currency
        risk_amount = equity * risk_pct * confidence * abs(signal_strength)

        # Estimate stop distance
        stop_distance = self._estimate_stop_distance(params)

        if stop_distance <= 0 or price <= 0:
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": f"Invalid stop distance ({stop_distance}) or price ({price})",
            }

        # Position size = risk_amount / stop_distance
        position_size = risk_amount / stop_distance
        position_value = position_size * price
        position_weight = position_value / equity if equity > 0 else 0.0

        # Cap at max position percentage
        if position_weight > max_position_pct:
            position_value = equity * max_position_pct
            position_size = position_value / price
            position_weight = max_position_pct

        risk_exposure = position_size * stop_distance

        reason = (
            f"FixedFrac {risk_pct:.2%}: risk={risk_amount:.2f}, "
            f"stop_dist={stop_distance:.2f}, size={position_size:.2f}"
        )

        logger.debug("Fixed fractional sizing: %s", reason)

        return {
            "position_size": round(position_size, 6),
            "position_value": round(position_value, 2),
            "position_weight": round(position_weight, 6),
            "risk_exposure": round(risk_exposure, 2),
            "reason": reason,
            "metadata": {
                "risk_per_trade_pct": risk_pct,
                "risk_amount": risk_amount,
                "stop_distance": stop_distance,
                "confidence": confidence,
                "signal_strength": signal_strength,
            },
        }
