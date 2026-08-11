"""
Tests for Governance Engine — full pipeline: Request → Policy → Authority
→ Constraint → Approval → Decision → Audit.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.governance_engine import (
    GovernanceEngine, GovernanceEvaluation, GovernanceVerdict,
)
from services.governance.policy_engine import PolicyEngine
from services.governance.policy import Policy, PolicyScope
from services.governance.policy_rule import PolicyRule, RuleSeverity
from services.governance.authority_engine import AuthorityEngine, AuthorityLevel
from services.governance.approval_engine import ApprovalEngine
from services.governance.decision_guard import DecisionGuard
from services.governance.decision_audit import DecisionAudit
from services.governance.governance_event_store import GovernanceEventStore
from services.governance.capital_constraint import CapitalConstraint
from services.governance.risk_constraint import RiskConstraint
from services.governance.leverage_constraint import LeverageConstraint
from services.governance.liquidity_constraint import LiquidityConstraint
from services.governance.concentration_constraint import ConcentrationConstraint
from services.governance.autonomy_constraint import AutonomyConstraint
from services.governance.decision_governance import DecisionGovernance
from services.governance.decision_context import DecisionContext
from services.governance.decision_request import DecisionRequest, DecisionType


class TestGovernanceEngine:

    @pytest.fixture
    def engine(self):
        """Configured engine with all components."""
        policy = PolicyEngine()
        # Survival >= 70
        policy.register(Policy(
            policy_id="surv-001",
            rules=[PolicyRule(
                rule_id="r1", metric="survival_score",
                operator=">=", threshold=70.0,
                severity=RuleSeverity.BLOCKING,
            )],
        ))

        auth = AuthorityEngine()
        auth.grant("SYSTEM", "CAPITAL_ALLOCATION", True,
                   max_amount=50_000_000, autonomy_level=AuthorityLevel.AUTONOMOUS_ALLOCATION)

        approval = ApprovalEngine()

        guard = DecisionGuard(min_survival_score=40.0)

        auditor = DecisionAudit()

        events = GovernanceEventStore()

        engine = GovernanceEngine(
            policy_engine=policy,
            authority_engine=auth,
            approval_engine=approval,
            decision_guard=guard,
            auditor=auditor,
            event_store=events,
        )

        # Register constraints
        engine._decision_governance.register(CapitalConstraint(max_deployable=100_000_000))
        engine._decision_governance.register(RiskConstraint(max_risk_budget_utilization=1.0))
        engine._decision_governance.register(LeverageConstraint(max_leverage=3.0))
        engine._decision_governance.register(LiquidityConstraint(min_liquidity_score=60.0))
        engine._decision_governance.register(ConcentrationConstraint(
            max_strategy_weight=0.25, max_factor_weight=0.35
        ))
        engine._decision_governance.register(AutonomyConstraint())

        return engine

    def _healthy_context(self, **kwargs) -> DecisionContext:
        defaults = {
            "capital": 100_000_000,
            "deployed_capital": 60_000_000,
            "available_capital": 40_000_000,
            "survival_score": 85.0,
            "liquidity_score": 75.0,
            "risk_budget_total": 10_000_000,
            "risk_budget_used": 4_000_000,
            "current_leverage": 2.0,
            "actor_autonomy_level": 3,
            "strategy_id": "strategy_b",
            "strategy_weight": 0.18,
            "strategy_allocations": {"strategy_b": 0.18},
        }
        defaults.update(kwargs)
        return DecisionContext(**defaults)

    # ------------------------------------------------------------------
    # Full pipeline — ALLOW
    # ------------------------------------------------------------------

    def test_full_pipeline_allow(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            strategy_id="strategy_b",
            requested_amount=10_000_000,
            direction="INCREASE",
        )
        context = self._healthy_context()
        evaluation = engine.evaluate(request, context)

        assert evaluation.verdict == GovernanceVerdict.ALLOW
        assert evaluation.allow_execution is True

    # ------------------------------------------------------------------
    # Policy blocks
    # ------------------------------------------------------------------

    def test_policy_blocks_low_survival(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=5_000_000,
        )
        context = self._healthy_context(survival_score=50.0)
        evaluation = engine.evaluate(request, context)

        assert evaluation.verdict == GovernanceVerdict.BLOCKED
        assert "Policy breach" in evaluation.reason

    # ------------------------------------------------------------------
    # Authority denies
    # ------------------------------------------------------------------

    def test_authority_denies_unknown_actor(self, engine):
        request = DecisionRequest(
            actor="UNKNOWN",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
        )
        context = self._healthy_context()
        evaluation = engine.evaluate(request, context)

        # Policy passes, but authority denies
        assert evaluation.verdict in (GovernanceVerdict.BLOCKED, GovernanceVerdict.REJECT)
        assert "Authority" in evaluation.reason or "authority" in evaluation.reason.lower()

    # ------------------------------------------------------------------
    # Constraint blocks
    # ------------------------------------------------------------------

    def test_capital_constraint_blocks_over_deployment(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=50_000_000,
        )
        context = self._healthy_context(
            deployed_capital=80_000_000,
            available_capital=20_000_000,
        )
        evaluation = engine.evaluate(request, context)

        assert evaluation.verdict == GovernanceVerdict.BLOCKED
        assert any("capital" in r.reason.lower() for r in evaluation.constraint_results
                   if not r.passed)

    def test_risk_constraint_blocks_over_budget(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            additional_risk=7_000_000,
        )
        context = self._healthy_context(
            risk_budget_total=10_000_000,
            risk_budget_used=6_000_000,
        )
        evaluation = engine.evaluate(request, context)

        # Post-risk = 6 + 7 = 13 > 10 budget
        assert evaluation.verdict == GovernanceVerdict.BLOCKED

    def test_leverage_constraint_blocks(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            direction="INCREASE",
        )
        context = self._healthy_context(current_leverage=4.0)
        evaluation = engine.evaluate(request, context)

        assert evaluation.verdict == GovernanceVerdict.BLOCKED
        assert any("elverag" in r.reason.lower() for r in evaluation.constraint_results
                   if not r.passed)

    def test_liquidity_constraint_allows_risk_reduction(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_DEALLOCATION,
            direction="DECREASE",
        )
        context = self._healthy_context(liquidity_score=40.0)
        evaluation = engine.evaluate(request, context)

        # Risk-reducing should pass even with low liquidity
        assert evaluation.verdict == GovernanceVerdict.ALLOW

    def test_concentration_constraint_blocks(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            strategy_id="strategy_c",
            requested_amount=30_000_000,
        )
        context = self._healthy_context(
            strategy_id="strategy_c",
            strategy_weight=0.30,
            strategy_allocations={"strategy_c": 0.30},
        )
        evaluation = engine.evaluate(request, context)

        # New weight = (0.30 * 100M + 30M) / 100M = 0.60 > 0.25
        assert evaluation.verdict == GovernanceVerdict.BLOCKED

    def test_autonomy_constraint_blocks_low_level(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=50_000_000,
        )
        context = self._healthy_context(actor_autonomy_level=0)
        evaluation = engine.evaluate(request, context)

        assert evaluation.verdict == GovernanceVerdict.BLOCKED
        assert any("autonomy" in r.reason.lower() for r in evaluation.constraint_results
                   if not r.passed)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def test_audit_record_created_on_allow(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = self._healthy_context()
        evaluation = engine.evaluate(request, context)

        assert evaluation.audit_record is not None
        assert evaluation.audit_record.verdict == "ALLOW"
        assert evaluation.audit_record.actor == "SYSTEM"

    def test_audit_record_created_on_block(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=10_000_000,
        )
        context = self._healthy_context(survival_score=50.0)
        evaluation = engine.evaluate(request, context)

        assert evaluation.audit_record is not None
        assert evaluation.audit_record.verdict == "BLOCKED"

    def test_audit_query(self, engine):
        req = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
        )
        engine.evaluate(req, self._healthy_context())
        engine.evaluate(req, self._healthy_context(survival_score=50.0))

        stats = engine._auditor.stats()
        assert stats["total"] == 2

        records = engine._auditor.query(verdict="BLOCKED")
        assert len(records) == 1

    # ------------------------------------------------------------------
    # Override
    # ------------------------------------------------------------------

    def test_override_decision(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=5_000_000,
        )
        context = self._healthy_context(survival_score=50.0)  # Would be blocked
        evaluation = engine.override_decision(
            request, context,
            override_actor="ADMIN",
            override_reason="Emergency market intervention",
            new_verdict=GovernanceVerdict.ALLOW,
        )

        assert evaluation.verdict == GovernanceVerdict.ALLOW
        assert "OVERRIDE" in evaluation.reason
        assert evaluation.allow_execution is True

    # ------------------------------------------------------------------
    # Event store
    # ------------------------------------------------------------------

    def test_events_emitted(self, engine):
        request = DecisionRequest(
            actor="SYSTEM",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            requested_amount=5_000_000,
        )
        context = self._healthy_context()
        engine.evaluate(request, context)

        events = engine._event_store.get_recent()
        assert len(events) > 0

        # Should have at least: REQUESTED, POLICY_EVALUATED,
        # AUTHORITY_EVALUATED, CONSTRAINT_CHECKED, EXECUTED
        event_types = {e.event_type for e in events}
        assert len(event_types) >= 3
