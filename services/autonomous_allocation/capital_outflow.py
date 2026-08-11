"""Capital Outflow — handles capital leaving the system.

When capital must be withdrawn, the system computes:
which positions should be reduced first?

Priority for reduction:
1. Low alpha strategies
2. High risk strategies
3. High impact (illiquid) strategies  
4. High correlation strategies
5. Low capacity efficiency strategies

NOT equal proportion across all strategies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReductionCandidate:
    """A candidate for capital reduction."""
    strategy_id: str
    current_capital: float = 0.0
    reduction_amount: float = 0.0
    remaining_capital: float = 0.0
    reduction_score: float = 0.0  # Higher = more desirable to reduce
    alpha_score: float = 0.0
    risk_score: float = 0.0
    impact_score: float = 0.0
    correlation_score: float = 0.0
    capacity_score: float = 0.0
    reason: str = ""


@dataclass
class CapitalOutflowResult:
    """Result of processing capital outflow."""
    outflow_amount: float = 0.0
    reductions: Dict[str, ReductionCandidate] = field(default_factory=dict)
    total_reduced: float = 0.0
    shortfall: float = 0.0  # Couldn't reduce enough
    released_from_reserve: float = 0.0
    released_from_buffer: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = [f"CapitalOutflow: {self.outflow_amount:,.0f} total"]
        for sid, cand in self.reductions.items():
            lines.append(
                f"  {sid}: -{cand.reduction_amount:,.0f} "
                f"(score={cand.reduction_score:.3f}, {cand.reason})"
            )
        if self.shortfall > 0:
            lines.append(f"  SHORTFALL: {self.shortfall:,.0f}")
        return "\n".join(lines)


class CapitalOutflow:
    """Manages capital outflow by prioritizing reductions intelligently.

    Instead of equal-proportion reduction, targets:
    1. Lowest alpha strategies first
    2. Highest risk
    3. Most illiquid
    4. Most correlated
    5. Most capacity-inefficient
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._alpha_weight = self._config.get("alpha_weight", 0.25)
        self._risk_weight = self._config.get("risk_weight", 0.25)
        self._impact_weight = self._config.get("impact_weight", 0.20)
        self._correlation_weight = self._config.get("correlation_weight", 0.15)
        self._capacity_weight = self._config.get("capacity_weight", 0.15)

    def process_outflow(self, outflow_amount: float,
                        current_allocations: Dict[str, float],
                        strategy_scores: Dict[str, Dict[str, float]],
                        reserve_amount: float = 0.0,
                        buffer_amount: float = 0.0) -> CapitalOutflowResult:
        """Process a capital outflow event.

        Determines which strategies should be reduced and by how much.
        """
        result = CapitalOutflowResult(outflow_amount=outflow_amount)

        # First, try to release from reserve and buffer
        released_reserve = min(reserve_amount, outflow_amount * 0.4)
        released_buffer = min(buffer_amount, outflow_amount * 0.3)
        from_reserves = released_reserve + released_buffer
        remaining = outflow_amount - from_reserves

        result.released_from_reserve = released_reserve
        result.released_from_buffer = released_buffer

        if remaining <= 0:
            return result

        # Score each strategy for reduction desirability
        candidates = []
        for sid, capital in current_allocations.items():
            if capital <= 0:
                continue

            scores = strategy_scores.get(sid, {})
            alpha = scores.get("alpha_score", 0.5)
            risk = scores.get("risk_score", 0.5)
            impact = scores.get("impact_score", 0.5)
            corr = scores.get("correlation_score", 0.5)
            cap_score = scores.get("capacity_score", 0.5)

            # Reduction desirability: higher = reduce this first
            # Low alpha → high desirability; High risk → high desirability, etc.
            reduction_score = (
                self._alpha_weight * (1.0 - alpha) +
                self._risk_weight * risk +
                self._impact_weight * (1.0 - impact) +
                self._correlation_weight * corr +
                self._capacity_weight * (1.0 - cap_score)
            )

            candidates.append((sid, capital, reduction_score, scores))

        # Sort by reduction desirability (highest first)
        candidates.sort(key=lambda x: x[2], reverse=True)

        reductions = {}
        remaining_to_reduce = remaining

        for sid, capital, red_score, scores in candidates:
            if remaining_to_reduce <= 0:
                break

            # Can't reduce more than current allocation
            reduce_amount = min(capital * 0.80, remaining_to_reduce)
            remaining_capital = capital - reduce_amount

            # Determine reason
            alpha = scores.get("alpha_score", 0.5)
            risk = scores.get("risk_score", 0.5)
            reasons = []
            if alpha < 0.3:
                reasons.append("low_alpha")
            if risk > 0.7:
                reasons.append("high_risk")
            if scores.get("impact_score", 0.5) < 0.3:
                reasons.append("illiquid")

            reductions[sid] = ReductionCandidate(
                strategy_id=sid,
                current_capital=capital,
                reduction_amount=reduce_amount,
                remaining_capital=remaining_capital,
                reduction_score=red_score,
                alpha_score=alpha,
                risk_score=risk,
                reason=", ".join(reasons) if reasons else "prioritized",
            )
            remaining_to_reduce -= reduce_amount

        result.reductions = reductions
        result.total_reduced = sum(r.reduction_amount for r in reductions.values())
        result.shortfall = max(0.0, remaining - result.total_reduced)

        return result
