"""
RecoveryPolicy — how the system should behave during / after recovery.

    recovery RUNNING      → DEGRADE (restrict new exposure while repairing)
    recovery FAILED       → BLOCK + escalate + retry
    recovery COMPLETED + all integrity TRUSTED
                          → RECOVER (start the ramp-up back to normal)

Recovery never jumps straight back to NORMAL — the engine returns RECOVER and
the Control Plane steps through RESTRICTED → DEGRADED → NORMAL (ramp-up).
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import and_, condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "recovery-progression-policy"
POLICY_VERSION = "1.0.0"


def build_recovery_policy() -> Policy:
    """Versioned recovery-progression policy."""
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Recovery Progression Policy",
            description=(
                "Governs trading while the system is recovering and gates "
                "the ramp back to normal operation."
            ),
            priority=PolicyPriority.HIGH,
        )
        .add_rule(
            PolicyRule(
                rule_id="recovery-running-restrict",
                condition=condition("recovery_state", "equals", "RUNNING"),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_IN_PROGRESS",
                        detail="reduce-only until recovery completes",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="RECOVERY_IN_PROGRESS",
                priority=PolicyPriority.HIGH,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="recovery-failed-block",
                condition=condition("recovery_state", "equals", "FAILED"),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_FAILED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="GLOBAL",
                        reason="RECOVERY_FAILED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="GLOBAL",
                        reason="RECOVERY_FAILED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="RECOVERY_FAILED",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="recovery-verified-ramp",
                condition=and_(
                    condition("recovery_state", "equals", "COMPLETED"),
                    condition(
                        "position_integrity",
                        "equals",
                        RiskIntegrity.TRUSTED,
                    ),
                    condition("ledger_integrity", "equals", RiskIntegrity.TRUSTED),
                    condition(
                        "risk_health", "equals", ComponentState.HEALTHY
                    ),
                ),
                decision=PolicyDecision.RECOVER,
                actions=[
                    PolicyAction(
                        PolicyActionType.ALLOW_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_VERIFIED",
                        detail="ramp-up: RESTRICTED → DEGRADED → NORMAL",
                        priority=PolicyPriority.LOW,
                    )
                ],
                reason="RECOVERY_VERIFIED",
                priority=PolicyPriority.LOW,
            )
        )
    )
