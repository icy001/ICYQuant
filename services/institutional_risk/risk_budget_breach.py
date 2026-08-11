"""RiskBudgetBreach — risk budget breach handling.

Handles cases where risk budget is exceeded with automated
responses: RESIZE, REDUCE, FREEZE, REBALANCE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class BreachAction(Enum):
    RESIZE = auto()
    REDUCE = auto()
    FREEZE = auto()
    REBALANCE = auto()
    EMERGENCY = auto()


@dataclass
class BreachResponse:
    """Response to a risk budget breach."""

    action: BreachAction
    entity_id: str
    current_usage: float
    budget_limit: float
    excess: float
    recommended_reduction: float
    severity: str = "MODERATE"
    message: str = ""


class RiskBudgetBreachHandler:
    """Handles risk budget breaches.

    Usage::

        handler = RiskBudgetBreachHandler()
        response = handler.handle_breach(
            entity_id="strat_A",
            current_usage=2_500_000,
            budget_limit=2_000_000,
        )
        print(f"Action: {response.action.name}, Reduce by {response.recommended_reduction:.0f}")
    """

    def __init__(
        self,
        freeze_threshold_pct: float = 120.0,
        emergency_threshold_pct: float = 150.0,
    ):
        self._freeze = freeze_threshold_pct
        self._emergency = emergency_threshold_pct

    def handle_breach(
        self,
        entity_id: str,
        current_usage: float,
        budget_limit: float,
        total_budget: float = 0.0,
    ) -> BreachResponse:
        """Handle a risk budget breach.

        Args:
            entity_id: the entity exceeding its budget
            current_usage: current risk used
            budget_limit: allocated risk budget
            total_budget: total capital risk budget (for context)
        """
        excess = current_usage - budget_limit
        excess_pct = (current_usage / max(budget_limit, 1e-9)) * 100

        # determine action
        if excess_pct >= self._emergency:
            action = BreachAction.EMERGENCY
            severity = "CRITICAL"
            reduction = current_usage - budget_limit * 0.7  # reduce below limit
        elif excess_pct >= self._freeze:
            action = BreachAction.FREEZE
            severity = "HIGH"
            reduction = excess
        elif excess_pct > 100:
            action = BreachAction.REDUCE
            severity = "MODERATE"
            reduction = excess * 1.1  # reduce a bit more than excess
        else:
            # close to breach → resize
            action = BreachAction.RESIZE
            severity = "LOW"
            reduction = max(0.0, current_usage - budget_limit * 0.9)

        message = self._format_message(action, entity_id, current_usage, budget_limit)

        return BreachResponse(
            action=action,
            entity_id=entity_id,
            current_usage=current_usage,
            budget_limit=budget_limit,
            excess=excess,
            recommended_reduction=reduction,
            severity=severity,
            message=message,
        )

    def _format_message(
        self,
        action: BreachAction,
        entity_id: str,
        usage: float,
        limit: float,
    ) -> str:
        """Format a human-readable message."""
        pct = (usage / max(limit, 1e-9)) * 100
        return (
            f"{action.name}: {entity_id} at {pct:.0f}% of budget "
            f"({usage:,.0f}/{limit:,.0f})"
        )
