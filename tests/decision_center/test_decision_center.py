"""Tests for AI Decision Intelligence Center."""

import pytest

from services.decision_center import (
    ComplianceResult,
    ComplianceStatus,
    ComplianceValidator,
    ConfidenceAggregator,
    ConflictDetectionEngine,
    ConflictReport,
    DecisionArbitrationEngine,
    DecisionCenterService,
    DecisionCollector,
    DecisionMemory,
    DecisionPackage,
    DecisionTimeline,
    FinalDecision,
    FinalDecisionGenerator,
    MultiAgentFusionEngine,
)


# ---------------------------------------------------------------------------
# Decision Package & Collector
# ---------------------------------------------------------------------------

class TestDecisionPackage:
    def test_create(self):
        d = DecisionPackage(source="macro", signal="BUY", confidence=0.95)
        assert d.source == "macro"
        assert d.signal == "BUY"
        assert d.confidence == 0.95
        assert d.payload is None

    def test_with_payload(self):
        d = DecisionPackage(source="risk", signal="HOLD", confidence=0.5, payload={"reason": "volatile"})
        assert d.payload["reason"] == "volatile"


class TestDecisionCollector:
    def test_collect(self):
        collector = DecisionCollector()
        pkg = collector.collect("macro", "BUY", 0.9)
        assert pkg.signal == "BUY"
        assert collector.package_count == 1

    def test_flush(self):
        collector = DecisionCollector()
        collector.collect("macro", "BUY", 0.9)
        pkgs = collector.flush()
        assert len(pkgs) == 1
        assert collector.package_count == 0

    def test_by_source(self):
        collector = DecisionCollector()
        collector.collect("macro", "BUY", 0.9)
        collector.collect("risk", "SELL", 0.8)
        assert len(collector.by_source("macro")) == 1
        assert len(collector.by_source("risk")) == 1

    def test_by_signal(self):
        collector = DecisionCollector()
        collector.collect("macro", "BUY", 0.9)
        collector.collect("sentiment", "BUY", 0.7)
        collector.collect("risk", "SELL", 0.8)
        assert len(collector.by_signal("BUY")) == 2
        assert len(collector.by_signal("SELL")) == 1


# ---------------------------------------------------------------------------
# Multi-Agent Fusion Engine
# ---------------------------------------------------------------------------

class TestMultiAgentFusion:
    def test_fuse_max_confidence(self):
        engine = MultiAgentFusionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.7),
            DecisionPackage("sentiment", "BUY", 0.95),
            DecisionPackage("risk", "SELL", 0.8),
        ]
        winner = engine.fuse(decisions)
        assert winner.signal == "BUY"
        assert winner.confidence == 0.95

    def test_fuse_empty(self):
        engine = MultiAgentFusionEngine()
        assert engine.fuse([]) is None

    def test_weighted_vote(self):
        engine = MultiAgentFusionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.6),
            DecisionPackage("risk", "SELL", 0.9),
            DecisionPackage("sentiment", "BUY", 0.8),
        ]
        # Give macro extra weight
        weights = {"macro": 3.0, "risk": 1.0, "sentiment": 1.0}
        result = engine.weighted_vote(decisions, weights)
        # BUY: 0.6*3 + 0.8*1 = 2.6, SELL: 0.9*1 = 0.9
        assert result == "BUY"

    def test_weighted_vote_empty(self):
        engine = MultiAgentFusionEngine()
        assert engine.weighted_vote([]) == "HOLD"

    def test_confidence_weighted_fuse(self):
        engine = MultiAgentFusionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.8),
            DecisionPackage("sentiment", "BUY", 0.6),
            DecisionPackage("risk", "SELL", 0.4),
        ]
        result = engine.confidence_weighted_fuse(decisions)
        assert result["BUY"] == pytest.approx(1.4)
        assert result["SELL"] == pytest.approx(0.4)

    def test_bayesian_fuse(self):
        engine = MultiAgentFusionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.8),
            DecisionPackage("sentiment", "BUY", 0.6),
            DecisionPackage("risk", "SELL", 0.4),
        ]
        result = engine.bayesian_fuse(decisions)
        assert "BUY" in result
        assert result["BUY"] > result["SELL"]

    def test_bayesian_fuse_empty(self):
        engine = MultiAgentFusionEngine()
        assert engine.bayesian_fuse([]) == {}


