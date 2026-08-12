"""Tests for the risk adapter (spec section 7)."""
from __future__ import annotations

from services.control_plane.admission.risk import (
    RiskDecision,
    RiskResult,
)


def test_risk_decision_values():
    assert RiskDecision.APPROVED.value == "APPROVED"
    assert RiskDecision.REJECTED.value == "REJECTED"
    assert RiskDecision.REDUCE_ONLY.value == "REDUCE_ONLY"


def test_risk_result_defaults():
    result = RiskResult(decision=RiskDecision.APPROVED)

    assert result.decision is RiskDecision.APPROVED
    assert result.reason == ""
    assert result.risk_score is None
    assert result.metadata is None


def test_risk_result_carries_reason_and_score():
    result = RiskResult(
        decision=RiskDecision.REJECTED,
        reason="leverage limit breached",
        risk_score=2.4,
        metadata={"limit": 2.0},
    )

    assert result.reason == "leverage limit breached"
    assert result.risk_score == 2.4
    assert result.metadata == {"limit": 2.0}


def test_risk_result_of_accepts_string():
    result = RiskResult.of("REJECTED")

    assert result.decision is RiskDecision.REJECTED


def test_risk_result_of_accepts_enum():
    result = RiskResult.of(RiskDecision.APPROVED)

    assert result.decision is RiskDecision.APPROVED


def test_risk_result_of_accepts_object_with_decision():
    class _EngineResult:
        decision = "REDUCE_ONLY"
        reason = "reduce only per policy"
        risk_score = 1.1
        metadata = {"mode": "reduce-only"}

    result = RiskResult.of(_EngineResult())

    assert result.decision is RiskDecision.REDUCE_ONLY
    assert result.reason == "reduce only per policy"
    assert result.risk_score == 1.1
