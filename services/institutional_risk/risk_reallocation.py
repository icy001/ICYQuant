"""RiskReallocation — risk budget reallocation engine.

Moves risk budget from low-efficiency to high-efficiency
strategies based on real-time metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ReallocationMove:
    """A reallocation move."""

    from_entity: str
    to_entity: str
    risk_amount: float
    from_efficiency: float
    to_efficiency: float
    expected_efficiency_gain: float
    reason: str


@dataclass
class ReallocationPlan:
    """Complete risk reallocation plan."""

    moves: List[ReallocationMove] = field(default_factory=list)
    total_risk_moved: float = 0.0
    efficiency_before: float = 0.0
    efficiency_after: float = 0.0
    efficiency_improvement_pct: float = 0.0


class RiskReallocationEngine:
    """Reallocates risk budget for optimal efficiency.

    Usage::

        engine = RiskReallocationEngine()
        plan = engine.plan(
            current_allocations={"A": 1_500_000, "B": 3_000_000},
            efficiencies={"A": 0.8, "B": 1.7},
        )
        for move in plan.moves:
            print(f"{move.from_entity} → {move.to_entity}: {move.risk_amount:.0f}")
    """

    def __init__(
        self,
        efficiency_gap_threshold: float = 0.3,
        max_reallocation_pct: float = 30.0,
    ):
        self._gap_threshold = efficiency_gap_threshold
        self._max_reallocation = max_reallocation_pct

    def plan(
        self,
        current_allocations: Dict[str, float],
        efficiencies: Dict[str, float],
        risk_contributions: Optional[Dict[str, float]] = None,
    ) -> ReallocationPlan:
        """Plan risk budget reallocation.

        Moves risk from below-average efficiency to above-average.

        Args:
            current_allocations: {entity_id: current_risk_allocation}
            efficiencies: {entity_id: risk_efficiency_score}
            risk_contributions: optional risk contribution values
        """
        common = set(current_allocations.keys()) & set(efficiencies.keys())
        if not common:
            return ReallocationPlan()

        avg_eff = sum(efficiencies[e] for e in common) / len(common)

        # identify donors (below avg) and recipients (above avg)
        donors = [
            (e, efficiencies[e], current_allocations[e])
            for e in common if efficiencies[e] < avg_eff - self._gap_threshold
        ]
        recipients = [
            (e, efficiencies[e], current_allocations[e])
            for e in common if efficiencies[e] > avg_eff + self._gap_threshold
        ]

        donors.sort(key=lambda x: x[1])
        recipients.sort(key=lambda x: x[1], reverse=True)

        moves: List[ReallocationMove] = []
        total_moved = 0.0

        for donor_id, donor_eff, donor_alloc in donors:
            movable = donor_alloc * (self._max_reallocation / 100)
            if movable <= 0:
                continue

            for recip_id, recip_eff, recip_alloc in recipients:
                if movable <= 0:
                    break
                if donor_id == recip_id:
                    continue

                amount = min(movable, donor_alloc * 0.5)  # move at most 50%
                if amount > 0:
                    moves.append(ReallocationMove(
                        from_entity=donor_id,
                        to_entity=recip_id,
                        risk_amount=amount,
                        from_efficiency=donor_eff,
                        to_efficiency=recip_eff,
                        expected_efficiency_gain=(recip_eff - donor_eff) * amount,
                        reason=f"Efficiency gap: {donor_eff:.2f} → {recip_eff:.2f}",
                    ))
                    total_moved += amount
                    movable -= amount

        # weighted average efficiency before/after
        total_risk = sum(current_allocations.values())
        eff_before = 0.0
        if total_risk > 0:
            eff_before = sum(
                current_allocations[e] * efficiencies.get(e, 0.0)
                for e in current_allocations
            ) / total_risk

        eff_after = eff_before
        if total_risk > 0:
            eff_after = (eff_before * total_risk + sum(
                m.expected_efficiency_gain for m in moves
            )) / total_risk

        improvement = 0.0
        if eff_before > 0:
            improvement = (eff_after - eff_before) / eff_before * 100

        return ReallocationPlan(
            moves=moves,
            total_risk_moved=total_moved,
            efficiency_before=eff_before,
            efficiency_after=eff_after,
            efficiency_improvement_pct=improvement,
        )
