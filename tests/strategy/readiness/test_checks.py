"""Tests for the individual readiness checks."""

from services.strategy.readiness.checks import (
    DEFAULT_READINESS_CHECKS,
    ConfigurationCheck,
    ExecutionConnectivityCheck,
    LifecycleCheck,
    MarketDataReadinessCheck,
    RiskReadinessCheck,
    RuntimeCheck,
)
from services.strategy.readiness.state import ReadinessContext


def context(**overrides) -> ReadinessContext:
    fields = {"strategy_id": "STRAT-001", "timestamp": 1000.0}
    fields.update(overrides)
    return ReadinessContext(**fields)


def test_lifecycle_check_requires_running() -> None:
    check = LifecycleCheck()
    assert check.name == "lifecycle"
    assert check.check(context(control_state="RUNNING")).passed is True
    failed = check.check(context(control_state="PAUSED"))
    assert failed.passed is False
    assert failed.hard is True


def test_runtime_check_requires_running() -> None:
    check = RuntimeCheck()
    assert check.name == "runtime"
    assert check.check(context(runtime_state="RUNNING")).passed is True
    for state in ("STOPPED", "UNKNOWN", "DEGRADED", "FAILED"):
        failed = check.check(context(runtime_state=state))
        assert failed.passed is False
        assert failed.hard is True


def test_market_data_check_accepts_fresh_feed() -> None:
    check = MarketDataReadinessCheck()
    assert check.name == "market_data"
    assert check.check(context(market_data_state="FRESH")).passed is True
    assert check.check(context(market_data_state="CONNECTED")).passed is True
    failed = check.check(context(market_data_state="STALE"))
    assert failed.passed is False
    assert failed.hard is True


def test_configuration_check_requires_valid_config() -> None:
    check = ConfigurationCheck()
    assert check.name == "configuration"
    assert check.check(context(configuration_state="VALID")).passed is True
    failed = check.check(context(configuration_state="INVALID"))
    assert failed.passed is False
    assert failed.hard is True


def test_risk_check_blocks_when_blocked() -> None:
    check = RiskReadinessCheck()
    assert check.name == "risk"
    assert check.check(context(risk_state="ALLOWED")).passed is True
    assert check.check(context(risk_state="OK")).passed is True
    failed = check.check(context(risk_state="BLOCKED"))
    assert failed.passed is False
    assert failed.hard is True


def test_execution_check_requires_connectivity() -> None:
    check = ExecutionConnectivityCheck()
    assert check.name == "execution"
    assert check.check(context(execution_state="CONNECTED")).passed is True
    failed = check.check(context(execution_state="DISCONNECTED"))
    assert failed.passed is False
    assert failed.hard is True


def test_default_checks_cover_the_full_core_set() -> None:
    names = [check.name for check in DEFAULT_READINESS_CHECKS]
    assert names == [
        "lifecycle",
        "runtime",
        "market_data",
        "configuration",
        "risk",
        "execution",
    ]
