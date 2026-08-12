"""
DegradeTradingExecutor — request to constrain trading (degraded mode).

DEGRADE ≠ HALT EVERYTHING.  Typically it means:

    - new entries denied
    - reduce-only / risk-reducing orders still allowed
    - high-risk order types restricted

The exact per-order interpretation lives in the Trading Gate.
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import PolicyContext


@register_executor
class DegradeTradingExecutor(ActionExecutor):
    """Request DEGRADE_TRADING for the action target."""

    action_type = PolicyActionType.DEGRADE_TRADING

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        return ActionRequest(
            action_type=self.action_type,
            target=action.target or "GLOBAL",
            status="REQUESTED",
            detail=(
                action.detail
                or "trading degraded: new entries denied, reduce-only allowed"
            ),
            correlation_id=context.correlation_id,
        )


def degrade_trading(
    action: PolicyAction, context: PolicyContext
) -> ActionRequest:
    return DegradeTradingExecutor().execute(action, context)
