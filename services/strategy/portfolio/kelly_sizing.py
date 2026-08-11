"""
Kelly Position Sizing
=====================
Implements the Kelly Criterion for optimal position sizing.

Formula:
    f* = (p * b - q) / b
    where:
        p = win probability (win_rate)
        q = loss probability (1 - win_rate)
        b = payoff ratio (avg_win / avg_loss)

Position = f* * account_equity / price

Supports:
- Full Kelly
- Half Kelly (conservative)
- Quarter Kelly (very conservative)
- Custom fraction
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.strategy.portfolio.sizing_models import BaseSizingModel

logger = logging.getLogger(__name__)


@dataclass
class KellyParams:
    """Parameters for Kelly Criterion calculation."""

    win_rate: float = 0.5
    payoff_ratio: float = 2.0
    fraction: float = 0.5  # Full=1.0, Half=0.5, Quarter=0.25
    max_kelly_pct: float = 0.25  # Cap on kelly fraction


class KellySizingModel(BaseSizingModel):
    """
    Kelly Criterion position sizing model.

    Computes optimal position size based on win rate and payoff ratio.
    Uses Half Kelly by default for conservative sizing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._name = "KellySizing"
        self._version = "1.0.0"

        # Configurable defaults
        self._default_fraction = self._config.get("fraction", 0.5)  # Half Kelly
        self._max_kelly_pct = self._config.get("max_kelly_pct", 0.25)
        self._min_win_rate = self._config.get("min_win_rate", 0.01)
        self._min_payoff = self._config.get("min_payoff", 1.01)

    def _compute_kelly_fraction(
        self,
        win_rate: float,
        payoff_ratio: float,
        fraction: float,
    ) -> float:
        """
        Compute the Kelly fraction.

        f* = (p * b - (1-p)) / b
        """
        p = max(win_rate, self._min_win_rate)
        q = 1.0 - p
        b = max(payoff_ratio, self._min_payoff)

        # Kelly formula
        kelly = (p * b - q) / b

        # Kelly must be positive to take position
        if kelly <= 0:
            return 0.0

        # Apply conservative fraction (Half Kelly etc.)
        kelly *= fraction

        # Cap at maximum
        kelly = min(kelly, self._max_kelly_pct)

        return max(kelly, 0.0)

    async def compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute Kelly position size.

        Required params:
            account_equity, current_price, win_rate, payoff_ratio
        Optional:
            fraction (override default), max_position_pct, risk_budget
        """
        errors = self.validate_params(params)
        if errors:
            logger.warning("Kelly sizing validation errors: %s", errors)
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": f"Validation failed: {'; '.join(errors)}",
            }

        equity = params["account_equity"]
        price = params["current_price"]
        win_rate = params.get("win_rate", 0.5)
        payoff_ratio = params.get("payoff_ratio", 2.0)
        fraction = params.get("fraction", self._default_fraction)
        max_position_pct = params.get("max_position_pct", 1.0)
        confidence = params.get("confidence", 1.0)

        # Compute Kelly fraction
        kelly_pct = self._compute_kelly_fraction(win_rate, payoff_ratio, fraction)

        if kelly_pct <= 0:
            return {
                "position_size": 0.0,
                "position_value": 0.0,
                "position_weight": 0.0,
                "risk_exposure": 0.0,
                "reason": (
                    f"Kelly fraction <= 0 (win_rate={win_rate:.2%}, "
                    f"payoff={payoff_ratio:.2f}, fraction={fraction:.2f})"
                ),
            }

        # Adjust by confidence
        kelly_pct *= confidence

        # Apply max position cap
        kelly_pct = min(kelly_pct, max_position_pct)

        # Calculate position
        position_value = equity * kelly_pct
        position_size = position_value / price if price > 0 else 0.0
        risk_exposure = position_value * (1.0 / payoff_ratio) if payoff_ratio > 0 else position_value

        reason = (
            f"Kelly {fraction:.0%}: kelly={kelly_pct:.4%} "
            f"(wr={win_rate:.2%}, payoff={payoff_ratio:.2f}, "
            f"conf={confidence:.2f})"
        )

        logger.debug("Kelly sizing: %s", reason)

        return {
            "position_size": round(position_size, 6),
            "position_value": round(position_value, 2),
            "position_weight": round(kelly_pct, 6),
            "risk_exposure": round(risk_exposure, 2),
            "reason": reason,
            "metadata": {
                "kelly_fraction": kelly_pct,
                "raw_kelly": kelly_pct / fraction if fraction > 0 else 0,
                "win_rate": win_rate,
                "payoff_ratio": payoff_ratio,
                "confidence": confidence,
            },
        }