# ---------------------------------------------------------------------------
# Conflict Detection Engine
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_detect_conflict(self):
        engine = ConflictDetectionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("risk", "SELL", 0.8),
        ]
        assert engine.detect(decisions) is True

    def test_detect_no_conflict(self):
        engine = ConflictDetectionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("sentiment", "BUY", 0.7),
        ]
        assert engine.detect(decisions) is False

    def test_detect_empty(self):
        engine = ConflictDetectionEngine()
        assert engine.detect([]) is False

    def test_detect_single(self):
        engine = ConflictDetectionEngine()
        assert engine.detect([DecisionPackage("macro", "BUY", 0.9)]) is False

    def test_conflict_score_no_conflict(self):
        engine = ConflictDetectionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("sentiment", "BUY", 0.7),
        ]
        assert engine.conflict_score(decisions) == 0.0

    def test_conflict_score_max_conflict(self):
        engine = ConflictDetectionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 1.0),
            DecisionPackage("risk", "SELL", 1.0),
        ]
        score = engine.conflict_score(decisions)
        assert score > 0.5  # Strong conflict

    def test_conflict_score_single(self):
        engine = ConflictDetectionEngine()
        assert engine.conflict_score([DecisionPackage("macro", "BUY", 0.9)]) == 0.0

    def test_analyze_full(self):
        engine = ConflictDetectionEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("sentiment", "BUY", 0.7),
            DecisionPackage("risk", "SELL", 0.6),
        ]
        report = engine.analyze(decisions)
        assert report.has_conflict is True
        assert report.unique_signals == 2
        assert report.conflict_score > 0
        assert report.details["signal_breakdown"]["BUY"] == 2
        assert report.details["signal_breakdown"]["SELL"] == 1


# ---------------------------------------------------------------------------
# Confidence Aggregator
# ---------------------------------------------------------------------------

class TestConfidenceAggregator:
    def test_aggregate_average(self):
        agg = ConfidenceAggregator()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("sentiment", "BUY", 0.7),
            DecisionPackage("risk", "SELL", 0.8),
        ]
        assert agg.aggregate(decisions) == pytest.approx(0.8)

    def test_aggregate_empty(self):
        agg = ConfidenceAggregator()
        assert agg.aggregate([]) == 0.0

    def test_weighted_aggregate(self):
        agg = ConfidenceAggregator()
        decisions = [
            DecisionPackage("macro", "BUY", 0.9),
            DecisionPackage("risk", "SELL", 0.5),
        ]
        weights = {"macro": 2.0, "risk": 1.0}
        result = agg.weighted_aggregate(decisions, weights)
        # (0.9*2 + 0.5*1) / 3 = 2.3/3 ≈ 0.7667
        assert result == pytest.approx(2.3 / 3.0)

    def test_harmonic_mean(self):
        agg = ConfidenceAggregator()
        decisions = [
            DecisionPackage("a", "BUY", 1.0),
            DecisionPackage("b", "BUY", 0.5),
        ]
        # 2 / (1/1 + 1/0.5) = 2 / (1 + 2) = 2/3 ≈ 0.6667
        assert agg.harmonic_mean(decisions) == pytest.approx(2.0 / 3.0)

    def test_aggregate_stats(self):
        agg = ConfidenceAggregator()
        decisions = [
            DecisionPackage("a", "BUY", 0.9),
            DecisionPackage("b", "BUY", 0.7),
            DecisionPackage("c", "BUY", 0.5),
        ]
        stats = agg.aggregate_stats(decisions)
        assert stats["mean"] == pytest.approx(0.7)
        assert stats["min"] == 0.5
        assert stats["max"] == 0.9
        assert stats["count"] == 3


# ---------------------------------------------------------------------------
# Decision Arbitration Engine
# ---------------------------------------------------------------------------

