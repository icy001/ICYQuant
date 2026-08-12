"""
BlockTradingExecutor — request to block new trading flow.

A block stops new orders but (unlike HALT) still permits risk-reducing
operations decided by the Trading Gate / Execution Safety Policy.
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import PolicyContext


@register_executor
class BlockTradingExecutor(ActionExecutor):
    """Request BLOCK_TRADING for the action target."""

    action_type = PolicyActionType.BLOCK_TRADING

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        return ActionRequest(
            action_type=self.action_type,
            target=action.target or "GLOBAL",
            status="REQUESTED",
            detail=action.detail or "new trading flow blocked",
            correlation_id=context.correlation_id,
        )


def block_trading(action: PolicyAction, context: PolicyContext) -> ActionRequest:
    return BlockTradingExecutor().execute(action, context)
