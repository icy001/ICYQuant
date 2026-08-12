"""Tests for ControlDecision / ControlDecisionReason (spec sections 8 and 13)."""
from __future__ import annotations

from services.control_plane.gateway.decision import (
    ControlDecision,
    ControlDecisionReason,
)


def test_decision_values():
    assert ControlDecision.ALLOW.value == "ALLOW"
    assert ControlDecision.REDUCE_ONLY.value == "REDUCE_ONLY"
    assert ControlDecision.BLOCK.value == "BLOCK"


def test_decision_is_blocking():
    assert ControlDecision.BLOCK.is_blocking is True
    assert ControlDecision.ALLOW.is_blocking is False
    assert ControlDecision.REDUCE_ONLY.is_blocking is False


def test_decision_permits():
    assert ControlDecision.ALLOW.permits is True
    assert ControlDecision.REDUCE_ONLY.permits is True
    assert ControlDecision.BLOCK.permits is False


def test_decision_reason_values():
    assert ControlDecisionReason.NO_ACTIVE_CONTROL.value == "NO_ACTIVE_CONTROL"
    assert ControlDecisionReason.GLOBAL_KILL_SWITCH.value == "GLOBAL_KILL_SWITCH"
    assert ControlDecisionReason.ACCOUNT_BLOCKED.value == "ACCOUNT_BLOCKED"
    assert ControlDecisionReason.STRATEGY_DISABLED.value == "STRATEGY_DISABLED"
    assert ControlDecisionReason.SYMBOL_BLOCKED.value == "SYMBOL_BLOCKED"
    assert ControlDecisionReason.VENUE_DISABLED.value == "VENUE_DISABLED"
    assert ControlDecisionReason.REDUCE_ONLY_MODE.value == "REDUCE_ONLY_MODE"
    assert ControlDecisionReason.EXECUTION_DISABLED.value == "EXECUTION_DISABLED"


def test_decision_reason_round_trip():
    assert ControlDecisionReason("SYMBOL_BLOCKED") is ControlDecisionReason.SYMBOL_BLOCKED
