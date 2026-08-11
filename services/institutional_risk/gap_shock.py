"""GapShock — price gap shock simulation.

Simulates discontinuous price gaps (no trading at intermediate
prices), especially important for overnight positions and
event risk in low-liquidity assets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GapShockResult:
    """Result of a gap shock simulation."""

    gap_pct: float = 0.0
    immediate_loss: float = 0.0
    loss_pct_of_capital: float = 0.0
    affected_positions: List[str] = field(default_factory=list)
    stop_loss_breach: bool = False
    margin_call_triggered: bool = False
    overnight_exposure_at_risk: float = 0.0


class GapShockSimulator:
    """Simulates price gap events.

    Price gaps are especially dangerous because:
    - Stop losses don't execute at the stop price
    - No opportunity to reduce position during the gap
    - Margin calls can be triggered immediately

    Usage::

        sim = GapShockSimulator()
        result = sim.simulate(
            gap_pct=-10.0,
            positions={"strat_A": {"value": 15_000_000, "overnight": True}},
            capital=100_000_000,
            margin_requirement=30_000_000,
        )
    """

    def __init__(
        self,
        margin_call_trigger_pct: float = 20.0,
        stop_loss_gap_multiplier: float = 1.5,
    ):
        self._margin_threshold = margin_call_trigger_pct
        self._stop_loss_multiplier = stop_loss_gap_multiplier

    def simulate(
        self,
        gap_pct: float,
        positions: Dict[str, Dict[str, Any]],
        capital: float,
        margin_requirement: float = 0.0,
        stop_losses: Optional[Dict[str, float]] = None,
    ) -> GapShockResult:
        """Simulate a gap shock.

        Args:
            gap_pct: price gap percentage (negative = gap down)
            positions: {position_id: {"value": float, "overnight": bool}}
            capital: total capital pool
            margin_requirement: current margin requirement
            stop_losses: {position_id: stop_loss_price_pct}
        """
        gap = gap_pct / 100.0
        total_loss = 0.0
        affected = []
        overnight_at_risk = 0.0

        for pid, pos in positions.items():
            value = pos.get("value", 0.0)
            is_overnight = pos.get("overnight", False)

            if is_overnight:
                overnight_at_risk += value

            loss = value * gap
            total_loss += loss

            # check stop loss breach
            if stop_losses and pid in stop_losses:
                stop_pct = stop_losses[pid]
                if abs(gap_pct) > abs(stop_pct) * self._stop_loss_multiplier:
                    affected.append(pid)

        loss_pct = (abs(total_loss) / max(capital, 1e-9)) * 100

        # margin call check
        margin_call = False
        if margin_requirement > 0:
            remaining_capital = capital + total_loss  # total_loss is negative
            if remaining_capital < margin_requirement:
                margin_call = True

        return GapShockResult(
            gap_pct=gap_pct,
            immediate_loss=abs(total_loss),
            loss_pct_of_capital=loss_pct,
            affected_positions=affected,
            stop_loss_breach=len(affected) > 0,
            margin_call_triggered=margin_call,
            overnight_exposure_at_risk=overnight_at_risk,
        )

    def compute_worst_case_gap(
        self,
        portfolio_value: float,
        max_historical_gap_pct: float,
        overnight_pct: float,
    ) -> float:
        """Estimate worst-case gap loss.

        Args:
            portfolio_value: total portfolio value
            max_historical_gap_pct: worst historical gap (absolute %)
            overnight_pct: fraction of portfolio held overnight
        """
        return portfolio_value * overnight_pct * (max_historical_gap_pct / 100.0)
