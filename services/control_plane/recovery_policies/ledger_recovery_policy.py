"""
LedgerRecoveryPolicy — trigger ledger recovery.

A corrupted / diverged ledger blocks trading and requests a LEDGER recovery.
The ledger is rebuilt from snapshot + event stream by the orchestrator; the
ledger remains the source of truth (never direct UPDATEs).
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import condition, or_
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "ledger-recovery-policy"
POLICY_VERSION = "1.0.0"

UNHEALTHY = ComponentState.UNHEALTHY
UNTRUSTED = RiskIntegrity.UNTRUSTED


def build_ledger_recovery_policy() -> Policy:
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Ledger Recovery Policy",
            description=(
                "Triggers a ledger rebuild when ledger state is untrusted "
                "or unhealthy."
            ),
            priority=PolicyPriority.HIGH,
        )
        .add_rule(
            PolicyRule(
                rule_id="ledger-untrusted-start-recovery",
                condition=or_(
                    condition("ledger_integrity", "equals", UNTRUSTED),
                    condition("ledger_health", "equals", UNHEALTHY),
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="LEDGER_STATE_UNTRUSTED",
                        priority=PolicyPriority.HIGH,
                    ),
                    PolicyAction(
                        PolicyActionType.START_RECOVERY,
                        target="LEDGER",
                        detail="rebuild ledger from snapshot + events",
                        reason="LEDGER_POSITION_DIVERGENCE",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="LEDGER_STATE_UNTRUSTED",
                priority=PolicyPriority.HIGH,
            )
        )
    )
