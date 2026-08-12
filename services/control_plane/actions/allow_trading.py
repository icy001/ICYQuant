"""
AllowTradingExecutor — request to resume / keep trading allowed.

Executors never mutate state.  This executor additionally guards the
fail-safe boundary: it refuses to request ALLOW while a kill switch is
ACTIVE (the kill switch outranks every allow decision).
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import KillSwitchState, PolicyContext


@register_executor
class AllowTradingExecutor(ActionExecutor):
    """Request ALLOW_TRADING for the action target."""

    action_type = PolicyActionType.ALLOW_TRADING

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        if context.kill_switch_state is KillSwitchState.ACTIVE:
            return ActionRequest(
                action_type=self.action_type,
                target=action.target or "GLOBAL",
                status="BLOCKED",
                detail="kill switch is ACTIVE; ALLOW cannot be requested",
                correlation_id=context.correlation_id,
            )
        return ActionRequest(
            action_type=self.action_type,
            target=action.target or "GLOBAL",
            status="REQUESTED",
            detail=action.detail or "trading allowed",
            correlation_id=context.correlation_id,
        )


def allow_trading(action: PolicyAction, context: PolicyContext) -> ActionRequest:
    return AllowTradingExecutor().execute(action, context)
