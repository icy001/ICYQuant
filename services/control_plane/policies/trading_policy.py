"""
TradingPolicy — what may the system do with trading given the TradingState?

    TRADING_READY      → ALLOW (when system is ready)
    TRADING_DEGRADED   → DEGRADE (constrain trading)
    TRADING_DISABLED   → BLOCK (startup phase)
    TRADING_HALTED     → BLOCK / HALT (hard stop)

The Trading Gate still applies its own order-level logic on top of this
decision (e.g. REDUCE_ONLY allowed while new entries are denied).
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.system_state import SystemState
from ..domain.trading_state import TradingState
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import and_, condition
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "trading-safety-policy"
POLICY_VERSION = "1.0.0"


def build_trading_policy() -> Policy:
    """Versioned trading-safety policy."""
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Trading Safety Policy",
            description=(
                "Maps TradingState and SystemState onto the operational "
                "decision for trading."
            ),
            priority=PolicyPriority.HIGH,
        )
        .add_rule(
            PolicyRule(
                rule_id="trading-halted-block",
                condition=condition(
                    "trading_state", "equals", TradingState.TRADING_HALTED
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="TRADING_HALTED",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="TRADING_HALTED",
                priority=PolicyPriority.HIGH,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="trading-disabled-block",
                condition=condition(
                    "trading_state", "equals", TradingState.TRADING_DISABLED
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="TRADING_DISABLED",
                        priority=PolicyPriority.MEDIUM,
                    )
                ],
                reason="TRADING_DISABLED",
                priority=PolicyPriority.MEDIUM,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="trading-degraded-restrict",
                condition=condition(
                    "trading_state", "equals", TradingState.TRADING_DEGRADED
                ),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="TRADING_DEGRADED",
                        detail="constrain risk-taking; allow risk-reducing flow",
                        priority=PolicyPriority.MEDIUM,
                    )
                ],
                reason="TRADING_DEGRADED",
                priority=PolicyPriority.MEDIUM,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="trading-ready-allow",
                condition=and_(
                    condition(
                        "trading_state", "equals", TradingState.TRADING_READY
                    ),
                    condition("system_state", "equals", SystemState.READY),
                    condition(
                        "risk_health",
                        "not_equals",
                        ComponentState.UNHEALTHY,
                    ),
                    condition(
                        "execution_health",
                        "not_equals",
                        ComponentState.UNHEALTHY,
                    ),
                ),
                decision=PolicyDecision.ALLOW,
                actions=[
                    PolicyAction(
                        PolicyActionType.ALLOW_TRADING,
                        target="GLOBAL",
                        reason="TRADING_READY",
                        priority=PolicyPriority.LOW,
                    )
                ],
                reason="TRADING_READY",
                priority=PolicyPriority.LOW,
            )
        )
    )
