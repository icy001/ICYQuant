"""
EventRecoveryPolicy — trigger event-stream recovery.

When the event bus / event stream is unhealthy the system cannot synchronise
reliably: block trading and request an EVENTS recovery (replay + reconcile).
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "event-recovery-policy"
POLICY_VERSION = "1.0.0"

UNHEALTHY = ComponentState.UNHEALTHY


def build_event_recovery_policy() -> Policy:
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Event Recovery Policy",
            description=(
                "Blocks trading and triggers an event replay when the "
                "event bus is unhealthy."
            ),
            priority=PolicyPriority.HIGH,
        )
        .add_rule(
            PolicyRule(
                rule_id="event-bus-unhealthy-start-recovery",
                condition=condition("event_bus_health", "equals", UNHEALTHY),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="EVENT_BUS_UNHEALTHY",
                        priority=PolicyPriority.HIGH,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="EVENTS",
                        detail="replay + reconcile event stream",
                        reason="EVENT_BUS_UNHEALTHY",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="EVENT_BUS_UNHEALTHY",
                priority=PolicyPriority.HIGH,
            )
        )
    )
