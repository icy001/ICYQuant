"""
Tests for Decision Guard — final sanity gate.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.decision_guard import DecisionGuard
from services.governance.decision_context import DecisionContext
from services.governance.decision_request import DecisionRequest, DecisionType


class TestDecisionGuard:

    @pytest.fixture
    def guard(self):
        return DecisionGuard(
            min_survival_score=40.0,
            min_liquidity_score=30.0,
            max_post_decision_risk_ratio=1.0,
        )

    # ------------------------------------------------------------------
    # Normal operation
    # ------------------------------------------------------------------

    def test_pass_in_normal_conditions(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=5_000_000,
            direction="INCREASE",
        )
        context = DecisionContext(
            survival_score=82.0,
            liquidity_score=80.0,
            risk_budget_total=10_000_000,
            post_decision_risk=0,
            available_capital=50_000_000,
        )
        result = guard.check(request, context)
        assert result["pass"] is True

    # ------------------------------------------------------------------
    # Survival score below floor
    # ------------------------------------------------------------------

    def test_block_when_survival_below_floor_and_risk_increasing(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=5_000_000,
            direction="INCREASE",
        )
        context = DecisionContext(
            survival_score=25.0,
            liquidity_score=80.0,
        )
        result = guard.check(request, context)
        assert result["pass"] is False
        assert "survival" in result["reason"].lower()

    def test_allow_risk_reduction_when_survival_low(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_DEALLOCATION,
            requested_amount=-5_000_000,
            direction="DECREASE",
        )
        context = DecisionContext(
            survival_score=25.0,
            liquidity_score=80.0,
        )
        result = guard.check(request, context)
        assert result["pass"] is True

    # ------------------------------------------------------------------
    # Liquidity below floor
    # ------------------------------------------------------------------

    def test_block_when_liquidity_below_floor(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            direction="INCREASE",
        )
        context = DecisionContext(
            survival_score=85.0,
            liquidity_score=15.0,
        )
        result = guard.check(request, context)
        assert result["pass"] is False

    # ------------------------------------------------------------------
    # Emergency mode
    # ------------------------------------------------------------------

    def test_block_risk_increasing_in_emergency(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            direction="INCREASE",
        )
        context = DecisionContext(
            survival_score=85.0,
            liquidity_score=80.0,
            emergency_mode=True,
        )
        result = guard.check(request, context)
        assert result["pass"] is False

    # ------------------------------------------------------------------
    # Post-decision risk ratio
    # ------------------------------------------------------------------

    def test_block_when_post_risk_exceeds_ratio(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            post_decision_risk=12_000_000,
            direction="INCREASE",
        )
        context = DecisionContext(
            survival_score=85.0,
            liquidity_score=80.0,
            risk_budget_total=10_000_000,
            available_capital=50_000_000,
        )
        result = guard.check(request, context)
        assert result["pass"] is False

    # ------------------------------------------------------------------
    # Negative available capital
    # ------------------------------------------------------------------

    def test_block_negative_available_capital(self, guard):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=100_000_000,
        )
        context = DecisionContext(
            survival_score=85.0,
            liquidity_score=80.0,
            available_capital=10_000_000,
        )
        result = guard.check(request, context)
        assert result["pass"] is False

    # ------------------------------------------------------------------
    # check_simple
    # ------------------------------------------------------------------

    def test_check_simple(self, guard):
        safe = DecisionContext(survival_score=85.0, liquidity_score=80.0)
        assert guard.check_simple(safe, is_risk_increasing=True) is True

        risky = DecisionContext(survival_score=25.0, liquidity_score=80.0)
        assert guard.check_simple(risky, is_risk_increasing=True) is False
        assert guard.check_simple(risky, is_risk_increasing=False) is True

        emergency = DecisionContext(survival_score=85.0, liquidity_score=80.0, emergency_mode=True)
        assert guard.check_simple(emergency, is_risk_increasing=True) is False
