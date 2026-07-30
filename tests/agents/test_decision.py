"""Tests for Decision Engine - Unified AI Decision Maker."""

import pytest
from services.agents.decision import (
    DecisionEngine, DecisionInput, DecisionOutput, FinalDecision,
)


class TestDecisionEngine:
    """Decision Engine tests."""

    @pytest.fixture
    def engine(self):
        return DecisionEngine()

    # ── Decision Making ─────────────────────────────────────────

    def test_decide_with_all_inputs_bullish(self, engine):
        """Strong bullish signal with low risk should EXECUTE."""
        inputs = DecisionInput(
            market_signal={"symbol": "NVDA", "regime": "risk_on", "trend": "bullish"},
            trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.85, "size": 2.0},
            risk_assessment={"decision": "approved", "risk_score": 0.1, "warnings": []},
        )
        output = engine.decide(inputs)
        assert output.decision in (FinalDecision.EXECUTE, FinalDecision.EXECUTE_REDUCED)
        assert output.composite_score > 50

    def test_decide_high_risk_rejects(self, engine):
        """High risk should reject even with good signals."""
        inputs = DecisionInput(
            market_signal={"symbol": "NVDA", "regime": "risk_on", "trend": "bullish"},
            trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.9, "size": 5.0},
            risk_assessment={
                "decision": "rejected",
                "risk_score": 0.85,
                "warnings": ["Sector limit exceeded"],
                "violations": [{"rule_id": "SECTOR_EXPOSURE", "rule_type": "sector_exposure"}],
            },
        )
        output = engine.decide(inputs)
        assert output.decision in (FinalDecision.REJECTED, FinalDecision.SKIP, FinalDecision.HOLD)

    def test_decide_risk_off_hold(self, engine):
        """Risk-off market should hold."""
        inputs = DecisionInput(
            market_signal={"symbol": "SPY", "regime": "risk_off", "trend": "bearish"},
            trade_proposal={"symbol": "SPY", "action": "SELL", "confidence": 0.55, "size": 2.0},
            risk_assessment={"decision": "approved_with_warnings", "risk_score": 0.4, "warnings": []},
        )
        output = engine.decide(inputs)
        assert output.decision in (FinalDecision.HOLD, FinalDecision.SKIP, FinalDecision.REDUCE)

    def test_decide_no_inputs(self, engine):
        """No inputs should result in HOLD."""
        inputs = DecisionInput()
        output = engine.decide(inputs)
        assert output.decision in (FinalDecision.HOLD, FinalDecision.SKIP)

    # ── Scoring ─────────────────────────────────────────────────

    def test_market_signal_scoring_bullish(self, engine):
        score = engine._score_market_signal({"regime": "risk_on", "trend": "bullish"})
        assert score > 60

    def test_market_signal_scoring_bearish(self, engine):
        score = engine._score_market_signal({"regime": "risk_off", "trend": "bearish"})
        assert score < 50

    def test_risk_scoring_approved(self, engine):
        score = engine._score_risk_assessment({"decision": "approved", "risk_score": 0.1, "violations": []})
        assert score > 70

    def test_risk_scoring_blocked(self, engine):
        score = engine._score_risk_assessment({"decision": "blocked", "risk_score": 0.9, "violations": [{"r": 1}]})
        assert score < 30

    # ── Decision Output ─────────────────────────────────────────

    def test_output_has_required_fields(self, engine):
        inputs = DecisionInput(
            market_signal={"symbol": "NVDA", "regime": "neutral", "trend": "neutral"},
            trade_proposal={"symbol": "NVDA", "action": "HOLD", "confidence": 0.5, "size": 1.0},
        )
        output = engine.decide(inputs)

        assert output.decision_id is not None
        assert output.decision in FinalDecision
        assert output.composite_score >= 0
        assert output.confidence >= 0
        assert "market_signal" in output.scores
        assert "risk_assessment" in output.scores
        assert len(output.reasons) > 0

    def test_output_to_dict(self, engine):
        inputs = DecisionInput(
            market_signal={"symbol": "NVDA", "regime": "risk_on", "trend": "bullish"},
            trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.9, "size": 2.0},
            risk_assessment={"decision": "approved", "risk_score": 0.1, "warnings": []},
        )
        output = engine.decide(inputs)
        d = output.to_dict()
        assert isinstance(d, dict)
        assert "decision_id" in d
        assert "decision" in d
        assert "composite_score" in d

    # ── History ─────────────────────────────────────────────────

    def test_get_decisions(self, engine):
        engine.decide(DecisionInput(
            market_signal={"regime": "risk_on", "trend": "bullish"},
            trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.9, "size": 2.0},
        ))
        decisions = engine.get_decisions()
        assert len(decisions) > 0

    def test_get_decisions_filtered(self, engine):
        for _ in range(3):
            engine.decide(DecisionInput(
                market_signal={"regime": "risk_on", "trend": "bullish"},
                trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.9, "size": 2.0},
                risk_assessment={"decision": "approved", "risk_score": 0.1},
            ))

        executed = engine.get_decisions(decision=FinalDecision.EXECUTE)
        assert len(executed) > 0

    def test_get_summary(self, engine):
        engine.decide(DecisionInput(
            market_signal={"regime": "risk_on", "trend": "bullish"},
            trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.9, "size": 2.0},
        ))
        summary = engine.get_summary()
        assert summary["total"] > 0
        assert "by_type" in summary

    # ── Weights ─────────────────────────────────────────────────

    def test_default_weights(self, engine):
        total = sum(engine._weights.values())
        assert 0.99 <= total <= 1.01

    def test_update_weights(self, engine):
        engine.update_weights({"market_signal": 0.30, "risk_assessment": 0.40})
        assert engine._weights["market_signal"] == 0.30
        assert engine._weights["risk_assessment"] == 0.40

    # ── Composite Score ─────────────────────────────────────────

    def test_composite_score_range(self, engine):
        """Composite score should always be between 0 and 100."""
        test_cases = [
            DecisionInput(),
            DecisionInput(market_signal={"regime": "risk_on", "trend": "bullish"}),
            DecisionInput(market_signal={"regime": "crisis", "trend": "bearish"}),
            DecisionInput(
                market_signal={"regime": "risk_on", "trend": "bullish"},
                trade_proposal={"symbol": "NVDA", "action": "BUY", "confidence": 0.95, "size": 2.0},
                risk_assessment={"decision": "approved", "risk_score": 0.05},
            ),
            DecisionInput(
                market_signal={"regime": "crisis", "trend": "bearish"},
                trade_proposal={"symbol": "TSLA", "action": "SELL", "confidence": 0.3, "size": 10.0},
                risk_assessment={"decision": "blocked", "risk_score": 0.95, "violations": [{"r": 1}, {"r": 2}]},
            ),
        ]

        for inputs in test_cases:
            output = engine.decide(inputs)
            assert 0 <= output.composite_score <= 100, f"Score {output.composite_score} out of range"
