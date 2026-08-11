"""
Risk Parity Position Sizing
============================
Implements risk parity position sizing.

Formula:
    Weight_i = (1 / sigma_i) / sum(1 / sigma_j for j in portfolio)

Where sigma_i is the volatility (risk) of instrument i.

In risk parity, each position contributes equally to portfolio risk,
rather than equally to portfolio capital (as in equal weight).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.strategy.portfolio.sizing_models import BaseSizingModel

logger = logging.getLogger(__name__)


@dataclass
class RiskParityParams:
    """Parameters for risk parity sizing."""

    target_volatility: float = 0.12  # Portfolio target vol
    max_position_pct: float = 0.30
    min_position_pct: float = 0.001
    min_volatility: float = 0.01


class RiskParitySizingModel(BaseSizingModel):
    """
    Risk Parity position sizing model.

    Allocates capital such that each position contributes equally
    to portfolio risk. Higher-volatility instruments get smaller
    positions, lower-volatility instruments get larger positions.

    Note: Full risk parity requires covariance matrix. This simplified
    version uses inverse-volatility weighting (naive risk parity).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._name = "RiskParitySizing"
        self._version = "1.0.0"

        self._target_vol = self._config.get("target_volatility", 0.12)
        self._max_position_pct = self._config.get("max_position_pct", 0.30)
        self._min_position_pct = self._config.get("min_position_pct", 0.001)
        self._min_vol = self._config.get("min_volatility", 0.01)

        # For batch risk parity, we need to track the portfolio context
        self._portfolio_vol_sum: float = 0.0
        self._num_positions: int = 0

    def _get_volatility(self, params: Dict[str, Any]) -> float:
        """Extract or estimate instrument volatility."""
        annual_vol = params.get("annualized_volatility", 0.0)
        if annual_vol > 0:
            return annual_vol

        atr = params.get("atr", 0.0)
        price = params.get("current_price", 0.0)
        if atr > 0 and price > 0:
            return (atr / price) * (252 ** 0.5)

        return 0.20  # Default

    def set_portfolio_context(self, instruments: List[Dict[str, Any]]) -> None:
        """
        Set portfolio context for batch risk parity computation.

        Args:
            instruments: List of dicts with volatility info for all positions.
        """
        total_inv_vol = 0.0
        for inst in instruments:
            vol = inst.get("annualized_volatility", 0.0)
            if vol <= 0:
                atr = inst.get("atr", 0.0)
                price = inst.get("current_price", 0.0)
                if atr > 0 and price > 0:
                    vol = (atr / price) * (252 ** 0.5)
                else:
                    vol = 0.20
            total_inv_vol += 1.0 / max(vol, self._min_vol)

        self._portfolio_vol_sum = total_inv_vol
        self._num_positions = len(instruments)
        logger.debug(
            "Risk parity context: %d instruments, inv_vol_sum=%.4f",
            self._num_positions,
            self._portfolio_vol_sum,
        )

    async def compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute risk parity position size.

        Required params:
            account_equity, current_price
        Optional:
            annualized_volatility, atr, max_position_pct,
            portfolio_vol_sum (for batch), confidence
        """
        errors = self.validate_params(params)
        if errors:
            logger.warning("Risk parity validation errors: %s", errors)
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": f"Validation failed: {'; '.join(errors)}",
            }

        equity = params["account_equity"]
        price = params["current_price"]
        max_position_pct = params.get("max_position_pct", self._max_position_pct)
        confidence = params.get("confidence", 1.0)

        instrument_vol = self._get_volatility(params)
        instrument_vol = max(instrument_vol, self._min_vol)

        # Inverse volatility weight
        inv_vol = 1.0 / instrument_vol

        # If we have portfolio context, compute weight relative to portfolio
        portfolio_sum = params.get("portfolio_vol_sum", self._portfolio_vol_sum)
        if portfolio_sum > 0:
            position_weight = inv_vol / portfolio_sum
        else:
            # Standalone: assume this is the only position
            position_weight = 1.0

        # Adjust by confidence
        position_weight *= confidence

        # Scale by target volatility
        position_weight *= (self._target_vol / instrument_vol)

        # Apply caps
        position_weight = min(position_weight, max_position_pct)
        position_weight = max(position_weight, 0.0)

        # Calculate position
        position_value = equity * position_weight
        position_size = position_value / price if price > 0 else 0.0
        risk_exposure = position_value * instrument_vol

        reason = (
            f"RiskParity: inv_vol={inv_vol:.4f}, "
            f"weight={position_weight:.2%}, vol={instrument_vol:.1%}"
        )

        logger.debug("Risk parity sizing: %s", reason)

        return {
            "position_size": round(position_size, 6),
            "position_value": round(position_value, 2),
            "position_weight": round(position_weight, 6),
            "risk_exposure": round(risk_exposure, 2),
            "reason": reason,
            "metadata": {
                "instrument_volatility": instrument_vol,
                "inverse_volatility": inv_vol,
                "target_volatility": self._target_vol,
                "confidence": confidence,
            },
        }
