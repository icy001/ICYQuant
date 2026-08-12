"""
ActivateKillSwitchExecutor — request to arm a kill switch.

Kill Switch activation is guarded against accidental triggers:

    - a GLOBAL kill requires a non-empty reason (and the caller/actor is
      tracked through ``correlation_id`` / ``detail``)
    - requesting a kill when one is already ACTIVE is idempotent
      (status = ALREADY_ACTIVE)

Policy requests; the Kill Switch component performs the actual activation.
"""

from __future__ import annotations

from . import ActionExecutor, ActionRequest, register_executor
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import KillSwitchState, PolicyContext


@register_executor
class ActivateKillSwitchExecutor(ActionExecutor):
    """Request ACTIVATE_KILL_SWITCH for a scope."""

    action_type = PolicyActionType.ACTIVATE_KILL_SWITCH

    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        target = action.target or "GLOBAL"

        # A kill without a reason is never issued (anti-accidental-trigger).
        if not action.reason:
            return ActionRequest(
                action_type=self.action_type,
                target=target,
                status="REJECTED",
                detail="kill switch requires a non-empty reason",
                correlation_id=context.correlation_id,
            )

        if (
            context.kill_switch_state is KillSwitchState.ACTIVE
            and (not context.kill_switch_scope or context.kill_switch_scope == target)
        ):
            return ActionRequest(
                action_type=self.action_type,
                target=target,
                status="ALREADY_ACTIVE",
                detail="kill switch already active for this scope",
                correlation_id=context.correlation_id,
            )

        return ActionRequest(
            action_type=self.action_type,
            target=target,
            status="REQUESTED",
            detail=f"activate kill switch for {target}: {action.reason}",
            correlation_id=context.correlation_id,
        )


def activate_kill_switch(
    action: PolicyAction, context: PolicyContext
) -> ActionRequest:
    return ActivateKillSwitchExecutor().execute(action, context)
