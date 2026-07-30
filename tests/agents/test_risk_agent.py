"""Tests for Risk Agent - AI Risk Controller."""

import pytest
from services.agents.agent_base import AgentStatus
from services.agents.risk_agent import RiskAgent, RiskDecision, RiskAssessment


class TestRiskAgent:
    """Risk Agent lifecycle and risk assessment tests."""

    @pytest.fixture
    def agent(self):
        return RiskAgent(name="test_risk_agent")

    # ── Lifecycle ───────────────────────────────────────────────

    def test_initialization(self, agent):
        assert agent.name == "test_risk_agent"
        assert agent.agent_type == "risk_agent"
        assert agent.status in (AgentStatus.INIT, AgentStatus.IDLE)

    def test_start_stop(self, agent):
        agent.start()
        assert agent.status in (AgentStatus.IDLE, AgentStatus.OBSERVING, AgentStatus.ACTING)
        agent.stop()
        assert agent.status == AgentStatus.STOPPED

    # ── Proposal Evaluation ─────────────────────────────────────

    def test_evaluate_approve_safe_trade(self, agent):
        agent.start()
        agent.update_risk_metrics({
            "current_drawdown_pct": 2.0,
            "daily_pnl_pct": 0.5,
            "var_95": 0.01,
            "leverage": 1.0,
            "trades_this_hour": 3,
        })

        assessment = agent.evaluate_proposal(
            proposal_id="prop-001",
            symbol="NVDA",
            action="BUY",
            size_pct=2.0,
            confidence=0.85,
        )

        assert assessment.decision in (
            RiskDecision.APPROVED, RiskDecision.APPROVED_WITH_WARNINGS,
        )
        assert assessment.approved_size > 0

    def test_evaluate_reject_low_confidence(self, agent):
        agent.start()
        assessment = agent.evaluate_proposal(
            proposal_id="prop-002",
            symbol="AAPL",
            action="BUY",
            size_pct=5.0,
            confidence=0.3,
        )

        assert assessment.decision in (
            RiskDecision.REJECTED, RiskDecision.BLOCKED, RiskDecision.SIZE_REDUCED,
        )

    def test_evaluate_block_high_drawdown(self, agent):
        agent.start()
        agent.update_risk_metrics({
            "current_drawdown_pct": 12.0,  # High drawdown
            "daily_pnl_pct": -2.5,
            "var_95": 0.04,
            "leverage": 1.3,
            "trades_this_hour": 5,
        })

        assessment = agent.evaluate_proposal(
            proposal_id="prop-003",
            symbol="TSLA",
            action="BUY",
            size_pct=8.0,
            confidence=0.7,
        )

        assert assessment.decision in (
            RiskDecision.REJECTED, RiskDecision.BLOCKED, RiskDecision.SIZE_REDUCED,
        )
        assert assessment.risk_score > 0.3

    def test_evaluate_large_position_warning(self, agent):
        agent.start()
        agent.update_position("NVDA", 8.0)  # Already at 8%

        assessment = agent.evaluate_proposal(
            proposal_id="prop-004",
            symbol="NVDA",
            action="BUY",
            size_pct=3.0,  # Would push to 11%
            confidence=0.75,
        )

        assert assessment.decision in (
            RiskDecision.SIZE_REDUCED, RiskDecision.REJECTED, RiskDecision.BLOCKED,
        )

    def test_evaluate_conservative_mode(self, agent):
        agent.start()
        agent.memory.set_working("risk_mode", "conservative")

        assessment = agent.evaluate_proposal(
            proposal_id="prop-005",
            symbol="META",
            action="BUY",
            size_pct=5.0,  # Large in conservative mode
            confidence=0.7,
        )

        assert assessment.decision in (
            RiskDecision.SIZE_REDUCED, RiskDecision.APPROVED_WITH_WARNINGS,
        )

    # ── Risk Metrics ────────────────────────────────────────────

    def test_update_risk_metrics(self, agent):
        metrics = {"var_95": 0.03, "leverage": 1.2}
        agent.update_risk_metrics(metrics)
        assert agent._risk_metrics["var_95"] == 0.03
        assert agent._risk_metrics["leverage"] == 1.2

    def test_update_sector_exposure(self, agent):
        agent.update_sector_exposure("technology", 35.0)
        assert agent._sector_exposures["technology"] == 35.0

    def test_update_position(self, agent):
        agent.update_position("NVDA", 5.0)
        assert agent._position_sizes["NVDA"] == 5.0

    # ── Risk Summary ────────────────────────────────────────────

    def test_get_risk_summary(self, agent):
        agent.start()
        summary = agent.get_risk_summary()
        assert "approvals" in summary
        assert "rejections" in summary
        assert "circuit_breaker" in summary
        assert "risk_mode" in summary

    def test_get_rejection_reasons(self, agent):
        agent.start()
        # Cause a rejection
        agent.evaluate_proposal("p1", "TEST", "BUY", 5.0, 0.1)
        reasons = agent.get_rejection_reasons()
        assert isinstance(reasons, list)

    def test_get_assessments_filtered(self, agent):
        agent.start()
        agent.evaluate_proposal("p1", "TEST", "BUY", 2.0, 0.85)
        approved = agent.get_assessments(decision=RiskDecision.APPROVED)
        assert isinstance(approved, list)

    # ── Message Handling ────────────────────────────────────────

    def test_on_trade_proposal(self, agent):
        agent.start()
        data = {
            "decision_id": "d-001",
            "symbol": "NVDA",
            "action": "BUY",
            "size": 2.0,
            "confidence": 0.8,
        }
        agent._on_trade_proposal(data)
        # Should have created an assessment
        assert len(agent._assessments) > 0

    def test_on_portfolio_state(self, agent):
        agent.start()
        data = {
            "risk_metrics": {"var_95": 0.02},
            "sector_exposures": {"tech": 25.0},
            "position_sizes": {"NVDA": 5.0},
        }
        agent._on_portfolio_state(data)
        assert agent._risk_metrics.get("var_95") == 0.02

    # ── Status Report ───────────────────────────────────────────

    def test_status_report(self, agent):
        agent.start()
        report = agent.get_status_report()
        assert "agent_name" in report
        assert "status" in report
        assert "circuit_breaker" in report
