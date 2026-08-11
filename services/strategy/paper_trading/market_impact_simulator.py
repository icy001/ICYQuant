"""
Market Impact Simulator
=======================
Estimates price impact of trades using industry-standard models.

Models:
    Linear   — Impact proportional to order size
    SQRT     — Square-root impact model (Almgren-Chriss style)
    Kissell  — Kissell-Glantz institutional impact model

Pipeline:
    Order Size → Impact Model → Price Change
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ImpactModel(str, Enum):
    LINEAR = "linear"
    SQRT = "sqrt"
    KISSELL = "kissell"


@dataclass
class ImpactResult:
    """Market impact simulation result."""
    model: ImpactModel = ImpactModel.LINEAR
    instrument: str = ""
    order_size: float = 0.0
    base_price: float = 0.0
    impact_bps: float = 0.0
    impact_amount: float = 0.0
    effective_price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MarketImpactSimulator:
    """Estimates market impact of trades.

    Supports Linear, SQRT, and Kissell-Glantz models.
    """

    def __init__(self, model: ImpactModel = ImpactModel.LINEAR):
        self._model = model
        self._adv_values: Dict[str, float] = {}       # Average Daily Volume by instrument
        self._volatility: Dict[str, float] = {}         # Annualized volatility by instrument
        self._impact_coefficient: float = 0.1           # Linear impact coefficient
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("MarketImpactSimulator initialized (model=%s)", self._model.value)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_model(self, model: ImpactModel) -> None:
        self._model = model

    def set_adv(self, instrument: str, adv: float) -> None:
        self._adv_values[instrument] = adv

    def set_volatility(self, instrument: str, vol: float) -> None:
        self._volatility[instrument] = vol

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    async def simulate(self, instrument: str, quantity: float,
                       price: float) -> ImpactResult:
        """Estimate market impact for a trade."""
        if price <= 0 or quantity <= 0:
            return ImpactResult(
                model=self._model,
                instrument=instrument,
                order_size=quantity,
                base_price=price,
            )

        if self._model == ImpactModel.LINEAR:
            impact_bps = self._linear_impact(quantity)
        elif self._model == ImpactModel.SQRT:
            impact_bps = self._sqrt_impact(instrument, quantity, price)
        elif self._model == ImpactModel.KISSELL:
            impact_bps = self._kissell_impact(instrument, quantity, price)
        else:
            impact_bps = 0.0

        impact_amount = price * impact_bps / 10000.0
        return ImpactResult(
            model=self._model,
            instrument=instrument,
            order_size=quantity,
            base_price=price,
            impact_bps=impact_bps,
            impact_amount=impact_amount,
            effective_price=price + impact_amount,
        )

    # ------------------------------------------------------------------
    # Model Internals
    # ------------------------------------------------------------------

    def _linear_impact(self, quantity: float) -> float:
        """Linear impact: proportional to order size."""
        return self._impact_coefficient * quantity

    def _sqrt_impact(self, instrument: str, quantity: float, price: float) -> float:
        """SQRT impact (Almgren-Chriss style).

        impact = sigma * sqrt(Q / ADV) * scaling_factor
        """
        adv = self._adv_values.get(instrument, quantity * 10)
        sigma = self._volatility.get(instrument, 0.20)  # Default 20% vol
        participation = quantity / adv if adv > 0 else 0

        # Standard sqrt impact formula
        impact_bps = sigma * math.sqrt(participation) * 10000 * 0.3
        return min(impact_bps, 500.0)  # Cap at 500 bps

    def _kissell_impact(self, instrument: str, quantity: float, price: float) -> float:
        """Kissell-Glantz institutional impact model.

        Incorporates volatility, ADV, and a stock-specific coefficient.
        """
        adv = self._adv_values.get(instrument, quantity * 10)
        sigma = self._volatility.get(instrument, 0.20)
        participation = quantity / adv if adv > 0 else 0

        # Kissell instantaneous impact
        impact_cost = 0.5 * sigma * (participation ** 0.5) * 10000
        return min(impact_cost, 300.0)  # Cap at 300 bps

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "model": self._model.value,
            "impact_coefficient": self._impact_coefficient,
            "adv_instruments": len(self._adv_values),
            "volatility_instruments": len(self._volatility),
        }
