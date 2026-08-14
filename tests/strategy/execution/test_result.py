"""Tests for the intent result model."""

import dataclasses

import pytest

from services.strategy.execution.result import IntentResult


def test_accepted_intent_result() -> None:
    result = IntentResult(
        intent_id="INTENT-20260813-000001",
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        accepted=True,
        state="PENDING",
    )
    assert result.accepted is True
    assert result.state == "PENDING"
    assert result.reason is None


def test_rejected_intent_result() -> None:
    result = IntentResult(
        intent_id="",
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        accepted=False,
        state="REJECTED",
        reason="risk_blocked",
    )
    assert result.accepted is False
    assert result.state == "REJECTED"
    assert result.reason == "risk_blocked"


def test_intent_result_is_frozen() -> None:
    result = IntentResult(
        intent_id="INTENT-20260813-000001",
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        accepted=True,
        state="PENDING",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.accepted = False
