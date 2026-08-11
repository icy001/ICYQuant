"""Capital Inflow — handles new capital entering the system.

New capital is not simply distributed proportionally.
Instead, the system re-computes: where should marginal capital go?

Maximizes risk-adjusted MCE for each unit of new capital.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CapitalInflowResult:
    """Result of processing capital inflow."""
    inflow_amount: float = 0.0
    allocated: Dict[str, float] = field(default_factory=dict)  # strategy_id → amount
    reserved: float = 0.0
    buffered: float = 0.0
    unallocated: float = 0.0
    total_allocation: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = [f"CapitalInflow: {self.inflow_amount:,.0f} total"]
        for sid, amount in self.allocated.items():
            lines.append(f"  {sid}: +{amount:,.0f}")
        lines.append(f"  Reserve: +{self.reserved:,.0f}")
        lines.append(f"  Buffer: +{self.buffered:,.0f}")
        if self.unallocated > 0:
            lines.append(f"  Unallocated: {self.unallocated:,.0f}")
        return "\n".join(lines)


class CapitalInflow:
    """Manages new capital inflow allocation.

    Strategy: allocate to strategies with highest risk-adjusted MCE first,
    respecting capacity limits, then overflow to reserve.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._default_reserve_ratio = self._config.get("reserve_ratio", 0.10)
        self._default_buffer_ratio = self._config.get("buffer_ratio", 0.05)

    def process_inflow(self, inflow_amount: float,
                       strategy_scores: Dict[str, Dict[str, float]],
                       current_allocations: Dict[str, float],
                       capacity_limits: Dict[str, float],
                       reserve_ratio: Optional[float] = None,
                       buffer_ratio: Optional[float] = None) -> CapitalInflowResult:
        """Process a capital inflow event.

        Args:
            inflow_amount: Amount of new capital
            strategy_scores: {strategy_id: {marginal_alpha, risk_score, capacity_score, ...}}
            current_allocations: {strategy_id: current_capital}
            capacity_limits: {strategy_id: max_capacity}
            reserve_ratio: Fraction to reserve
            buffer_ratio: Fraction to buffer
        """
        rr = reserve_ratio if reserve_ratio is not None else self._default_reserve_ratio
        br = buffer_ratio if buffer_ratio is not None else self._default_buffer_ratio

        reserve_amount = inflow_amount * rr
        buffer_amount = inflow_amount * br
        deployable = inflow_amount - reserve_amount - buffer_amount

        result = CapitalInflowResult(
            inflow_amount=inflow_amount,
            reserved=reserve_amount,
            buffered=buffer_amount,
        )

        if deployable <= 0:
            result.unallocated = inflow_amount
            return result

        # Compute RAMCE for each strategy
        scored = []
        for sid, scores in strategy_scores.items():
            marginal_alpha = scores.get("marginal_alpha", 0.0)
            marginal_risk = scores.get("marginal_risk", 0.0)
            marginal_cost = scores.get("marginal_cost", 0.0)

            denominator = marginal_risk + marginal_cost
            rams = marginal_alpha / denominator if denominator > 0 else marginal_alpha

            # Available headroom
            current = current_allocations.get(sid, 0.0)
            cap = capacity_limits.get(sid, float("inf"))
            headroom = max(0.0, cap - current)

            scored.append((sid, rams, headroom, scores))

        # Sort by RAMCE descending
        scored.sort(key=lambda x: x[1], reverse=True)

        allocated = {}
        remaining = deployable

        for sid, rams, headroom, scores in scored:
            if remaining <= 0:
                break
            if headroom <= 0:
                continue

            # Allocate proportional to RAMCE
            total_rams = sum(max(0, s[1]) for s in scored)
            if total_rams > 0:
                share = remaining * (max(0, rams) / total_rams)
            else:
                share = remaining / len(scored)

            alloc = min(share, headroom, remaining)
            allocated[sid] = alloc
            remaining -= alloc

        result.allocated = allocated
        result.total_allocation = sum(allocated.values())
        result.unallocated = remaining

        return result
