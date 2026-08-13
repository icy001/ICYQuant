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


# ------------------------------------------------------------------
# Commit 28 Part 1.3 — Governance Approval Engine (Four-Eyes Control)
# ------------------------------------------------------------------


class TestGovernanceApprovalEngine:

    @pytest.fixture
    def engine(self):
        from services.governance.approval_engine import GovernanceApprovalEngine
        from services.governance.approval_rule import ApprovalRule

        return GovernanceApprovalEngine(
            rules=(
                ApprovalRule(
                    rule_id="RULE-RESUME-001",
                    resource="trading",
                    action="resume",
                    min_approvers=1,
                    required_roles=("INCIDENT_COMMANDER",),
                    approval_timeout_seconds=900,
                ),
            )
        )

    @pytest.fixture
    def pending_approval(self):
        from datetime import datetime, timedelta, timezone
        from services.governance.approval import Approval

        now = datetime.now(timezone.utc)
        return Approval(
            approval_id="APR-001",
            resource="trading",
            action="resume",
            requested_by="ops-001",
            incident_id="INC-001",
            requested_at=now,
            expires_at=now + timedelta(seconds=900),
        )

    def test_create_request_finds_rule(self, engine, pending_approval):
        result = engine.create_request(pending_approval)
        assert result is pending_approval
        assert engine.current_state("APR-001") == "PENDING"

    def test_create_request_missing_rule_raises(self, engine):
        from datetime import datetime, timedelta, timezone
        from services.governance.approval import Approval

        now = datetime.now(timezone.utc)
        unknown = Approval(
            approval_id="APR-999",
            resource="portfolio",
            action="liquidate",
            requested_by="ops-001",
            requested_at=now,
            expires_at=now + timedelta(seconds=900),
        )
        with pytest.raises(ValueError):
            engine.create_request(unknown)

    def test_register_rule(self, engine, pending_approval):
        from services.governance.approval_rule import ApprovalRule

        engine.register_rule(
            ApprovalRule(
                rule_id="RULE-PORTFOLIO-001",
                resource="portfolio",
                action="liquidate",
            )
        )
        assert engine.find_rule("portfolio", "liquidate") is not None

    def test_create_request_records_audit(self, engine, pending_approval):
        from services.governance.audit import ApprovalAuditEventType

        engine.create_request(pending_approval)
        events = engine.auditor.for_approval("APR-001")
        assert len(events) == 1
        assert events[0].event_type == ApprovalAuditEventType.APPROVAL_CREATED

    def test_engine_approve_and_consume_records_audit(self, engine, pending_approval):
        from datetime import datetime, timezone
        from services.governance.approval import ApprovalState
        from services.governance.audit import ApprovalAuditEventType

        engine.create_request(pending_approval)
        now = datetime.now(timezone.utc)
        approved = engine.approve(
            pending_approval,
            "commander-001",
            now,
            approver_roles=("INCIDENT_COMMANDER",),
        )
        assert approved.state == ApprovalState.APPROVED

        consumed = engine.consume(approved)
        assert consumed.state == ApprovalState.CONSUMED

        event_types = {
            event.event_type for event in engine.auditor.for_approval("APR-001")
        }
        assert ApprovalAuditEventType.APPROVAL_APPROVED in event_types
        assert ApprovalAuditEventType.APPROVAL_CONSUMED in event_types

    def test_authorize_execution_denied_decision_not_consumed(self, engine, pending_approval):
        from datetime import datetime, timezone
        from services.governance.approval import ApprovalState
        from services.governance.decision import (
            DecisionEffect,
            GovernanceDecision,
        )

        engine.create_request(pending_approval)
        now = datetime.now(timezone.utc)
        approved = engine.approve(
            pending_approval,
            "commander-001",
            now,
            approver_roles=("INCIDENT_COMMANDER",),
        )
        denied = GovernanceDecision(
            effect=DecisionEffect.DENY,
            reason="denied by POLICY-TRADING-RESUME-BLOCKED-001",
            policy_id="POLICY-TRADING-RESUME-BLOCKED-001",
        )

        result = engine.authorize_execution(approved, denied, now)

        assert result.effect == DecisionEffect.DENY
        assert engine.current_state("APR-001") == ApprovalState.APPROVED
