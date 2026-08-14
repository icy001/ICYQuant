"""Tests for the execution context snapshot."""

import dataclasses

import pytest

from services.strategy.execution.context import ExecutionContext


def make_context(**overrides) -> ExecutionContext:
    fields = {
        "strategy_id": "STRAT-001",
        "lifecycle_state": "RUNNING",
        "runtime_state": "RUNNING",
        "readiness_state": "READY",
        "risk_state": "ALLOWED",
        "execution_state": "CONNECTED",
        "market_timestamp": 999.0,
        "readiness_checked_at": 995.0,
        "timestamp": 1000.0,
    }
    fields.update(overrides)
    return ExecutionContext(**fields)


def test_context_defaults_fail_safe() -> None:
    context = ExecutionContext(strategy_id="STRAT-001")
    assert context.lifecycle_state == "UNKNOWN"
    assert context.runtime_state == "UNKNOWN"
    assert context.readiness_state == "UNKNOWN"
    assert context.risk_state == "UNKNOWN"
    assert context.execution_state == "UNKNOWN"


def test_context_records_snapshot_fields() -> None:
    context = make_context()
    assert context.strategy_id == "STRAT-001"
    assert context.market_timestamp == 999.0
    assert context.readiness_checked_at == 995.0
    assert context.timestamp == 1000.0


def test_context_is_frozen() -> None:
    context = make_context()
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.risk_state = "BLOCKED"
