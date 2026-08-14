"""Tests for the strategy execution session."""

from datetime import datetime

import pytest

from services.strategy.execution.session import (
    ExecutionSessionError,
    ExecutionSessionState,
    StrategyExecutionSession,
    new_session_id,
    session_state_value,
)


def make_session(**overrides) -> StrategyExecutionSession:
    fields = {"strategy_id": "STRAT-001", "now": 1000.0}
    fields.update(overrides)
    return StrategyExecutionSession(**fields)


def test_session_starts_created() -> None:
    session = make_session()
    assert session.state == ExecutionSessionState.CREATED
    assert session.state_value == "CREATED"
    assert session.can_create_intent() is False
    assert session.intent_count == 0


def test_new_session_id_format() -> None:
    timestamp = 1775000000.0
    expected_date = datetime.fromtimestamp(timestamp).strftime("%Y%m%d")
    session_id = new_session_id("STRAT001", timestamp)
    assert session_id.startswith("SESSION-STRAT001-%s-" % expected_date)
    assert session_id.rsplit("-", 1)[-1].isdigit()


def test_session_activation() -> None:
    session = make_session()
    session.activate()
    assert session.state == ExecutionSessionState.ACTIVE
    assert session.activated_at == 1000.0
    assert session.can_create_intent() is True


def test_active_session_registers_intent() -> None:
    session = make_session()
    session.activate()
    session.register_intent()
    assert session.intent_count == 1


def test_pause_blocks_intent_creation() -> None:
    session = make_session()
    session.activate()
    session.pause()
    assert session.state == ExecutionSessionState.PAUSED
    assert session.can_create_intent() is False


def test_resume_reactivates_session() -> None:
    session = make_session()
    session.activate()
    session.pause()
    session.resume()
    assert session.state == ExecutionSessionState.ACTIVE
    assert session.activated_at == 1000.0


def test_close_requires_closing() -> None:
    session = make_session()
    session.activate()
    session.start_closing()
    assert session.state == ExecutionSessionState.CLOSING
    assert session.can_create_intent() is False
    session.close()
    assert session.state == ExecutionSessionState.CLOSED
    assert session.closed_at == 1000.0


def test_fail_marks_session_failed() -> None:
    session = make_session()
    session.activate()
    session.fail("killed")
    assert session.state == ExecutionSessionState.FAILED
    assert session.failed_reason == "killed"


def test_invalid_transition_raises() -> None:
    session = make_session()
    session.activate()
    with pytest.raises(ExecutionSessionError):
        session.close()  # ACTIVE -> CLOSED requires CLOSING first


def test_register_intent_requires_active_session() -> None:
    session = make_session()
    with pytest.raises(ExecutionSessionError):
        session.register_intent()


def test_session_snapshot() -> None:
    session = make_session()
    session.activate()
    session.register_intent()
    snapshot = session.snapshot()
    assert snapshot["session_id"] == session.session_id
    assert snapshot["strategy_id"] == "STRAT-001"
    assert snapshot["state"] == "ACTIVE"
    assert snapshot["intent_count"] == 1


def test_session_state_value_helper() -> None:
    assert session_state_value(ExecutionSessionState.ACTIVE) == "ACTIVE"
    assert session_state_value("CLOSED") == "CLOSED"
