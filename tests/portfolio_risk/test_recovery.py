"""Tests for risk cooldown, hysteresis and breach recovery (Commit 37 Part 1.4).

Covers the recovery state machine (BREACHED/CRITICAL -> RECOVERING -> COOLDOWN
-> NORMAL), the recovery threshold hysteresis, cooldown timing, the reset
behaviour when risk returns above threshold, the recovery action mapping and
the service-level ``update_recovery_state`` delegation.
"""

from decimal import Decimal

from services.portfolio_risk import (
    PortfolioRiskService,
    RecoveryAction,
    RiskRecoveryPolicy,
    RiskRecoveryResult,
    RiskState,
)
from services.portfolio_risk.recovery import (
    RecoveryContext,
    RiskRecoveryEngine,
)


def build_policy():

    return RiskRecoveryPolicy(
        policy_id="test-policy",
        recovery_threshold=Decimal("1.80"),
        cooldown_seconds=300,
        required_recovery_checks=3,
    )


def test_recovery_requires_multiple_checks():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=100,
    )

    assert (
        context.state
        == RiskState.RECOVERING
    )

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=101,
    )

    assert (
        context.state
        == RiskState.RECOVERING
    )

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=102,
    )

    assert (
        context.state
        == RiskState.COOLDOWN
    )


def test_recovery_requires_cooldown():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=100,
    )

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=101,
    )

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=102,
    )

    assert (
        context.state
        == RiskState.COOLDOWN
    )

    # Cooldown started at t=102 (COOLDOWN entry); 300s elapse at t=402.
    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=402,
    )

    assert (
        context.state
        == RiskState.NORMAL
    )


def test_recovery_resets_when_risk_returns():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=100,
    )

    assert (
        context.state
        == RiskState.RECOVERING
    )

    engine.update(
        context=context,
        risk_value=Decimal("2.10"),
        policy=policy,
        now=101,
    )

    assert (
        context.recovery_checks == 0
    )

    assert (
        context.state
        == RiskState.RECOVERING
    )


def test_recovery_from_critical():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.CRITICAL
    )

    policy = build_policy()

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=100,
    )

    assert (
        context.state
        == RiskState.RECOVERING
    )

    assert (
        context.recovery_checks == 1
    )


def test_risk_above_threshold_keeps_state():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.WARNING,
        recovery_checks=2,
    )

    policy = build_policy()

    engine.update(
        context=context,
        risk_value=Decimal("1.90"),
        policy=policy,
        now=100,
    )

    assert (
        context.state
        == RiskState.WARNING
    )

    assert (
        context.recovery_checks == 0
    )


def test_disabled_policy_returns_normal():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.CRITICAL,
        recovery_checks=2,
        cooldown_started_at=5.0,
    )

    policy = RiskRecoveryPolicy(
        policy_id="test-disabled",
        recovery_threshold=Decimal("1.80"),
        cooldown_seconds=300,
        required_recovery_checks=3,
        enabled=False,
    )

    result = engine.update(
        context=context,
        risk_value=Decimal("2.50"),
        policy=policy,
        now=100,
    )

    assert result == RiskState.NORMAL
    assert context.recovery_checks == 0
    assert context.cooldown_started_at is None


def test_recovery_action_mapping():

    engine = RiskRecoveryEngine()

    expectations = {
        RiskState.CRITICAL: (
            RecoveryAction.CONTINUE_BLOCK
        ),
        RiskState.BREACHED: (
            RecoveryAction.REDUCE_ONLY
        ),
        RiskState.RECOVERING: (
            RecoveryAction.REDUCE_ONLY
        ),
        RiskState.COOLDOWN: (
            RecoveryAction.COOLDOWN
        ),
        RiskState.NORMAL: (
            RecoveryAction.RESTORE
        ),
        RiskState.WARNING: (
            RecoveryAction.NONE
        ),
    }

    for state, action in (
        expectations.items()
    ):

        assert (
            engine.action_for_state(state)
            == action
        )


def test_recovery_result_reports_recovered():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    for now in (100, 101, 102):

        engine.update(
            context=context,
            risk_value=Decimal("1.70"),
            policy=policy,
            now=now,
        )

    result = engine.build_result(
        previous_state=RiskState.BREACHED,
        context=context,
        policy=policy,
        now=102,
    )

    assert isinstance(
        result, RiskRecoveryResult
    )
    assert (
        result.current_state
        == RiskState.COOLDOWN
    )
    assert result.action == RecoveryAction.COOLDOWN
    assert result.recovered is False
    assert (
        result.cooldown_remaining_seconds == 300
    )

    engine.update(
        context=context,
        risk_value=Decimal("1.70"),
        policy=policy,
        now=403,
    )

    result = engine.build_result(
        previous_state=RiskState.COOLDOWN,
        context=context,
        policy=policy,
        now=403,
    )

    assert (
        result.current_state
        == RiskState.NORMAL
    )
    assert result.action == RecoveryAction.RESTORE
    assert result.recovered is True
    assert (
        result.cooldown_remaining_seconds == 0
    )


def test_cooldown_remaining_seconds():

    engine = RiskRecoveryEngine()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    for now in (100, 101, 102):

        engine.update(
            context=context,
            risk_value=Decimal("1.70"),
            policy=policy,
            now=now,
        )

    result = engine.build_result(
        previous_state=RiskState.BREACHED,
        context=context,
        policy=policy,
        now=150,
    )

    assert (
        result.cooldown_remaining_seconds == 252
    )

    assert (
        result.recovery_checks == 3
    )


def test_service_update_recovery_state():

    service = PortfolioRiskService()

    context = RecoveryContext(
        state=RiskState.BREACHED
    )

    policy = build_policy()

    result = service.update_recovery_state(
        context=context,
        risk_value="1.70",
        policy=policy,
        now=100,
    )

    assert result == RiskState.RECOVERING
    assert (
        context.state
        == RiskState.RECOVERING
    )
