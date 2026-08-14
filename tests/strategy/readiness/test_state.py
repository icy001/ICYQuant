"""Tests for execution readiness state definitions."""

import re

from services.strategy.readiness.state import (
    EXECUTABLE_STATES,
    ExecutionReadiness,
    ReadinessContext,
    is_executable,
    new_evaluation_id,
    readiness_state_value,
)


def test_execution_readiness_enum_values() -> None:
    assert [s.value for s in ExecutionReadiness] == [
        "UNKNOWN",
        "NOT_READY",
        "CHECKING",
        "READY",
        "DEGRADED",
        "BLOCKED",
    ]


def test_execution_readiness_is_string_enum() -> None:
    assert ExecutionReadiness.READY == "READY"
    assert ExecutionReadiness.BLOCKED.value == "BLOCKED"


def test_only_ready_is_statically_executable() -> None:
    assert EXECUTABLE_STATES == frozenset({"READY"})
    assert is_executable(ExecutionReadiness.READY) is True
    assert is_executable("READY") is True
    for state in ("UNKNOWN", "NOT_READY", "CHECKING", "DEGRADED", "BLOCKED"):
        assert is_executable(state) is False


def test_readiness_state_value_normalises() -> None:
    assert readiness_state_value(ExecutionReadiness.BLOCKED) == "BLOCKED"
    assert readiness_state_value("DEGRADED") == "DEGRADED"


def test_readiness_context_defaults_fail_safe() -> None:
    context = ReadinessContext(strategy_id="STRAT-001")
    assert context.strategy_id == "STRAT-001"
    assert context.control_state == "UNKNOWN"
    assert context.runtime_state == "UNKNOWN"
    assert context.market_data_state == "UNKNOWN"
    assert context.configuration_state == "UNKNOWN"
    assert context.risk_state == "UNKNOWN"
    assert context.execution_state == "UNKNOWN"
    assert context.evaluation_id is None


def test_readiness_context_is_frozen() -> None:
    context = ReadinessContext(strategy_id="STRAT-001")
    try:
        context.runtime_state = "RUNNING"
    except Exception:
        return
    raise AssertionError("ReadinessContext must be frozen")


def test_new_evaluation_id_format() -> None:
    evaluation_id = new_evaluation_id(timestamp=1_752_940_000.0)
    assert re.fullmatch(r"READINESS-\d{8}-\d{6}", evaluation_id)


def test_new_evaluation_id_is_monotonic() -> None:
    first = new_evaluation_id()
    second = new_evaluation_id()
    assert first != second
    assert int(first.rsplit("-", 1)[1]) < int(second.rsplit("-", 1)[1])
