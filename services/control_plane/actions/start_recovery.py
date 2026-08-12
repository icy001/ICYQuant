"""
StartRecoveryExecutor — request to start a recovery procedure.

The Recovery Engine (Commit 24 Part 1.5) performs the actual rebuild /
reconcile / repair / verify steps.  This executor only hands over the request
and records why recovery was requested.
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import PolicyContext


@register_executor
class StartRecoveryExecutor(ActionExecutor):
    """Request START_RECOVERY for a target component."""

    action_type = PolicyActionType.START_RECOVERY

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        target = action.target or "GLOBAL"
        return ActionRequest(
            action_type=self.action_type,
            target=target,
            status="REQUESTED",
            detail=action.detail or f"start recovery for {target}",
            correlation_id=context.correlation_id,
        )


def start_recovery(action: PolicyAction, context: PolicyContext) -> ActionRequest:
    return StartRecoveryExecutor().execute(action, context)
