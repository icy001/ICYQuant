"""
Tests for the risk decision model.
"""

from dataclasses import FrozenInstanceError

import pytest

from services.risk.decision.risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)


def test_status_enum_values():
    assert RiskDecisionStatus.APPROVED.value == "APPROVED"
    assert RiskDecisionStatus.REJECTED.value == "REJECTED"


def test_approved_decision():
    decision = RiskDecision(status=RiskDecisionStatus.APPROVED)

    assert decision.approved is True


def test_rejected_decision():
    decision = RiskDecision(status=RiskDecisionStatus.REJECTED)

    assert decision.approved is False


def test_rejection_carries_reason_and_policy():
    decision = RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        reason_code="POSITION_LIMIT_EXCEEDED",
        reason="projected position exceeds limit",
        policy_id="position_limit",
    )

    assert decision.reason_code == "POSITION_LIMIT_EXCEEDED"
    assert decision.reason == "projected position exceeds limit"
    assert decision.policy_id == "position_limit"


def test_decision_defaults():
    decision = RiskDecision(status=RiskDecisionStatus.APPROVED)

    assert decision.reason_code is None
    assert decision.reason is None
    assert decision.policy_id is None
    assert decision.correlation_id is None
    assert decision.causation_id is None
    assert decision.lineage_id is None


def test_decision_carries_identity_fields():
    decision = RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )

    assert decision.correlation_id == "corr-1"
    assert decision.causation_id == "event-1"
    assert decision.lineage_id == "lineage-1"


def test_decision_is_frozen():
    decision = RiskDecision(status=RiskDecisionStatus.APPROVED)

    with pytest.raises(FrozenInstanceError):
        decision.status = RiskDecisionStatus.REJECTED
