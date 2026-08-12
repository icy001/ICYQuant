"""
RiskPolicy — what to do when risk / position / ledger integrity degrades.

    risk_integrity UNTRUSTED        → GLOBAL KILL (risk inputs cannot be trusted)
    risk_integrity DEGRADED         → DEGRADE + manual approval for new exposure
    position_integrity UNTRUSTED    → BLOCK + START_RECOVERY
    ledger_integrity UNTRUSTED      → BLOCK + START_RECOVERY (divergence)
    risk_health UNHEALTHY           → GLOBAL KILL

Ledger vs Position divergence is handled via ``ledger_integrity``:

    ledger == position              → TRUSTED → healthy
    ledger != position, unresolved  → UNTRUSTED → BLOCK / HALT
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "risk-integrity-policy"
POLICY_VERSION = "1.0.0"


def build_risk_policy() -> Policy:
    """Versioned risk-integrity policy."""
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Risk Integrity Policy",
            description=(
                "Protects the system when risk / position / ledger integrity "
                "can no longer be trusted."
            ),
            priority=PolicyPriority.CRITICAL,
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-integrity-kill",
                condition=condition(
                    "risk_integrity", "equals", RiskIntegrity.UNTRUSTED
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="RISK_INTEGRITY_UNTRUSTED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="RISK_INTEGRITY_UNTRUSTED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="RISK_INTEGRITY_UNTRUSTED",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-integrity-degrade",
                condition=condition(
                    "risk_integrity", "equals", RiskIntegrity.DEGRADED
                ),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="RISK_INTEGRITY_DEGRADED",
                        priority=PolicyPriority.HIGH,
                    ),
                    PolicyAction(
                        PolicyActionType.REQUIRE_MANUAL_APPROVAL,
                        target="RISK",
                        reason="RISK_INTEGRITY_DEGRADED",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="RISK_INTEGRITY_DEGRADED",
                priority=PolicyPriority.HIGH,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="position-integrity-failed",
                condition=condition(
                    "position_integrity", "equals", RiskIntegrity.UNTRUSTED
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="POSITION_INTEGRITY_FAILED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="POSITION",
                        reason="POSITION_INTEGRITY_FAILED",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="POSITION_INTEGRITY_FAILED",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="ledger-divergence-block",
                condition=condition(
                    "ledger_integrity", "equals", RiskIntegrity.UNTRUSTED
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="LEDGER_POSITION_DIVERGENCE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="LEDGER",
                        reason="LEDGER_POSITION_DIVERGENCE",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="LEDGER_POSITION_DIVERGENCE",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-health-dead-kill",
                condition=condition(
                    "risk_health", "equals", ComponentState.UNHEALTHY
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="RISK_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.CRITICAL,
                    )
                ],
                reason="RISK_ENGINE_UNHEALTHY",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-health-degraded-restrict",
                condition=condition(
                    "risk_health", "equals", ComponentState.DEGRADED
                ),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="RISK_ENGINE_DEGRADED",
                        priority=PolicyPriority.MEDIUM,
                    )
                ],
                reason="RISK_ENGINE_DEGRADED",
                priority=PolicyPriority.MEDIUM,
            )
        )
    )
