"""
PositionRecoveryPolicy — trigger position recovery.

A corrupted / untrusted position is blocked and a recovery is requested for the
POSITION scope.  The recovery itself is orchestrated by the RecoveryOrchestrator
(rebuild from ledger + events) — the policy only fires the request.
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import or_
from ..policy.policy_condition import condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "position-recovery-policy"
POLICY_VERSION = "1.0.0"

UNHEALTHY = ComponentState.UNHEALTHY
UNTRUSTED = RiskIntegrity.UNTRUSTED


def build_position_recovery_policy() -> Policy:
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Position Recovery Policy",
            description=(
                "Triggers a position rebuild when position state is "
                "untrusted or unhealthy."
            ),
            priority=PolicyPriority.HIGH,
        )
        .add_rule(
            PolicyRule(
                rule_id="position-untrusted-start-recovery",
                condition=or_(
                    condition("position_integrity", "equals", UNTRUSTED),
                    condition("position_health", "equals", UNHEALTHY),
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="POSITION_STATE_UNTRUSTED",
                        priority=PolicyPriority.HIGH,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="POSITION",
                        detail="rebuild position from ledger + events",
                        reason="POSITION_STATE_UNTRUSTED",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="POSITION_STATE_UNTRUSTED",
                priority=PolicyPriority.HIGH,
            )
        )
    )
