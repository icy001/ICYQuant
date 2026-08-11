"""EmergencyLiquidation — emergency position liquidation engine.

Prioritizes liquidation by:
1. Highest risk positions first
2. Highest liquidity risk → exit quickly
3. Highest leverage → reduce immediately
4. Highest tail exposure → close

This is NOT "liquidate everything" — it's smart, prioritized reduction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LiquidationCandidate:
    """A position considered for emergency liquidation."""

    entity_id: str
    position_value: float
    risk_contribution: float
    liquidity_score: float
    leverage: float
    tail_exposure: float
    urgency_score: float = 0.0
    recommended_reduction_pct: float = 0.0
    reason: str = ""


@dataclass
class LiquidationPlan:
    """Emergency liquidation plan."""

    candidates: List[LiquidationCandidate] = field(default_factory=list)
    total_reduction: float = 0.0
    total_position_value: float = 0.0
    estimated_impact_bps: float = 0.0
    estimated_recovery_score: float = 100.0
    urgency_level: str = "NORMAL"


class EmergencyLiquidationEngine:
    """Emergency liquidation engine.

    Usage::

        engine = EmergencyLiquidationEngine()
        plan = engine.plan(
            positions={
                "A": {"value": 20_000_000, "risk": 4_000_000, "liquidity": 0.9, "leverage": 2.0},
                "B": {"value": 15_000_000, "risk": 6_000_000, "liquidity": 0.2, "leverage": 3.0},
            },
            target_reduction_pct=40.0,
        )
    """

    def __init__(
        self,
        risk_weight: float = 2.0,
        liquidity_weight: float = 1.5,
        leverage_weight: float = 1.0,
        tail_weight: float = 1.5,
    ):
        self._w_risk = risk_weight
        self._w_liquidity = liquidity_weight
        self._w_leverage = leverage_weight
        self._w_tail = tail_weight

    def plan(
        self,
        positions: Dict[str, Dict[str, Any]],
        target_reduction_pct: float,
        max_individual_reduction_pct: float = 80.0,
    ) -> LiquidationPlan:
        """Plan emergency liquidation.

        Args:
            positions: {entity_id: {value, risk, liquidity, leverage, tail_exposure}}
            target_reduction_pct: % of total position value to reduce
            max_individual_reduction_pct: max reduction for any single position
        """
        if not positions:
            return LiquidationPlan()

        total_value = sum(p.get("value", 0.0) for p in positions.values())
        target_reduction = total_value * (target_reduction_pct / 100.0)

        # compute urgency scores
        candidates: List[LiquidationCandidate] = []

        for sid, pos in positions.items():
            value = pos.get("value", 0.0)
            risk = pos.get("risk", 0.0)
            liquidity = pos.get("liquidity", 0.5)
            leverage = pos.get("leverage", 1.0)
            tail = pos.get("tail_exposure", 0.0)

            # urgency = weighted sum of normalized metrics
            risk_score = risk / max(total_value * 0.01, 1e-9)
            liq_score = (1.0 - liquidity) * 100
            lev_score = leverage * 10
            tail_score = tail * 20

            urgency = (
                risk_score * self._w_risk
                + liq_score * self._w_liquidity
                + lev_score * self._w_leverage
                + tail_score * self._w_tail
            )

            candidates.append(LiquidationCandidate(
                entity_id=sid,
                position_value=value,
                risk_contribution=risk,
                liquidity_score=liquidity,
                leverage=leverage,
                tail_exposure=tail,
                urgency_score=urgency,
                reason=f"Urgency: {urgency:.1f} (risk:{risk_score:.1f}, liq:{liq_score:.1f}, lev:{lev_score:.1f}, tail:{tail_score:.1f})",
            ))

        # sort by urgency (highest first)
        candidates.sort(key=lambda c: c.urgency_score, reverse=True)

        # assign reductions
        remaining = target_reduction
        for candidate in candidates:
            if remaining <= 0:
                break

            max_reduction = candidate.position_value * (max_individual_reduction_pct / 100)
            reduction = min(remaining, max_reduction, candidate.position_value)
            candidate.recommended_reduction_pct = (reduction / max(candidate.position_value, 1e-9)) * 100
            remaining -= reduction

        # urgency level
        urgency = "NORMAL"
        avg_urgency = sum(c.urgency_score for c in candidates) / max(len(candidates), 1)
        if avg_urgency > 70:
            urgency = "CRITICAL"
        elif avg_urgency > 40:
            urgency = "HIGH"

        # estimate impact
        est_impact = len(candidates) * 5  # rough bps

        return LiquidationPlan(
            candidates=candidates,
            total_reduction=target_reduction - remaining,
            total_position_value=total_value,
            estimated_impact_bps=est_impact,
            urgency_level=urgency,
        )
