"""
Slippage Simulator
==================
Simulates execution slippage using configurable models.

Models:
    Fixed       — Fixed BPS per trade
    Volume      — Slippage based on trade volume relative to market
    ATR         — Slippage proportional to Average True Range
    Order Book  — Slippage from order book depth
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SlippageModel(str, Enum):
    FIXED = "fixed"
    VOLUME = "volume"
    ATR = "atr"
    ORDERBOOK = "orderbook"


@dataclass
class SlippageResult:
    """Slippage simulation result."""
    model: SlippageModel = SlippageModel.FIXED
    base_price: float = 0.0
    slippage_bps: float = 0.0
    slippage_amount: float = 0.0
    effective_price: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SlippageSimulator:
    """Simulates execution slippage for paper trading.

    Supports Fixed, Volume-based, ATR-based, and Order Book-based models.
    """

    def __init__(self, model: SlippageModel = SlippageModel.FIXED):
        self._model = model
        self._fixed_bps: float = 5.0
        self._atr_values: Dict[str, float] = {}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("SlippageSimulator initialized (model=%s)", self._model.value)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_model(self, model: SlippageModel) -> None:
        self._model = model

    def set_fixed_bps(self, bps: float) -> None:
        self._fixed_bps = bps

    def set_atr(self, instrument: str, atr: float) -> None:
        self._atr_values[instrument] = atr

    # ------------------------------------------------------------------
    # Simulate
    # ------------------------------------------------------------------

    async def simulate(self, instrument: str, price: float,
                       quantity: float, side: str = "BUY") -> SlippageResult:
        """Simulate slippage for a trade."""
        if self._model == SlippageModel.FIXED:
            bps = self._fixed_bps
        elif self._model == SlippageModel.VOLUME:
            bps = self._volume_based_slippage(quantity)
        elif self._model == SlippageModel.ATR:
            bps = self._atr_based_slippage(instrument, price)
        elif self._model == SlippageModel.ORDERBOOK:
            bps = self._orderbook_based_slippage(price, quantity)
        else:
            bps = 0.0

        # Slippage direction: BUY = adverse (higher price), SELL = adverse (lower)
        direction = 1 if side == "BUY" else -1
        slippage_amount = direction * (price * bps / 10000.0)

        # Add small random noise (±20% of base slippage)
        noise = random.uniform(-0.2, 0.2) * slippage_amount
        slippage_amount += noise

        result = SlippageResult(
            model=self._model,
            base_price=price,
            slippage_bps=bps,
            slippage_amount=slippage_amount,
            effective_price=price + slippage_amount,
        )
        return result

    # ------------------------------------------------------------------
    # Model Internals
    # ------------------------------------------------------------------

    def _volume_based_slippage(self, quantity: float) -> float:
        """Volume-based slippage: larger orders = more slippage."""
        # Logarithmic relationship: log10(quantity) * base_bps
        if quantity <= 0:
            return 0.0
        return min(self._fixed_bps * math.log10(max(quantity, 10)), 50.0)

    def _atr_based_slippage(self, instrument: str, price: float) -> float:
        """ATR-based slippage: slippage proportional to ATR/Price."""
        atr = self._atr_values.get(instrument, price * 0.01)
        if price <= 0:
            return 0.0
        return (atr / price) * 10000 * 0.5  # Half ATR as slippage in bps

    def _orderbook_based_slippage(self, price: float, quantity: float) -> float:
        """Order book depth slippage estimate."""
        if quantity <= 0:
            return 0.0
        return min(self._fixed_bps * (1 + math.log(quantity / 100)), 100.0)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "model": self._model.value,
            "fixed_bps": self._fixed_bps,
            "atr_instruments": len(self._atr_values),
        }
