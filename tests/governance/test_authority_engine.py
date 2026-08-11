"""
Tests for Authority Engine — covers Authorized, Unauthorized, Amount Exceeded,
Scope Exceeded, Autonomy Level Exceeded.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.authority_engine import AuthorityEngine, AuthorityEvaluationResult
from services.governance.authority_policy import AuthorityLevel
from services.governance.decision_authority import DecisionAuthority
from services.governance.decision_context import DecisionContext
from services.governance.decision_request import DecisionRequest, DecisionType


class TestAuthorityEngine:

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    @pytest.fixture
    def engine(self):
        eng = AuthorityEngine()
        eng.setup_default_authorities()
        return eng

    # ------------------------------------------------------------------
    # Authorized tests
    # ------------------------------------------------------------------

    def test_system_authorized_for_capital_allocation(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = DecisionContext(actor_autonomy_level=3)
        result = engine.evaluate(request, context)
        assert result.authorized is True

    def test_risk_engine_authorized_for_emergency(self, engine):
        request = DecisionRequest(
            actor="RISK_ENGINE",
            decision_type=DecisionType.EMERGENCY_ACTION,
        )
        context = DecisionContext(actor_autonomy_level=4, emergency_mode=True)
        result = engine.evaluate(request, context)
        assert result.authorized is True

    # ------------------------------------------------------------------
    # Unauthorized tests
    # ------------------------------------------------------------------

    def test_unknown_actor_denied(self, engine):
        request = DecisionRequest(
            actor="UNKNOWN_ACTOR",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
        )
        context = DecisionContext(actor_autonomy_level=0)
        result = engine.evaluate(request, context)
        assert result.authorized is False

    def test_strategy_cannot_do_capital_allocation(self):
        engine = AuthorityEngine()
        # Strategy only gets ORDER_SUBMIT
        engine.grant("STRATEGY", "ORDER_SUBMIT", True,
                     max_amount=1_000_000, autonomy_level=AuthorityLevel.RECOMMENDATION)

        request = DecisionRequest(
            actor="STRATEGY",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
        )
        context = DecisionContext(actor_autonomy_level=1)
        result = engine.evaluate(request, context)
        assert result.authorized is False

    def test_explicit_deny(self, engine):
        engine.grant("BLOCKED_ACTOR", "CAPITAL_ALLOCATION", authorized=False)
        request = DecisionRequest(
            actor="BLOCKED_ACTOR",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
        )
        context = DecisionContext()
        result = engine.evaluate(request, context)
        assert result.authorized is False

    # ------------------------------------------------------------------
    # Amount exceeded
    # ------------------------------------------------------------------

    def test_amount_exceeds_max(self, engine):
        # SYSTEM max for CAPITAL_ALLOCATION is 50M
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=100_000_000,  # exceeds 50M
        )
        context = DecisionContext(actor_autonomy_level=3)
        result = engine.evaluate(request, context)
        assert result.authorized is False
        assert result.review_required is True

    def test_amount_within_limit(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=30_000_000,  # within 50M
        )
        context = DecisionContext(actor_autonomy_level=3)
        result = engine.evaluate(request, context)
        assert result.authorized is True

    # ------------------------------------------------------------------
    # Autonomy level tests
    # ------------------------------------------------------------------

    def test_autonomy_level_insufficient(self, engine):
        # SYSTEM needs level 3 for CAPITAL_ALLOCATION
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = DecisionContext(actor_autonomy_level=1)  # Only level 1
        result = engine.evaluate(request, context)
        assert result.authorized is False

    def test_autonomy_level_sufficient(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = DecisionContext(actor_autonomy_level=3)
        result = engine.evaluate(request, context)
        assert result.authorized is True

    # ------------------------------------------------------------------
    # Approval required
    # ------------------------------------------------------------------

    def test_approval_required_triggers_review(self, engine):
        # STRATEGY has approval_required=True for ORDER_SUBMIT
        request = DecisionRequest(
            actor="STRATEGY",
            decision_type=DecisionType.ORDER_SUBMIT,
            requested_amount=500_000,
        )
        context = DecisionContext(actor_autonomy_level=1)
        result = engine.evaluate(request, context)
        # Strategy has approval_required=True
        assert result.review_required is True

    # ------------------------------------------------------------------
    # Wildcard authority
    # ------------------------------------------------------------------

    def test_wildcard_authority(self, engine):
        engine.grant("ADMIN", "*", True)
        request = DecisionRequest(
            actor="ADMIN",
            decision_type=DecisionType.POLICY_OVERRIDE,
        )
        context = DecisionContext()
        result = engine.evaluate(request, context)
        assert result.authorized is True

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    def test_revoke_removes_authority(self, engine):
        engine.grant("TEMP_ACTOR", "CAPITAL_ALLOCATION", True)
        request = DecisionRequest(actor="TEMP_ACTOR", decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext()
        assert engine.evaluate(request, context).authorized is True

        engine.revoke("TEMP_ACTOR", "CAPITAL_ALLOCATION")
        assert engine.evaluate(request, context).authorized is False

    # ------------------------------------------------------------------
    # List authorities
    # ------------------------------------------------------------------

    def test_list_authorities(self, engine):
        engine.setup_default_authorities()
        all_auths = engine.list_authorities()
        assert len(all_auths) > 0

        system_auths = engine.list_authorities(actor="SYSTEM")
        assert len(system_auths) > 0
        assert all(a.actor == "SYSTEM" for a in system_auths)

    # ------------------------------------------------------------------
    # Risk exceeded
    # ------------------------------------------------------------------

    def test_risk_exceeds_max(self, engine):
        # SYSTEM risk limit for RISK_BUDGET_CHANGE is 2M
        engine.grant("SYSTEM", "RISK_BUDGET_CHANGE", True, max_risk=2_000_000,
                      autonomy_level=AuthorityLevel.AUTONOMOUS_ALLOCATION)
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.RISK_BUDGET_CHANGE,
            additional_risk=5_000_000,
        )
        context = DecisionContext(actor_autonomy_level=3)
        result = engine.evaluate(request, context)
        assert result.authorized is False
