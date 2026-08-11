"""
Volatility Position Sizing
===========================
Implements volatility-targeted position sizing.

Formula:
    Position = (Target Volatility * Account Equity) / (Instrument Volatility * Price)

This model adjusts position size inversely with volatility,
reducing exposure in high-volatility regimes and increasing
it in low-volatility regimes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.strategy.portfolio.sizing_models import BaseSizingModel

logger = logging.getLogger(__name__)


@dataclass
class VolatilitySizingParams:
    """Parameters for volatility-targeted sizing."""

    target_volatility: float = 0.15  # 15% annualized target vol
    max_position_pct: float = 0.25
    min_position_pct: float = 0.001
    vol_lookback: int = 20  # Days for volatility estimation


class VolatilitySizingModel(BaseSizingModel):
    """
    Volatility-targeted position sizing model.

    Adjusts position size to target a specific portfolio volatility
    contribution from each position. Ideal for risk-parity-style
    approaches and strategies sensitive to market volatility.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._name = "VolatilitySizing"
        self._version = "1.0.0"

        self._target_vol = self._config.get("target_volatility", 0.15)
        self._max_position_pct = self._config.get("max_position_pct", 0.25)
        self._min_position_pct = self._config.get("min_position_pct", 0.001)
        self._min_vol = self._config.get("min_volatility", 0.01)  # Floor for vol

    def _estimate_volatility(self, params: Dict[str, Any]) -> float:
        """Estimate instrument volatility."""
        annual_vol = params.get("annualized_volatility", 0.0)
        if annual_vol > 0:
            return annual_vol

        # Try to derive from ATR
        atr = params.get("atr", 0.0)
        price = params.get("current_price", 0.0)
        if atr > 0 and price > 0:
            daily_vol_pct = atr / price
            # Annualize (252 trading days)
            annual_vol = daily_vol_pct * (252 ** 0.5)
            return annual_vol

        # Default conservative estimate
        return 0.25  # 25% annual vol

    async def compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute volatility-targeted position size.

        Required params:
            account_equity, current_price
        Optional:
            annualized_volatility, atr, target_volatility,
            max_position_pct, confidence
        """
        errors = self.validate_params(params)
        if errors:
            logger.warning("Volatility sizing validation errors: %s", errors)
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": f"Validation failed: {'; '.join(errors)}",
            }

        equity = params["account_equity"]
        price = params["current_price"]
        target_vol = params.get("target_volatility", self._target_vol)
        max_position_pct = params.get("max_position_pct", self._max_position_pct)
        confidence = params.get("confidence", 1.0)

        # Estimate instrument volatility
        instrument_vol = self._estimate_volatility(params)
        instrument_vol = max(instrument_vol, self._min_vol)

        # Volatility scaling: position weight = target_vol / instrument_vol
        raw_weight = target_vol / instrument_vol

        # Adjust by confidence
        raw_weight *= confidence

        # Apply caps
        position_weight = min(raw_weight, max_position_pct)
        position_weight = max(position_weight, 0.0)

        # Calculate position
        position_value = equity * position_weight
        position_size = position_value / price if price > 0 else 0.0
        risk_exposure = position_value * instrument_vol

        reason = (
            f"VolTarget {target_vol:.1%}: instr_vol={instrument_vol:.1%}, "
            f"weight={position_weight:.2%} (raw={raw_weight:.2%})"
        )

        logger.debug("Volatility sizing: %s", reason)

        return {
            "position_size": round(position_size, 6),
            "position_value": round(position_value, 2),
            "position_weight": round(position_weight, 6),
            "risk_exposure": round(risk_exposure, 2),
            "reason": reason,
            "metadata": {
                "target_volatility": target_vol,
                "instrument_volatility": instrument_vol,
                "raw_weight": raw_weight,
                "confidence": confidence,
            },
        }
