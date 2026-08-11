"""
Tests for Approval Engine — covers No Approval, Approval Required,
Approved, Rejected, Expired.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.approval_engine import ApprovalEngine
from services.governance.approval_requirement import ApprovalRequirement, ApprovalLevel
from services.governance.approval_workflow import (
    ApprovalWorkflow, ApprovalWorkflowStep,
)
from services.governance.approval_result import ApprovalDecision
from services.governance.decision_context import DecisionContext
from services.governance.decision_request import DecisionRequest, DecisionType


class TestApprovalEngine:

    @pytest.fixture
    def engine(self):
        """Engine with default requirements only."""
        return ApprovalEngine()

    @pytest.fixture
    def risk_review_engine(self):
        """Engine with risk review workflow."""
        engine = ApprovalEngine()
        engine.register_workflow(ApprovalWorkflow.risk_review_workflow())
        return engine

    # ------------------------------------------------------------------
    # No approval required
    # ------------------------------------------------------------------

    def test_small_allocation_no_approval(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=3_000_000,  # Below 5M threshold
        )
        context = DecisionContext(survival_score=85.0)
        result = engine.evaluate(request, context)

        assert result["approved"] is True
        assert result["approval_required"] is False

    # ------------------------------------------------------------------
    # Approval required — medium allocation
    # ------------------------------------------------------------------

    def test_medium_allocation_requires_risk_review(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,  # Between 5M and 20M
        )
        context = DecisionContext(
            survival_score=85.0,
            risk_budget_total=20_000_000,
            risk_budget_available=15_000_000,
        )
        result = engine.evaluate(request, context)

        assert result["approval_required"] is True
        assert result["level"] == "RISK_REVIEW"

    def test_large_allocation_requires_institutional(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=25_000_000,  # Above 20M
        )
        context = DecisionContext(survival_score=85.0)
        result = engine.evaluate(request, context)

        assert result["approval_required"] is True
        assert result["level"] == "INSTITUTIONAL"

    # ------------------------------------------------------------------
    # Risk review workflow — survival check
    # ------------------------------------------------------------------

    def test_risk_review_rejects_low_survival(self, risk_review_engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = DecisionContext(
            survival_score=50.0,  # Below 70
            risk_budget_total=20_000_000,
            risk_budget_available=15_000_000,
        )
        result = risk_review_engine.evaluate(request, context)
        assert result["approved"] is False

    def test_risk_review_approves_healthy(self, risk_review_engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = DecisionContext(
            survival_score=85.0,
            risk_budget_total=20_000_000,
            risk_budget_available=15_000_000,
        )
        result = risk_review_engine.evaluate(request, context)
        assert result["approved"] is True

    # ------------------------------------------------------------------
    # Institutional workflow
    # ------------------------------------------------------------------

    def test_institutional_workflow(self, engine):
        engine.register_workflow(ApprovalWorkflow.institutional_workflow())

        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=25_000_000,
        )
        context = DecisionContext(
            stress_survival_score=85.0,
            strategy_capacity=30_000_000,
            current_concentration=0.20,
        )
        result = engine.evaluate(request, context)
        assert result["approved"] is True

    def test_institutional_rejects_low_stress_survival(self, engine):
        engine.register_workflow(ApprovalWorkflow.institutional_workflow())

        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=25_000_000,
        )
        context = DecisionContext(
            stress_survival_score=50.0,  # Below 70
        )
        result = engine.evaluate(request, context)
        assert result["approved"] is False

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_no_requested_amount_no_approval(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=None,
        )
        context = DecisionContext()
        result = engine.evaluate(request, context)
        # No amount matches no requirement → approved
        assert result["approval_required"] is False

    def test_override_decision_type_no_approval(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.POLICY_OVERRIDE,
        )
        context = DecisionContext()
        result = engine.evaluate(request, context)
        # POLICY_OVERRIDE has no default requirement → auto-approved
        assert result["approval_required"] is False
        assert result["approved"] is True

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def test_history_records(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=25_000_000,
        )
        context = DecisionContext()
        engine.evaluate(request, context)

        history = engine.get_history()
        assert len(history) == 1
        assert history[0].level == "INSTITUTIONAL"
