"""Execution Simulator — Simulated market environment for algorithm testing.

Provides a simulated market environment for testing execution algorithms
without connecting to live markets. Simulates fills, market impact,
and volume profiles.

Features:
    - Configurable market conditions (volatility, spread, volume)
    - Realistic fill simulation with market impact
    - Volume profile generation
    - Latency simulation

Usage::

    simulator = ExecutionSimulator()
    fill = await simulator.simulate_fill(
        child_order=child,
        market_price=150.0,
        volatility=0.20,
    )
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.child_order import ChildOrder

logger = logging.getLogger(__name__)


@dataclass
class SimulatedFill:
    """A simulated fill event."""

    child_order_id: str
    fill_quantity: float
    fill_price: float
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_order_id": self.child_order_id,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
            "is_complete": self.is_complete,
        }


@dataclass
class MarketState:
    """Simulated market state."""

    price: float = 150.0
    volatility: float = 0.20  # Annualized
    spread_bps: float = 2.0
    volume_per_minute: float = 10000.0
    bid: float = 0.0
    ask: float = 0.0

    def __post_init__(self) -> None:
        spread = self.price * self.spread_bps / 10000
        self.bid = self.price - spread / 2
        self.ask = self.price + spread / 2


class ExecutionSimulator:
    """Simulated market environment for algorithm testing.

    Simulates realistic fills with market impact, random noise,
    and configurable market conditions. Used for backtesting
    and strategy validation.

    Attributes:
        market: Current simulated market state
        _seed: Random seed for reproducibility
        _rng: Random number generator
    """

    def __init__(self, seed: int = 42) -> None:
        self.market = MarketState()
        self._seed = seed
        self._rng = random.Random(seed)
        self._fill_count: int = 0

    # ── Configuration ──────────────────────────────────────────────

    def set_market(
        self,
        price: float = 150.0,
        volatility: float = 0.20,
        spread_bps: float = 2.0,
        volume_per_minute: float = 10000.0,
    ) -> None:
        """Configure simulated market conditions.

        Args:
            price: Current market price
            volatility: Annualized volatility
            spread_bps: Bid-ask spread in basis points
            volume_per_minute: Trading volume per minute
        """
        self.market = MarketState(
            price=price,
            volatility=volatility,
            spread_bps=spread_bps,
            volume_per_minute=volume_per_minute,
        )

    def update_market(self, dt_seconds: float = 1.0) -> MarketState:
        """Evolve market state forward in time.

        Simulates price movement using geometric Brownian motion.

        Args:
            dt_seconds: Time step in seconds

        Returns:
            Updated MarketState
        """
        # Annualized to per-second volatility
        seconds_per_year = 252 * 6.5 * 3600
        vol_per_step = self.market.volatility * math.sqrt(dt_seconds / seconds_per_year)

        # Random price movement
        drift = 0.0  # Assume zero drift
        shock = self._rng.gauss(0, 1)
        return_pct = drift * dt_seconds / seconds_per_year + vol_per_step * shock

        self.market.price *= (1 + return_pct)

        # Update bid/ask
        spread = self.market.price * self.market.spread_bps / 10000
        self.market.bid = self.market.price - spread / 2
        self.market.ask = self.market.price + spread / 2

        return self.market

    # ── Fill Simulation ────────────────────────────────────────────

    async def simulate_fill(
        self,
        child: ChildOrder,
        market_price: Optional[float] = None,
        volatility: Optional[float] = None,
        fill_probability: float = 0.90,
    ) -> Optional[SimulatedFill]:
        """Simulate a fill for a child order.

        Models realistic fills with:
        - Market impact proportional to order size
        - Random price noise based on volatility
        - Commission estimation

        Args:
            child: Child order to simulate fill for
            market_price: Override market price
            volatility: Override volatility
            fill_probability: Probability of getting a fill (0-1)

        Returns:
            SimulatedFill or None if no fill
        """
        self._fill_count += 1

        price = market_price or self.market.price
        vol = volatility or self.market.volatility

        # Check if fill occurs
        if self._rng.random() > fill_probability:
            return None

        # Market impact: larger orders move price more
        participation = child.quantity / max(self.market.volume_per_minute, 1)
        impact_bps = 2.0 * math.sqrt(participation * 100)  # ~2 bps at 1% participation

        # Random noise from volatility
        noise_bps = vol * self._rng.gauss(0, 1) * 100

        # Total price adjustment
        total_bps = impact_bps + noise_bps

        # Adjust for side
        if str(child.side).upper() == "BUY":
            fill_price = price * (1 + total_bps / 10000)  # Buy = worse price
        else:
            fill_price = price * (1 - total_bps / 10000)  # Sell = worse price

        # Simulate partial fill based on market volume
        max_fill_pct = min(1.0, self.market.volume_per_minute / max(child.quantity, 1) * 0.1)
        fill_pct = self._rng.uniform(0.3, max_fill_pct)

        fill_qty = child.quantity * fill_pct
        fill_qty = min(fill_qty, child.remaining_quantity)
        fill_qty = math.floor(fill_qty * 100) / 100

        if fill_qty <= 0:
            return None

        # Commission: 1 bps of notional
        commission = fill_qty * fill_price * 0.0001

        is_complete = (child.filled_quantity + fill_qty) >= child.quantity * 0.999

        logger.debug(
            "Simulated fill: child=%s qty=%.0f price=%.4f impact=%.1fbps complete=%s",
            child.order_id,
            fill_qty,
            fill_price,
            impact_bps,
            is_complete,
        )

        return SimulatedFill(
            child_order_id=child.order_id,
            fill_quantity=fill_qty,
            fill_price=fill_price,
            commission=commission,
            is_complete=is_complete,
        )

    # ── Volume Profile ─────────────────────────────────────────────

    def generate_volume_profile(self, slices: int) -> list[float]:
        """Generate a simulated volume profile.

        Produces a realistic U-shaped intraday volume distribution.

        Args:
            slices: Number of time slices

        Returns:
            List of volume proportions (sums to 1.0)
        """
        profile = []
        for i in range(slices):
            t = i / max(slices - 1, 1)
            # U-shape: high at open and close, low at midday
            u_shape = 0.5 + 2.0 * (t - 0.5) ** 2
            noise = self._rng.uniform(0.9, 1.1)
            profile.append(u_shape * noise)

        total = sum(profile)
        return [p / total for p in profile]

    # ── Run Simulation ─────────────────────────────────────────────

    async def run_simulation(
        self,
        child_orders: list[ChildOrder],
        duration_seconds: float = 3600.0,
        dt_seconds: float = 60.0,
    ) -> list[SimulatedFill]:
        """Run a full simulation over multiple child orders.

        Simulates market evolution and fills over a time period.

        Args:
            child_orders: Child orders to simulate
            duration_seconds: Simulation duration
            dt_seconds: Time step size

        Returns:
            List of simulated fills
        """
        fills: list[SimulatedFill] = []
        remaining = list(child_orders)
        elapsed = 0.0

        while elapsed < duration_seconds and remaining:
            self.update_market(dt_seconds)

            for child in list(remaining):
                fill = await self.simulate_fill(child)
                if fill:
                    fills.append(fill)
                    if fill.is_complete:
                        remaining.remove(child)

            elapsed += dt_seconds

        logger.info(
            "Simulation complete: fills=%d remaining=%d duration=%.0fs",
            len(fills),
            len(remaining),
            elapsed,
        )
        return fills

    # ── Statistics ─────────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """Get simulation statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "fill_count": self._fill_count,
            "market_price": self.market.price,
            "market_bid": self.market.bid,
            "market_ask": self.market.ask,
            "spread_bps": self.market.spread_bps,
            "volatility": self.market.volatility,
            "volume_per_minute": self.market.volume_per_minute,
        }

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the simulator state.

        Args:
            seed: New random seed (keeps current if None)
        """
        if seed is not None:
            self._seed = seed
        self._rng = random.Random(self._seed)
        self._fill_count = 0
        self.market = MarketState()