class TestDecisionArbitration:
    def test_select_by_priority(self):
        engine = DecisionArbitrationEngine()
        decisions = [
            DecisionPackage("sentiment", "BUY", 0.9),
            DecisionPackage("risk", "SELL", 0.8),
            DecisionPackage("macro", "HOLD", 0.7),
        ]
        winner = engine.select(decisions)
        # risk > macro > sentiment in default priority
        assert winner.source == "risk"

    def test_select_empty(self):
        engine = DecisionArbitrationEngine()
        assert engine.select([]) is None

    def test_select_top_k(self):
        engine = DecisionArbitrationEngine()
        decisions = [
            DecisionPackage("sentiment", "BUY", 0.9),
            DecisionPackage("execution", "SELL", 0.8),
            DecisionPackage("macro", "HOLD", 0.7),
            DecisionPackage("risk", "BUY", 0.6),
        ]
        top3 = engine.select_top_k(decisions, k=3)
        assert len(top3) == 3
        assert top3[0].source == "risk"

    def test_arbitrate_with_conflict(self):
        engine = DecisionArbitrationEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.8),
            DecisionPackage("risk", "SELL", 0.9),
        ]
        result = engine.arbitrate(decisions)
        assert result["winner"].signal == "SELL"  # risk wins
        assert result["conflict_report"].has_conflict is True
        assert "Conflict" in result["rationale"]

    def test_arbitrate_no_conflict(self):
        engine = DecisionArbitrationEngine()
        decisions = [
            DecisionPackage("macro", "BUY", 0.8),
            DecisionPackage("sentiment", "BUY", 0.6),
        ]
        result = engine.arbitrate(decisions)
        assert result["winner"].signal == "BUY"
        assert result["conflict_report"].has_conflict is False

    def test_arbitrate_empty(self):
        engine = DecisionArbitrationEngine()
        result = engine.arbitrate([])
        assert result["winner"] is None

    def test_set_priorities(self):
        engine = DecisionArbitrationEngine()
        engine.set_priorities(["sentiment", "macro", "risk"])
        decisions = [
            DecisionPackage("risk", "SELL", 0.9),
            DecisionPackage("sentiment", "BUY", 0.8),
        ]
        winner = engine.select(decisions)
        assert winner.source == "sentiment"  # now highest priority


# ---------------------------------------------------------------------------
# Compliance Validator
# ---------------------------------------------------------------------------

class TestComplianceValidator:
    def test_validate_approved(self):
        cv = ComplianceValidator()
        assert cv.validate(True) is True
        assert cv.validate(False) is False

    def test_check_risk_limit_pass(self):
        cv = ComplianceValidator()
        result = cv.check_risk_limit(exposure=0.5, max_exposure=1.0)
        assert result.status == ComplianceStatus.PASS

    def test_check_risk_limit_fail(self):
        cv = ComplianceValidator()
        result = cv.check_risk_limit(exposure=1.5, max_exposure=1.0)
        assert result.status == ComplianceStatus.FAIL

    def test_check_trading_rules(self):
        cv = ComplianceValidator()
        result = cv.check_trading_rules("BUY", ["BUY", "SELL", "HOLD"])
        assert result.status == ComplianceStatus.PASS
        result = cv.check_trading_rules("STRONG_SELL", ["BUY", "SELL"])
        assert result.status == ComplianceStatus.FAIL

    def test_check_blacklist(self):
        cv = ComplianceValidator()
        result = cv.check_blacklist("NVDA", ["TSLA", "AAPL"])
        assert result.status == ComplianceStatus.PASS
        result = cv.check_blacklist("TSLA", ["TSLA", "AAPL"])
        assert result.status == ComplianceStatus.FAIL

    def test_check_exposure(self):
        cv = ComplianceValidator()
        result = cv.check_exposure(0.3, 0.5, "NVDA")
        assert result.status == ComplianceStatus.PASS
        result = cv.check_exposure(0.8, 0.5, "NVDA")
        assert result.status == ComplianceStatus.FAIL

    def test_validate_all_pass(self):
        cv = ComplianceValidator()
        results = [
            cv.check_risk_limit(0.3, 1.0),
            cv.check_trading_rules("BUY", ["BUY", "SELL"]),
            cv.check_blacklist("NVDA", ["TSLA"]),
        ]
        aggregated = cv.validate_all(results)
        assert aggregated.status == ComplianceStatus.PASS

    def test_validate_all_fail(self):
        cv = ComplianceValidator()
        results = [
            cv.check_risk_limit(0.3, 1.0),
            cv.check_risk_limit(1.5, 1.0),  # fails
        ]
        aggregated = cv.validate_all(results)
        assert aggregated.status == ComplianceStatus.FAIL


