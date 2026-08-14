"""Tests for the risk escalation engine, override policy and decision trace
(Commit 37 Part 1.3).

Covers the escalation matrix (APPROVE->ALLOW, WARNING->WARN, REJECT->BLOCK,
CRITICAL->FREEZE), the default policy and the override boundaries (CRITICAL
cannot be overridden by default).
"""

import pytest
from decimal import Decimal

from services.portfolio_risk import (
    EscalationLevel,
    PortfolioRiskDecision,
    RiskAction,
    RiskDecision,
    RiskEscalation,
    RiskEscalationEngine,
    RiskEscalationPolicy,
    RiskOverride,
    RiskOverrideEngine,
    RiskOverridePolicy,
)
from services.portfolio_risk.escalation import DEFAULT_POLICY


def build_policy():

    return RiskEscalationPolicy(
        policy_id="test-policy",

        warning_action=RiskAction.WARN,
        breach_action=RiskAction.BLOCK,
        critical_action=RiskAction.FREEZE,

        warning_level=EscalationLevel.L1,
        breach_level=EscalationLevel.L2,
        critical_level=EscalationLevel.L4,
    )


def test_warning_escalates_to_warn():

    engine = RiskEscalationEngine()

    decision = RiskDecision(
        decision=PortfolioRiskDecision.WARNING,
        warning_count=1,
        breach_count=0,
        critical_count=0,
        reason="warning",
        violations=(),
    )

    result = engine.evaluate(
        decision=decision,
        policy=build_policy(),
    )

    assert result.action == RiskAction.WARN
    assert result.level == EscalationLevel.L1


def test_reject_escalates_to_block():

    engine = RiskEscalationEngine()

    decision = RiskDecision(
        decision=PortfolioRiskDecision.REJECT,
        warning_count=0,
        breach_count=1,
        critical_count=0,
        reason="breach",
        violations=(),
    )

    result = engine.evaluate(
        decision=decision,
        policy=build_policy(),
    )

    assert result.action == RiskAction.BLOCK
    assert result.level == EscalationLevel.L2


def test_critical_escalates_to_freeze():

    engine = RiskEscalationEngine()

    decision = RiskDecision(
        decision=PortfolioRiskDecision.CRITICAL,
        warning_count=0,
        breach_count=0,
        critical_count=1,
        reason="critical",
        violations=(),
    )

    result = engine.evaluate(
        decision=decision,
        policy=build_policy(),
    )

    assert result.action == RiskAction.FREEZE
    assert result.level == EscalationLevel.L4


def test_approve_escalates_to_allow():

    engine = RiskEscalationEngine()

    decision = RiskDecision(
        decision=PortfolioRiskDecision.APPROVE,
        warning_count=0,
        breach_count=0,
        critical_count=0,
        reason="approved",
        violations=(),
    )

    result = engine.evaluate(
        decision=decision,
        policy=build_policy(),
    )

    assert result.action == RiskAction.ALLOW
    assert result.level == EscalationLevel.NONE


def test_disabled_policy_allows():

    engine = RiskEscalationEngine()

    decision = RiskDecision(
        decision=PortfolioRiskDecision.CRITICAL,
        warning_count=0,
        breach_count=0,
        critical_count=1,
        reason="critical",
        violations=(),
    )

    policy = RiskEscalationPolicy(
        policy_id="test-disabled",

        warning_action=RiskAction.WARN,
        breach_action=RiskAction.BLOCK,
        critical_action=RiskAction.FREEZE,

        warning_level=EscalationLevel.L1,
        breach_level=EscalationLevel.L2,
        critical_level=EscalationLevel.L4,

        enabled=False,
    )

    result = engine.evaluate(
        decision=decision,
        policy=policy,
    )

    assert result.action == RiskAction.ALLOW
    assert result.level == EscalationLevel.NONE
    assert "disabled" in result.reason


def test_default_policy_matrix():

    engine = RiskEscalationEngine()

    expectations = {
        PortfolioRiskDecision.APPROVE: (
            RiskAction.ALLOW,
            EscalationLevel.NONE,
        ),
        PortfolioRiskDecision.WARNING: (
            RiskAction.WARN,
            EscalationLevel.L1,
        ),
        PortfolioRiskDecision.REJECT: (
            RiskAction.BLOCK,
            EscalationLevel.L2,
        ),
        PortfolioRiskDecision.CRITICAL: (
            RiskAction.FREEZE,
            EscalationLevel.L4,
        ),
    }

    for decision, (action, level) in (
        expectations.items()
    ):

        result = engine.evaluate(
            decision=RiskDecision(
                decision=decision,
                warning_count=0,
                breach_count=0,
                critical_count=0,
                reason="test",
                violations=(),
            ),
            policy=DEFAULT_POLICY,
        )

        assert result.action == action
        assert result.level == level


def test_critical_override_is_blocked():

    override_policy = RiskOverridePolicy(
        allow_warning_override=True,
        allow_breach_override=True,
        allow_critical_override=False,
    )

    override = RiskOverride(
        override_id="override-001",
        decision=PortfolioRiskDecision.APPROVE,
        action=RiskAction.ALLOW,
        reason="Emergency approval",
        operator_id="risk-manager",
    )

    escalation = RiskEscalation(
        decision=PortfolioRiskDecision.CRITICAL,
        action=RiskAction.FREEZE,
        level=EscalationLevel.L4,
        reason="critical risk",
    )

    with pytest.raises(PermissionError):

        RiskOverrideEngine().apply(
            escalation=escalation,
            override=override,
            policy=override_policy,
        )


def test_breach_override_applies():

    override_policy = RiskOverridePolicy(
        allow_warning_override=True,
        allow_breach_override=True,
        allow_critical_override=False,
    )

    override = RiskOverride(
        override_id="override-002",
        decision=PortfolioRiskDecision.APPROVE,
        action=RiskAction.ALLOW,
        reason="Authorized by risk manager",
        operator_id="risk-manager",
    )

    escalation = RiskEscalation(
        decision=PortfolioRiskDecision.REJECT,
        action=RiskAction.BLOCK,
        level=EscalationLevel.L2,
        reason="risk breach",
    )

    result = RiskOverrideEngine().apply(
        escalation=escalation,
        override=override,
        policy=override_policy,
    )

    assert result.decision == PortfolioRiskDecision.APPROVE
    assert result.action == RiskAction.ALLOW
    assert result.level == EscalationLevel.L2
    assert "Risk override applied" in result.reason
