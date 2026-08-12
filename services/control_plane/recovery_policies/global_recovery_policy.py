"""
GlobalRecoveryPolicy — global fail-safe recovery rules.

While a recovery is RUNNING, new orders are denied regardless of partial health.
After the recovery completes, trading is only allowed back when the policy
agrees — recovery itself never re-opens the gate.
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.system_state import SystemState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import and_, condition, or_
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "global-recovery-policy"
POLICY_VERSION = "1.0.0"

UNHEALTHY = ComponentState.UNHEALTHY
UNTRUSTED = RiskIntegrity.UNTRUSTED


def build_global_recovery_policy() -> Policy:
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Global Recovery Policy",
            description=(
                "Global fail-safe recovery rules: risk failure escalates to "
                "a global recovery; a running recovery denies new orders."
            ),
            priority=PolicyPriority.CRITICAL,
        )
        # -- risk failure -> global recovery ------------------------------
        .add_rule(
            PolicyRule(
                rule_id="risk-untrusted-global-recovery",
                condition=or_(
                    condition("risk_integrity", "equals", UNTRUSTED),
                    condition("risk_health", "equals", UNHEALTHY),
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="RISK_FAILURE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="RISK_FAILURE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="GLOBAL",
                        detail="global integrity recovery",
                        reason="RISK_FAILURE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="RISK_FAILURE",
                priority=PolicyPriority.CRITICAL,
            )
        )
        # -- #43 recovery running -> new orders denied ---------------------
        .add_rule(
            PolicyRule(
                rule_id="recovery-running-deny",
                condition=condition("recovery_state", "equals", "RUNNING"),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_RUNNING",
                        detail="new orders denied while recovery is in progress",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="RECOVERY_RUNNING",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- #35 policy agrees -> resume -----------------------------------
        .add_rule(
            PolicyRule(
                rule_id="recovery-completed-allow",
                condition=and_(
                    condition("recovery_state", "equals", "COMPLETED"),
                    condition("risk_health", "equals", ComponentState.HEALTHY),
                    condition(
                        "position_integrity", "equals", RiskIntegrity.TRUSTED
                    ),
                    condition("ledger_integrity", "equals", RiskIntegrity.TRUSTED),
                ),
                decision=PolicyDecision.ALLOW,
                actions=[
                    PolicyAction(
                        PolicyActionType.ALLOW_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_COMPLETED_VERIFIED",
                        priority=PolicyPriority.LOW,
                    )
                ],
                reason="RECOVERY_COMPLETED_VERIFIED",
                priority=PolicyPriority.LOW,
            )
        )
        # -- system in recovery -> keep restricted -------------------------
        .add_rule(
            PolicyRule(
                rule_id="system-recovering-restrict",
                condition=condition("system_state", "equals", SystemState.RECOVERING),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="SYSTEM_RECOVERING",
                        detail="ramp-up in progress",
                        priority=PolicyPriority.MEDIUM,
                    )
                ],
                reason="SYSTEM_RECOVERING",
                priority=PolicyPriority.MEDIUM,
            )
        )
    )
