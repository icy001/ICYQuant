"""LiquidityShock — liquidity evaporation shock simulation.

Simulates sudden liquidity drops (volume, depth, spread) and
recomputes execution capacity, market impact, and exit costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LiquidityShockResult:
    """Result of a liquidity shock simulation."""

    volume_decline_pct: float = 0.0
    depth_decline_pct: float = 0.0
    spread_increase_pct: float = 0.0

    original_daily_volume: float = 0.0
    shocked_daily_volume: float = 0.0

    original_exit_days: float = 0.0
    shocked_exit_days: float = 0.0

    original_impact_bps: float = 0.0
    shocked_impact_bps: float = 0.0

    exit_cost_increase: float = 0.0
    capital_at_risk: float = 0.0
    can_exit: bool = True
    warning: str = ""


class LiquidityShockSimulator:
    """Simulates liquidity shock impacts.

    Connection to Part 1.3 (Capacity & Liquidity):
    Recomputes execution capacity and market impact under
    liquidity-stressed conditions.

    Usage::

        sim = LiquidityShockSimulator()
        result = sim.simulate(
            volume_decline_pct=-50.0,
            depth_decline_pct=-60.0,
            spread_increase_pct=100.0,
            position_sizes={"strat_A": 15_000_000},
            daily_volumes={"strat_A": 5_000_000},
        )
        if not result.can_exit:
            print("WARNING: Portfolio cannot be exited within reasonable time")
    """

    def __init__(self, max_exit_days: int = 20, sqrt_impact_model: bool = True):
        self._max_exit_days = max_exit_days
        self._sqrt_impact = sqrt_impact_model

    def simulate(
        self,
        volume_decline_pct: float,
        depth_decline_pct: float,
        spread_increase_pct: float,
        position_sizes: Dict[str, float],
        daily_volumes: Dict[str, float],
        participation_rates: Optional[Dict[str, float]] = None,
    ) -> LiquidityShockResult:
        """Simulate a liquidity shock.

        Args:
            volume_decline_pct: volume decline % (negative = drop)
            depth_decline_pct: market depth decline %
            spread_increase_pct: spread increase %
            position_sizes: {strategy/asset_id: position_value}
            daily_volumes: {strategy/asset_id: daily_volume}
            participation_rates: {strategy/asset_id: participation_rate}
        """
        import math

        vol_factor = 1.0 + volume_decline_pct / 100.0
        depth_factor = 1.0 + depth_decline_pct / 100.0
        spread_factor = 1.0 + spread_increase_pct / 100.0

        total_position = sum(position_sizes.values())
        total_volume = sum(daily_volumes.values())

        shocked_volume = total_volume * vol_factor

        # exit time
        original_exit_days = total_position / max(total_volume * 0.1, 1e-9)
        shocked_exit_days = total_position / max(shocked_volume * 0.1, 1e-9)

        # market impact
        # Simple sqrt model: impact = σ * sqrt(Q / V)
        # where Q = trade size, V = daily volume
        original_impact = 0.0
        shocked_impact = 0.0

        if self._sqrt_impact:
            for sid in position_sizes:
                pos = position_sizes[sid]
                vol = daily_volumes.get(sid, 1.0)
                part_rate = (participation_rates or {}).get(sid, 0.1)
                # impact ~ sqrt(participation_rate) * vol_adjustment
                base_impact = math.sqrt(part_rate) * 10  # bps
                original_impact += base_impact * (pos / max(total_position, 1e-9))

                # shocked impact scales with depth and spread
                shocked_base = base_impact / max(depth_factor, 0.01) * spread_factor
                shocked_impact += shocked_base * (pos / max(total_position, 1e-9))

        # exit cost increase
        exit_cost_increase = (shocked_exit_days - original_exit_days) * 0.01 * total_position

        # whether portfolio can exit within acceptable time
        can_exit = shocked_exit_days <= self._max_exit_days

        warning = ""
        if not can_exit:
            warning = (
                f"Exit would take {shocked_exit_days:.0f} days "
                f"(max: {self._max_exit_days}) under liquidity shock"
            )

        return LiquidityShockResult(
            volume_decline_pct=volume_decline_pct,
            depth_decline_pct=depth_decline_pct,
            spread_increase_pct=spread_increase_pct,
            original_daily_volume=total_volume,
            shocked_daily_volume=shocked_volume,
            original_exit_days=original_exit_days,
            shocked_exit_days=shocked_exit_days,
            original_impact_bps=original_impact,
            shocked_impact_bps=shocked_impact,
            exit_cost_increase=exit_cost_increase,
            capital_at_risk=total_position,
            can_exit=can_exit,
            warning=warning,
        )

    def compute_liquidity_adjusted_var(
        self,
        current_var: float,
        liquidity_shock_pct: float,
    ) -> float:
        """Adjust VaR for liquidity conditions.

        During liquidity shocks, actual risk is higher than
        mark-to-market risk suggests.
        """
        liq_multiplier = 1.0 + abs(liquidity_shock_pct) / 100.0
        return current_var * liq_multiplier
