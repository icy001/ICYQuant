"""Market Impact Model — Almgren-Chriss and square-root models.

Estimates the price impact of trading a given quantity:
- Temporary impact: transient cost from order flow imbalance
- Permanent impact: lasting price change from information content
"""

from __future__ import annotations

import math
from typing import Optional

from .models import ImpactEstimate, MarketState


class MarketImpactModel:
    """Estimates market impact of orders using industry-standard models.

    Based on Almgren-Chriss framework with square-root law:
    - Temporary impact ∝ σ · (Q / (V · T))^β
    - Permanent impact ∝ σ · (Q / V)^γ

    Where:
    - σ = volatility
    - Q = order quantity
    - V = daily volume
    - T = time fraction
    - β, γ = model exponents
    """

    def __init__(
        self,
        temporary_impact_factor: float = 0.15,
        permanent_impact_factor: float = 0.10,
        beta: float = 0.6,
        gamma: float = 0.5,
    ):
        """Initialize the impact model.

        Args:
            temporary_impact_factor: Scale factor for temporary impact.
            permanent_impact_factor: Scale factor for permanent impact.
            beta: Exponent for temporary impact (typically 0.5–0.7).
            gamma: Exponent for permanent impact (typically 0.5).
        """
        self.temporary_impact_factor = temporary_impact_factor
        self.permanent_impact_factor = permanent_impact_factor
        self.beta = beta
        self.gamma = gamma

    def estimate(
        self,
        symbol: str,
        order_quantity: float,
        market_state: MarketState,
        time_fraction: float = 1.0,
        is_buy: bool = True,
    ) -> ImpactEstimate:
        """Estimate market impact for an order.

        Args:
            symbol: Trading symbol.
            order_quantity: Quantity to trade.
            market_state: Current market conditions.
            time_fraction: Fraction of day to execute (0–1).
            is_buy: True for buy orders, False for sell.

        Returns:
            ImpactEstimate with temporary, permanent, and total impact.
        """
        if order_quantity <= 0 or market_state.daily_volume <= 0:
            return ImpactEstimate(
                symbol=symbol,
                order_quantity=order_quantity,
                daily_volume=market_state.daily_volume,
                volatility=market_state.volatility_20d,
                spread_bps=market_state.spread_bps,
            )

        # Participation rate
        participation = order_quantity / market_state.daily_volume
        vol = market_state.volatility_20d

        # Square-root impact model (Almgren-Chriss)
        if time_fraction <= 0:
            time_fraction = 1.0 / 390  # 1 minute as minimum

        # Temporary impact (can be reduced by spreading over time)
        temp_impact_frac = (
            self.temporary_impact_factor
            * vol
            * math.pow(participation / time_fraction, self.beta)
        )

        # Permanent impact (information content, not reduced by time)
        perm_impact_frac = (
            self.permanent_impact_factor
            * vol
            * math.pow(participation, self.gamma)
        )

        # Convert to basis points
        temp_impact_bps = temp_impact_frac * 10000
        perm_impact_bps = perm_impact_frac * 10000
        total_impact_bps = temp_impact_bps + perm_impact_bps

        # Add half-spread cost
        spread_cost_bps = market_state.spread_bps / 2.0
        total_impact_bps += spread_cost_bps

        # Sign adjustment: buy pushes price up, sell pushes down
        sign = 1.0 if is_buy else -1.0
        total_impact_amount = (
            market_state.mid_price * order_quantity * total_impact_bps / 10000
        )

        return ImpactEstimate(
            symbol=symbol,
            order_quantity=order_quantity,
            daily_volume=market_state.daily_volume,
            volatility=vol,
            spread_bps=market_state.spread_bps,
            participation_rate=participation,
            temporary_impact_bps=round(temp_impact_bps, 2),
            permanent_impact_bps=round(perm_impact_bps, 2),
            total_impact_bps=round(total_impact_bps, 2),
            total_impact_amount=round(total_impact_amount, 2),
            confidence_interval=(
                round(total_impact_bps * 0.7, 2),
                round(total_impact_bps * 1.3, 2),
            ),
        )

    def estimate_sliced(
        self,
        symbol: str,
        total_quantity: float,
        num_slices: int,
        market_state: MarketState,
        is_buy: bool = True,
    ) -> ImpactEstimate:
        """Estimate impact when order is sliced into N parts.

        Slicing reduces temporary impact because each slice is a
        smaller order. The time_fraction is kept at 1.0 for each
        slice (each slice independently takes a day-equivalent),
        so the reduced quantity per slice directly lowers impact.

        Permanent impact scales with total quantity, not per-slice.

        Args:
            symbol: Trading symbol.
            total_quantity: Total order quantity.
            num_slices: Number of execution slices.
            market_state: Market conditions.
            is_buy: Buy or sell.

        Returns:
            ImpactEstimate with reduced temporary impact per slice.
        """
        if num_slices <= 0:
            num_slices = 1

        # Each slice is a smaller order taking the full day
        slice_qty = total_quantity / num_slices

        slice_impact = self.estimate(
            symbol=symbol,
            order_quantity=slice_qty,
            market_state=market_state,
            time_fraction=1.0,
            is_buy=is_buy,
        )

        # Permanent impact is based on total quantity, not per-slice
        vol = market_state.volatility_20d
        total_participation = total_quantity / market_state.daily_volume if market_state.daily_volume > 0 else 0
        perm_impact_frac = (
            self.permanent_impact_factor
            * vol
            * math.pow(total_participation, self.gamma)
        )
        perm_impact_bps = perm_impact_frac * 10000

        # Temporary impact per slice (each slice incurs this independently)
        temp_impact_bps = slice_impact.temporary_impact_bps

        # Total impact for any one slice
        spread_cost_bps = market_state.spread_bps / 2.0
        total_impact_bps = temp_impact_bps + perm_impact_bps + spread_cost_bps

        return ImpactEstimate(
            symbol=symbol,
            order_quantity=total_quantity,
            daily_volume=market_state.daily_volume,
            volatility=vol,
            spread_bps=market_state.spread_bps,
            participation_rate=slice_impact.participation_rate,
            temporary_impact_bps=round(temp_impact_bps, 2),
            permanent_impact_bps=round(perm_impact_bps, 2),
            total_impact_bps=round(total_impact_bps, 2),
            total_impact_amount=round(
                market_state.mid_price * slice_qty * total_impact_bps / 10000, 2
            ),
            confidence_interval=slice_impact.confidence_interval,
        )

    def compare_algorithms(
        self,
        symbol: str,
        total_quantity: float,
        market_state: MarketState,
        is_buy: bool = True,
    ) -> dict:
        """Compare impact across different slicing strategies.

        Args:
            symbol: Trading symbol.
            total_quantity: Total order quantity.
            market_state: Market conditions.
            is_buy: Buy or sell.

        Returns:
            Dict with impact estimates for each algorithm.
        """
        results = {}

        # Single order (no slicing)
        results["single_order"] = self.estimate(
            symbol, total_quantity, market_state, time_fraction=1.0, is_buy=is_buy
        ).to_dict()

        # TWAP (20 slices)
        results["twap_20"] = self.estimate_sliced(
            symbol, total_quantity, 20, market_state, is_buy=is_buy
        ).to_dict()

        # VWAP (26 slices)
        results["vwap_26"] = self.estimate_sliced(
            symbol, total_quantity, 26, market_state, is_buy=is_buy
        ).to_dict()

        # POV (continuous, 60+ slices)
        results["pov_60"] = self.estimate_sliced(
            symbol, total_quantity, 60, market_state, is_buy=is_buy
        ).to_dict()

        return results
