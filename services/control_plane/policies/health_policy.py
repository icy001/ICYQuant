"""
HealthPolicy — decide what to do based on component health.

Rule of thumb:

    Risk Engine UNHEALTHY          → CRITICAL → GLOBAL KILL
    Execution Engine UNHEALTHY     → HALT new orders + escalate
    Event Bus UNHEALTHY            → BLOCK (services cannot sync reliably)
    Position UNTRUSTED             → BLOCK + START_RECOVERY
    Ledger UNTRUSTED               → BLOCK (divergence)
    Market Data STALE              → DEGRADE → BLOCK → HALT (escalating)

Hysteresis (via context signals):

    3 consecutive failures        → BLOCK
    5 consecutive healthy checks  → ALLOW
"""

from __future__ import annotations

from ..domain.component_state import ComponentState
from ..domain.trading_gate import RiskIntegrity
from ..policy.policy import Policy
from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_condition import and_, condition, or_
from ..policy.policy_decision import PolicyDecision
from ..policy.policy_priority import PolicyPriority
from ..policy.policy_rule import PolicyRule

POLICY_ID = "core-health-policy"
POLICY_VERSION = "1.0.0"

UNHEALTHY = ComponentState.UNHEALTHY
DEGRADED = ComponentState.DEGRADED
UNTRUSTED = RiskIntegrity.UNTRUSTED

#: Market data staleness thresholds (seconds) driving escalation.
STALE_BLOCK_SECONDS = 10.0
STALE_HALT_SECONDS = 60.0


def build_health_policy() -> Policy:
    """Versioned core-health policy."""
    return (
        Policy(
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            name="Core Health Policy",
            description=(
                "Converts component health / integrity / market data "
                "freshness into operational decisions."
            ),
            priority=PolicyPriority.HIGH,
        )
        # -- risk engine --------------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="risk-dead-kill",
                condition=condition("risk_health", "equals", UNHEALTHY),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="RISK_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ACTIVATE_KILL_SWITCH,
                        target="GLOBAL",
                        reason="RISK_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="GLOBAL",
                        reason="RISK_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="RISK_ENGINE_UNHEALTHY",
                priority=PolicyPriority.CRITICAL,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="risk-degraded-restrict",
                condition=condition("risk_health", "equals", DEGRADED),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="RISK_ENGINE_DEGRADED",
                        detail="reduce new entries until risk recovers",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="RISK_ENGINE_DEGRADED",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- execution engine ---------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="execution-dead-halt",
                condition=condition("execution_health", "equals", UNHEALTHY),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="EXECUTION_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.HIGH,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="EXECUTION_ENGINE",
                        reason="EXECUTION_ENGINE_UNHEALTHY",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="EXECUTION_ENGINE_UNHEALTHY",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- event bus ----------------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="event-bus-down-block",
                condition=condition("event_bus_health", "equals", UNHEALTHY),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="EVENT_BUS_UNHEALTHY",
                        detail="trading services cannot synchronise reliably",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="EVENT_BUS_UNHEALTHY",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- position ------------------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="position-untrusted-block-recover",
                condition=or_(
                    condition("position_health", "equals", UNHEALTHY),
                    condition("position_integrity", "equals", UNTRUSTED),
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
                        reason="POSITION_STATE_UNTRUSTED",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="POSITION_STATE_UNTRUSTED",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- ledger --------------------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="ledger-untrusted-block",
                condition=or_(
                    condition("ledger_health", "equals", UNHEALTHY),
                    condition("ledger_integrity", "equals", UNTRUSTED),
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
                        reason="LEDGER_POSITION_DIVERGENCE",
                        priority=PolicyPriority.HIGH,
                    ),
                ],
                reason="LEDGER_STATE_UNTRUSTED",
                priority=PolicyPriority.HIGH,
            )
        )
        # -- market data (escalating) -------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="market-stale-degrade",
                condition=and_(
                    condition("market_data_freshness", "equals", "STALE"),
                    condition("market_data_stale_seconds", "less_than", 10.0),
                ),
                decision=PolicyDecision.DEGRADE,
                actions=[
                    PolicyAction(
                        PolicyActionType.DEGRADE_TRADING,
                        target="GLOBAL",
                        reason="MARKET_DATA_STALE",
                        priority=PolicyPriority.MEDIUM,
                    )
                ],
                reason="MARKET_DATA_STALE",
                priority=PolicyPriority.MEDIUM,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="market-stale-block",
                condition=and_(
                    condition("market_data_freshness", "equals", "STALE"),
                    condition(
                        "market_data_stale_seconds",
                        "greater_than",
                        STALE_BLOCK_SECONDS,
                    ),
                    condition(
                        "market_data_stale_seconds",
                        "less_than",
                        STALE_HALT_SECONDS,
                    ),
                ),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="MARKET_DATA_STALE_ESCALATED",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="MARKET_DATA_STALE_ESCALATED",
                priority=PolicyPriority.HIGH,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="market-critical-halt",
                condition=and_(
                    condition("market_data_freshness", "equals", "STALE"),
                    condition(
                        "market_data_stale_seconds",
                        "greater_than",
                        STALE_HALT_SECONDS,
                    ),
                ),
                decision=PolicyDecision.HALT,
                actions=[
                    PolicyAction(
                        PolicyActionType.HALT_TRADING,
                        target="GLOBAL",
                        reason="MARKET_DATA_CRITICAL",
                        priority=PolicyPriority.CRITICAL,
                    ),
                    PolicyAction(
                        PolicyActionType.ESCALATE_INCIDENT,
                        target="MARKET_DATA",
                        reason="MARKET_DATA_CRITICAL",
                        priority=PolicyPriority.CRITICAL,
                    ),
                ],
                reason="MARKET_DATA_CRITICAL",
                priority=PolicyPriority.CRITICAL,
            )
        )
        # -- hysteresis ----------------------------------------------------
        .add_rule(
            PolicyRule(
                rule_id="failure-threshold-block",
                condition=condition("consecutive_failures", "greater_than", 2),
                decision=PolicyDecision.BLOCK,
                actions=[
                    PolicyAction(
                        PolicyActionType.BLOCK_TRADING,
                        target="GLOBAL",
                        reason="CONSECUTIVE_FAILURE_THRESHOLD",
                        priority=PolicyPriority.HIGH,
                    )
                ],
                reason="CONSECUTIVE_FAILURE_THRESHOLD",
                priority=PolicyPriority.HIGH,
            )
        )
        .add_rule(
            PolicyRule(
                rule_id="recovery-threshold-allow",
                condition=and_(
                    condition("consecutive_healthy_checks", "greater_than", 4),
                    condition("risk_health", "equals", ComponentState.HEALTHY),
                    condition(
                        "execution_health", "equals", ComponentState.HEALTHY
                    ),
                ),
                decision=PolicyDecision.ALLOW,
                actions=[
                    PolicyAction(
                        PolicyActionType.ALLOW_TRADING,
                        target="GLOBAL",
                        reason="RECOVERY_CONFIRMED",
                        priority=PolicyPriority.LOW,
                    )
                ],
                reason="RECOVERY_CONFIRMED",
                priority=PolicyPriority.LOW,
            )
        )
    )