# ---------------------------------------------------------------------------
# Final Decision Generator
# ---------------------------------------------------------------------------

class TestFinalDecisionGenerator:
    def test_build(self):
        gen = FinalDecisionGenerator()
        d = DecisionPackage("macro", "BUY", 0.95)
        result = gen.build(d)
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.95

    def test_build_full(self):
        gen = FinalDecisionGenerator()
        d = DecisionPackage("macro", "BUY", 0.95)
        fd = gen.build_full(
            d,
            reason="All agents agree",
            risk_level="LOW",
            execution_plan={"quantity": 100},
            conflict_score=0.0,
            arbitration_method="consensus",
        )
        assert fd.signal == "BUY"
        assert fd.confidence == 0.95
        assert fd.reason == "All agents agree"
        assert fd.risk_level == "LOW"
        assert fd.execution_plan["quantity"] == 100
        assert fd.conflict_score == 0.0
        assert fd.arbitration_method == "consensus"

    def test_to_dict(self):
        gen = FinalDecisionGenerator()
        d = DecisionPackage("macro", "BUY", 0.95)
        fd = gen.build_full(d, reason="test")
        result = gen.to_dict(fd)
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.95
        assert result["reason"] == "test"
        assert "timestamp" in result


# ---------------------------------------------------------------------------
# Decision Timeline
# ---------------------------------------------------------------------------

class TestDecisionTimeline:
    def test_append(self):
        timeline = DecisionTimeline()
        timeline.append({"signal": "BUY", "confidence": 0.9})
        assert timeline.event_count == 1

    def test_record(self):
        timeline = DecisionTimeline()
        timeline.record("BUY", 0.9, reason="strong momentum", model_version="2.0.0")
        event = timeline.events[0]
        assert event["signal"] == "BUY"
        assert event["confidence"] == 0.9
        assert event["model_version"] == "2.0.0"
        assert "timestamp" in event

    def test_query_by_signal(self):
        timeline = DecisionTimeline()
        timeline.record("BUY", 0.9)
        timeline.record("SELL", 0.7)
        timeline.record("BUY", 0.8)
        assert len(timeline.query_by_signal("BUY")) == 2

    def test_query_recent(self):
        timeline = DecisionTimeline()
        for i in range(5):
            timeline.record(f"S{i}", 0.5 + i * 0.1)
        recent = timeline.query_recent(n=3)
        assert len(recent) == 3

    def test_confidence_history(self):
        timeline = DecisionTimeline()
        timeline.record("BUY", 0.9)
        timeline.record("SELL", 0.7)
        timeline.record("BUY", 0.8)
        assert timeline.confidence_history() == [0.9, 0.7, 0.8]

    def test_clear(self):
        timeline = DecisionTimeline()
        timeline.record("BUY", 0.9)
        timeline.clear()
        assert timeline.event_count == 0


# ---------------------------------------------------------------------------
# Decision Memory
# ---------------------------------------------------------------------------

