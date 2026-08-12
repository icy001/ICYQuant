"""
EmergencyPolicy — the highest-severity policy bundle.

Triggers:

    Global Critical Failure        (operational_state == EMERGENCY)
    Multiple Critical Components   (critical_unhealthy_components >= 2)
    Integrity Failure              (risk_integrity UNTRUSTED)
    Global Kill active             (kill_switch ACTIVE on GLOBAL scope)

Actions:

    ACTIVATE_GLOBAL_KILL
    HALT_TRADING
    ESCALATE_INCIDENT

Emergency policy wins every conflict — its decision rank is the highest in
the fail-safe ordering.
"""

from __future__ import annotations

from ..domain.operational_state import OperationalState
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import and_, condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "global-emergency-policy"
POLICY_VERSION = "1.0.0"


def build_emergency_policy() -> Policy:
    """Versioned global-emergency policy."""
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Global Emergency Policy",
            description=(
                "Highest-priority policy: global kill + halt + escalation "
                "on catastrophic conditions."
            ),
            priority=PolicyPriority.CRITICAL,
        )
        .add_rule(
            PolicyRule(
                rule_id="emergency-mode-global-kill",
                condition=condition(
                    "operational_state", "equals", OperationalState.EMERGENCY
                ),
                decision=PolicyDecision.ESCALATE,
                actions=[
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="EMERGENCY_MODE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="EMERGENCY_MODE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="GLOBAL",
                        reason="EMERGENCY_MODE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="EMERGENCY_MODE",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="global-kill-active-halt",
                condition=and_(
                    condition("kill_switch_state", "equals", "ACTIVE"),
                    condition("kill_switch_scope", "equals", "GLOBAL"),
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="GLOBAL_KILL_ACTIVE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="GLOBAL",
                        reason="GLOBAL_KILL_ACTIVE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="GLOBAL_KILL_ACTIVE",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="multiple-critical-failures-kill",
                condition=condition(
                    "critical_unhealthy_components", "greater_than", 1
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="MULTIPLE_CRITICAL_FAILURES",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="MULTIPLE_CRITICAL_FAILURES",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="GLOBAL",
                        reason="MULTIPLE_CRITICAL_FAILURES",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="MULTIPLE_CRITICAL_FAILURES",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-integrity-emergency-kill",
                condition=condition("risk_integrity", "equals", "UNTRUSTED"),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="RISK_INTEGRITY_UNTRUSTED",
                        priority=PolicyPriority.CRITICAL,
                    )
                ],
                reason="RISK_INTEGRITY_UNTRUSTED",
                priority=PolicyPriority.CRITICAL,
            )
        )
    )
