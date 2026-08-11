"""RiskDeleveraging — automated deleveraging engine.

Reduces leverage in a smart way: not across-the-board but
targeting the highest-risk, lowest-alpha positions first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DeleveragingTarget:
    """A deleveraging target."""

    entity_id: str
    current_leverage: float
    target_leverage: float
    reduction_pct: float
    risk_contribution: float
    alpha_efficiency: float
    priority: int


@dataclass
class DeleveragingPlan:
    """A complete deleveraging plan."""

    current_total_leverage: float
    target_total_leverage: float
    targets: List[DeleveragingTarget] = field(default_factory=list)
    total_risk_reduction: float = 0.0
    estimated_execution_cost: float = 0.0
    steps: int = 1


class RiskDeleveragingEngine:
    """Automated smart deleveraging.

    Priority order for reduction:
    1. High risk, low alpha
    2. High correlation (cluster risk)
    3. High market impact (expensive to trade)
    4. Low liquidity (hard to exit)

    Usage::

        engine = RiskDeleveragingEngine()
        plan = engine.plan(
            strategies={
                "A": {"leverage": 2.0, "risk": 3_000_000, "alpha": 0.15, "liquidity": 0.9},
                "B": {"leverage": 3.0, "risk": 4_000_000, "alpha": 0.08, "liquidity": 0.4},
            },
            target_leverage=1.5,
        )
    """

    def plan(
        self,
        strategies: Dict[str, Dict[str, Any]],
        target_leverage: float,
        current_total_leverage: Optional[float] = None,
        max_steps: int = 3,
    ) -> DeleveragingPlan:
        """Create a smart deleveraging plan.

        Args:
            strategies: {strategy_id: {leverage, risk, alpha, liquidity, correlation}}
            target_leverage: desired total leverage
            current_total_leverage: current total leverage (computed if None)
            max_steps: maximum number of execution steps
        """
        if current_total_leverage is None:
            current_total_leverage = sum(
                s.get("leverage", 1.0) for s in strategies.values()
            )

        if current_total_leverage <= target_leverage:
            return DeleveragingPlan(
                current_total_leverage=current_total_leverage,
                target_total_leverage=target_leverage,
            )

        total_reduction_needed = current_total_leverage - target_leverage
        total_risk = sum(s.get("risk", 0.0) for s in strategies.values())

        # score each strategy for deleveraging priority
        scored: List[Tuple[str, Dict[str, Any], float]] = []

        for sid, s in strategies.items():
            risk = s.get("risk", 0.0)
            alpha = s.get("alpha", 0.0)
            liquidity = s.get("liquidity", 0.5)
            correlation = s.get("correlation", 0.3)
            leverage = s.get("leverage", 1.0)

            # priority score: higher = reduce first
            # high risk + low alpha + low liquidity + high correlation → high priority
            risk_score = risk / max(total_risk, 1e-9) if total_risk > 0 else 0
            alpha_inv = 1.0 / max(alpha, 0.01)
            liq_inv = 1.0 / max(liquidity, 0.1)

            priority = risk_score * 2 + alpha_inv * 0.5 + liq_inv * 0.3 + correlation * 1.0
            scored.append((sid, s, priority))

        scored.sort(key=lambda x: x[2], reverse=True)

        targets: List[DeleveragingTarget] = []
        remaining = total_reduction_needed

        for sid, s, priority in scored:
            if remaining <= 0:
                break

            current_lev = s.get("leverage", 1.0)
            # each strategy contributes proportionally to reduction
            contribution = current_lev / max(current_total_leverage, 1e-9) * total_reduction_needed
            contribution = min(contribution, current_lev - 1.0)  # don't go below 1x

            if contribution > 0:
                risk_contrib = s.get("risk", 0.0)
                alpha_eff = s.get("alpha", 0.0) / max(risk_contrib, 1e-9)

                targets.append(DeleveragingTarget(
                    entity_id=sid,
                    current_leverage=current_lev,
                    target_leverage=current_lev - contribution,
                    reduction_pct=(contribution / max(current_lev, 1e-9)) * 100,
                    risk_contribution=risk_contrib,
                    alpha_efficiency=alpha_eff,
                    priority=int(priority),
                ))
                remaining -= contribution

        # estimate execution cost (rough)
        execution_cost = sum(
            t.risk_contribution * 0.001 for t in targets
        )

        return DeleveragingPlan(
            current_total_leverage=current_total_leverage,
            target_total_leverage=target_leverage,
            targets=targets,
            total_risk_reduction=sum(t.risk_contribution * (t.reduction_pct / 100) for t in targets),
            estimated_execution_cost=execution_cost,
            steps=min(max_steps, len(targets)),
        )