class TestDecisionMemory:
    def test_save(self):
        mem = DecisionMemory()
        mem.save({"signal": "BUY", "confidence": 0.9})
        assert mem.record_count == 1

    def test_save_with_outcome(self):
        mem = DecisionMemory()
        mem.save_with_outcome("BUY", 0.9, conflict_score=0.2, outcome="WIN", pnl=150.0)
        record = mem.history[0]
        assert record["signal"] == "BUY"
        assert record["outcome"] == "WIN"
        assert record["pnl"] == 150.0

    def test_query_by_outcome(self):
        mem = DecisionMemory()
        mem.save_with_outcome("BUY", 0.9, outcome="WIN")
        mem.save_with_outcome("SELL", 0.7, outcome="LOSS")
        mem.save_with_outcome("BUY", 0.8, outcome="WIN")
        assert len(mem.query_by_outcome("WIN")) == 2
        assert len(mem.query_by_outcome("LOSS")) == 1

    def test_query_high_confidence(self):
        mem = DecisionMemory()
        mem.save_with_outcome("BUY", 0.9)
        mem.save_with_outcome("SELL", 0.5)
        mem.save_with_outcome("BUY", 0.85)
        assert len(mem.query_high_confidence(0.80)) == 2

    def test_query_high_conflict(self):
        mem = DecisionMemory()
        mem.save_with_outcome("BUY", 0.9, conflict_score=0.8)
        mem.save_with_outcome("SELL", 0.7, conflict_score=0.2)
        assert len(mem.query_high_conflict(0.50)) == 1

    def test_win_rate(self):
        mem = DecisionMemory()
        mem.save_with_outcome("BUY", 0.9, outcome="WIN")
        mem.save_with_outcome("SELL", 0.7, outcome="WIN")
        mem.save_with_outcome("BUY", 0.8, outcome="LOSS")
        assert mem.win_rate() == pytest.approx(2.0 / 3.0)

    def test_win_rate_no_outcomes(self):
        mem = DecisionMemory()
        mem.save({"signal": "BUY"})
        assert mem.win_rate() is None

    def test_clear(self):
        mem = DecisionMemory()
        mem.save({"signal": "BUY"})
        mem.clear()
        assert mem.record_count == 0


# ---------------------------------------------------------------------------
# Decision Center Service (integration)
# ---------------------------------------------------------------------------

class TestDecisionCenterService:
    def test_decide_simple(self):
        decision = DecisionPackage(source="macro", signal="BUY", confidence=0.95)
        service = DecisionCenterService(
            MultiAgentFusionEngine(),
            FinalDecisionGenerator(),
        )
        result = service.decide([decision])
        assert result["signal"] == "BUY"

    def test_decide_full_pipeline(self):
        service = DecisionCenterService(
            MultiAgentFusionEngine(),
            FinalDecisionGenerator(),
        )
        decisions = [
            DecisionPackage("macro", "BUY", 0.85),
            DecisionPackage("sentiment", "BUY", 0.75),
            DecisionPackage("risk", "SELL", 0.60),
            DecisionPackage("execution", "BUY", 0.70),
        ]
        report = service.decide_full(
            decisions,
            risk_level="LOW",
            execution_plan={"quantity": 500},
        )

        assert "final_decision" in report
        assert report["final_decision"]["signal"] in ("BUY", "SELL")
        assert "fusion" in report
        assert "conflict" in report
        assert report["conflict"]["has_conflict"] is True
        assert "confidence" in report
        assert "compliance" in report
        assert "arbitration" in report

        # Timeline and memory should have recorded
        assert service.timeline.event_count == 1
        assert service.memory.record_count == 1

    def test_decide_full_no_conflict(self):
        service = DecisionCenterService(
            MultiAgentFusionEngine(),
            FinalDecisionGenerator(),
        )
        decisions = [
            DecisionPackage("macro", "BUY", 0.85),
            DecisionPackage("sentiment", "BUY", 0.75),
            DecisionPackage("execution", "BUY", 0.70),
        ]
        report = service.decide_full(decisions)
        assert report["conflict"]["has_conflict"] is False
        assert report["arbitration"]["method"] == "consensus"

    def test_decide_full_empty(self):
        service = DecisionCenterService(
            MultiAgentFusionEngine(),
            FinalDecisionGenerator(),
        )
        report = service.decide_full([])
        assert report["final_decision"]["signal"] == "HOLD"
        assert report["final_decision"]["confidence"] == 0.0

    def test_decide_full_compliance_fail(self):
        service = DecisionCenterService(
            MultiAgentFusionEngine(),
            FinalDecisionGenerator(),
        )
        decisions = [DecisionPackage("macro", "BUY", 0.85)]
        report = service.decide_full(decisions, compliance_approved=False)
        assert report["compliance"]["approved"] is False


# ---------------------------------------------------------------------------
# Original minimal test from spec
# ---------------------------------------------------------------------------

def test_decision_center():
    decision = DecisionPackage(source="macro", signal="BUY", confidence=0.95)
    service = DecisionCenterService(
        MultiAgentFusionEngine(),
        FinalDecisionGenerator(),
    )
    result = service.decide([decision])
    assert result["signal"] == "BUY"
