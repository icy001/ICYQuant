"""Adaptive Strategy — Market-adaptive execution.

Dynamically adjusts execution parameters based on real-time market
conditions including volatility, spread, and liquidity signals.

Adapts to:
    - Volatility: Slower when volatile, faster when stable
    - Spread: More passive when spread is wide
    - Liquidity: More aggressive when liquidity is high
    - Momentum: Adjusts direction based on short-term momentum

Algorithm::

    Market Data → Signal Analysis → Parameter Adjustment → Child Orders

Usage::

    strategy = AdaptiveStrategy()
    await strategy.initialize(context)
    child = await strategy.next_child_order(metadata)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata

logger = logging.getLogger(__name__)


class AdaptiveStrategy(ExecutionStrategy):
    """Market-adaptive execution strategy.

    Dynamically adjusts execution parameters based on real-time
    market conditions. Combines elements of TWAP, VWAP, and POV
    with market-aware parameter optimization.

    Signal inputs (via strategy_params):
        - volatility: Current volatility (annualized)
        - spread_bps: Current bid-ask spread in bps
        - volume_ratio: Current volume vs historical average
        - momentum: Short-term price momentum (-1 to 1)
        - imbalance: Order book imbalance (-1 to 1)

    Decision outputs:
        - Participation rate adjustment
        - Slice size adjustment
        - Limit price aggressiveness
    """

    def __init__(self) -> None:
        super().__init__()
        self._total_qty: float = 0.0
        self._remaining_qty: float = 0.0
        self._current_slice: int = 0
        self._max_slices: int = 0

        # Adaptive parameters
        self._base_participation: float = 0.05
        self._current_participation: float = 0.05
        self._volatility: float = 0.0
        self._spread_bps: float = 0.0
        self._volume_ratio: float = 1.0
        self._momentum: float = 0.0
        self._imbalance: float = 0.0

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize Adaptive strategy.

        Sets base parameters and computes max slices.

        Args:
            context: Execution context
        """
        self.context = context
        self._total_qty = context.total_quantity
        self._remaining_qty = self._total_qty
        self._base_participation = context.participation_rate
        self._current_participation = self._base_participation
        self._current_slice = 0

        interval = context.slice_interval_seconds
        if interval <= 0:
            interval = 30.0
        self._max_slices = max(1, int(context.effective_duration / interval))

        # Initial market signals
        self._volatility = context.strategy_params.get("volatility", 0.20)
        self._spread_bps = context.strategy_params.get("spread_bps", 2.0)
        self._volume_ratio = context.strategy_params.get("volume_ratio", 1.0)
        self._momentum = context.strategy_params.get("momentum", 0.0)
        self._imbalance = context.strategy_params.get("imbalance", 0.0)

        logger.info(
            "Adaptive strategy initialized: base_participation=%.1f%% max_slices=%d qty=%.0f",
            self._base_participation * 100,
            self._max_slices,
            self._total_qty,
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next adaptive child order.

        Adjusts participation rate based on market signals before
        computing slice size.

        Args:
            metadata: Current execution metadata

        Returns:
            ChildOrder or None
        """
        if self._is_paused or self._is_complete:
            return None

        if self._remaining_qty <= 0:
            self._is_complete = True
            return None

        if self._current_slice >= self._max_slices:
            # Last chance: dump remaining
            if self._remaining_qty > 0:
                pass
            else:
                self._is_complete = True
                return None

        # ── Adaptive Signal Processing ─────────────────────────────

        # 1. Volatility adjustment: reduce participation in high vol
        vol_factor = self._compute_volatility_factor()

        # 2. Spread adjustment: reduce participation in wide spreads
        spread_factor = self._compute_spread_factor()

        # 3. Volume adjustment: increase participation in high volume
        volume_factor = self._compute_volume_factor()

        # 4. Momentum adjustment: trade with momentum
        momentum_factor = self._compute_momentum_factor()

        # 5. Imbalance adjustment: avoid trading against imbalance
        imbalance_factor = self._compute_imbalance_factor()

        # 6. Urgency adjustment: increase participation as deadline approaches
        urgency_factor = self._compute_urgency_factor()

        # Composite participation rate
        self._current_participation = (
            self._base_participation
            * vol_factor
            * spread_factor
            * volume_factor
            * momentum_factor
            * imbalance_factor
            * urgency_factor
        )

        # Clamp participation
        self._current_participation = max(0.01, min(0.50, self._current_participation))

        # Calculate slice quantity
        estimated_volume = self._total_qty * 10  # Simple estimate
        slice_qty = estimated_volume * self._current_participation

        # Apply constraints
        slice_qty = min(slice_qty, self._remaining_qty)
        slice_qty = max(slice_qty, self.context.min_slice_quantity)

        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)

        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            self._current_slice += 1
            return None

        # Determine price aggressiveness
        price = 0.0
        if self._spread_bps > 0:
            # More aggressive pricing when spread is tight
            price_aggressiveness = max(0.0, 1.0 - self._spread_bps / 20.0)
            if self._imbalance < 0:  # Favorable imbalance
                price_aggressiveness *= 1.5
            # For now, use market orders
            pass

        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=price,
            slice_index=self._current_slice,
        )

        self._remaining_qty -= slice_qty
        self._current_slice += 1

        logger.debug(
            "Adaptive slice %d: qty=%.2f part=%.2f%% vol=%.1f%% spread=%.1fbps mom=%.2f imb=%.2f",
            self._current_slice,
            slice_qty,
            self._current_participation * 100,
            self._volatility * 100,
            self._spread_bps,
            self._momentum,
            self._imbalance,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update adaptive parameters from latest market data.

        Reads updated market signals from strategy_params.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

        # Update market signals from context params (would be fed by market data feed)
        if self.context:
            self._volatility = self.context.strategy_params.get("volatility", self._volatility)
            self._spread_bps = self.context.strategy_params.get("spread_bps", self._spread_bps)
            self._volume_ratio = self.context.strategy_params.get("volume_ratio", self._volume_ratio)
            self._momentum = self.context.strategy_params.get("momentum", self._momentum)
            self._imbalance = self.context.strategy_params.get("imbalance", self._imbalance)

    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity
        if self._remaining_qty <= 0:
            self._is_complete = True

    async def complete(self) -> None:
        """Complete the Adaptive strategy."""
        self._is_complete = True
        logger.info("Adaptive strategy completed: slices=%d", self._current_slice)

    # ── Signal Processing ──────────────────────────────────────────

    def _compute_volatility_factor(self) -> float:
        """Volatility: reduce participation when volatile."""
        # Normalize: 20% vol = neutral (factor=1.0)
        neutral_vol = 0.20
        if self._volatility <= 0:
            return 1.0
        # Higher vol → lower factor (min 0.2)
        return max(0.2, neutral_vol / max(self._volatility, 0.01))

    def _compute_spread_factor(self) -> float:
        """Spread: reduce participation when spread is wide."""
        # 2 bps spread = neutral
        neutral_spread = 2.0
        if self._spread_bps <= 0:
            return 1.0
        return max(0.3, neutral_spread / max(self._spread_bps, 0.1))

    def _compute_volume_factor(self) -> float:
        """Volume: increase participation when volume is high."""
        # volume_ratio > 1 = higher than normal volume
        return max(0.5, min(2.0, self._volume_ratio))

    def _compute_momentum_factor(self) -> float:
        """Momentum: trade with momentum."""
        # Positive momentum = buying pressure
        side = str(getattr(self.context.parent_order, "side", "")).upper() if self.context else ""
        if side == "BUY":
            # Buying into positive momentum is favorable
            return 1.0 + self._momentum * 0.5
        else:
            # Selling into negative momentum is favorable
            return 1.0 - self._momentum * 0.5

    def _compute_imbalance_factor(self) -> float:
        """Imbalance: avoid trading against order book imbalance."""
        side = str(getattr(self.context.parent_order, "side", "")).upper() if self.context else ""
        if side == "BUY":
            # Positive imbalance = more bids = favorable for buy
            return 1.0 + self._imbalance * 0.5
        else:
            # Negative imbalance = more asks = favorable for sell
            return 1.0 - self._imbalance * 0.5

    def _compute_urgency_factor(self) -> float:
        """Urgency: increase participation as deadline approaches."""
        if self._max_slices <= 0:
            return 1.0

        progress = self._current_slice / self._max_slices

        # Exponential increase: 1.0 → 3.0 as progress → 1.0
        return 1.0 + progress * progress * 2.0
