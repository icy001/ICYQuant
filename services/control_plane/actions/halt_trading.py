"""
HaltTradingExecutor — request a trading halt.

Trading Halt ≠ System Shutdown.  Health checks, recovery, reconciliation and
auditing keep running while trading is halted.  Whether existing orders are
cancelled is decided by the Execution Safety Policy — not by a blind cancel.
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import KillSwitchState, PolicyContext


@register_executor
class HaltTradingExecutor(ActionExecutor):
    """Request HALT_TRADING for the action target."""

    action_type = PolicyActionType.HALT_TRADING

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        status = "REQUESTED"
        detail = action.detail or "trading halted"
        if context.kill_switch_state is KillSwitchState.ACTIVE:
            status = "ALREADY_HALTED"
            detail = "already halted by an active kill switch"
        return ActionRequest(
            action_type=self.action_type,
            target=action.target or "GLOBAL",
            status=status,
            detail=detail,
            correlation_id=context.correlation_id,
        )


def halt_trading(action: PolicyAction, context: PolicyContext) -> ActionRequest:
    return HaltTradingExecutor().execute(action, context)
