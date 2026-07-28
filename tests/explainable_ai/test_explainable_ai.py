"""Tests for AI Explainable Intelligence Engine."""

import pytest

from services.explainable_ai import (
    ConfidenceAnalyzer,
    ConfidenceLevel,
    DecisionCollector,
    DecisionEvent,
    DecisionPathEngine,
    ExplainableAIService,
    ExplainableMemory,
    FeatureImportanceAnalyzer,
    HumanExplanationGenerator,
    ModelAuditEngine,
    RuleValidationEngine,
    SignalAttributionEngine,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Decision Collector
# ---------------------------------------------------------------------------

class TestDecisionCollector:
    def test_collect_event(self):
        collector = DecisionCollector()
        event = collector.collect("momentum_strategy", "BUY", 0.94, symbol="NVDA")
        assert event.strategy == "momentum_strategy"
        assert event.signal == "BUY"
        assert event.confidence == 0.94
        assert event.symbol == "NVDA"
        assert collector.event_count == 1

    def test_collect_multiple(self):
        collector = DecisionCollector()
        collector.collect("s1", "BUY", 0.9)
        collector.collect("s2", "SELL", 0.7)
        collector.collect("s3", "HOLD", 0.5)
        assert collector.event_count == 3

    def test_flush(self):
        collector = DecisionCollector()
        collector.collect("s1", "BUY", 0.9)
        events = collector.flush()
        assert len(events) == 1
        assert collector.event_count == 0

    def test_event_metadata(self):
        collector = DecisionCollector()
        event = collector.collect("s1", "BUY", 0.9, metadata={"alpha": 0.5})
        assert event.metadata["alpha"] == 0.5

    def test_event_dataclass_defaults(self):
        event = DecisionEvent(strategy="test", signal="BUY", confidence=0.8)
        assert event.symbol is None
        assert event.source == "unknown"
        assert event.metadata == {}


# ---------------------------------------------------------------------------
# Signal Attribution Engine
# ---------------------------------------------------------------------------

class TestSignalAttribution:
    def test_analyze_normalization(self):
        engine = SignalAttributionEngine()
        result = engine.analyze({"price": 40, "macro": 25, "sentiment": 15, "flow": 20})
        assert sum(result.values()) == pytest.approx(1.0)
        assert result["price"] == pytest.approx(0.4, rel=0.01)
        assert result["macro"] == pytest.approx(0.25, rel=0.01)

    def test_analyze_empty(self):
        engine = SignalAttributionEngine()
        assert engine.analyze({}) == {}

    def test_analyze_zero_total(self):
        engine = SignalAttributionEngine()
        result = engine.analyze({"a": 0.0, "b": 0.0})
        assert result == {"a": 0.0, "b": 0.0}

    def test_top_contributors(self):
        engine = SignalAttributionEngine()
        scores = {"a": 10, "b": 30, "c": 20, "d": 40}
        top = engine.top_contributors(scores, n=2)
        assert len(top) == 2
        assert list(top.keys()) == ["d", "b"]


# ---------------------------------------------------------------------------
# Feature Importance Analyzer
# ---------------------------------------------------------------------------

class TestFeatureImportance:
    def test_rank_descending(self):
        analyzer = FeatureImportanceAnalyzer()
        features = {"liquidity": 0.34, "momentum": 0.26, "volatility": 0.18}
        ranked = analyzer.rank(features)
        assert ranked[0][0] == "liquidity"
        assert ranked[1][0] == "momentum"
        assert ranked[2][0] == "volatility"

    def test_rank_empty(self):
        analyzer = FeatureImportanceAnalyzer()
        assert analyzer.rank({}) == []

    def test_top_features(self):
        analyzer = FeatureImportanceAnalyzer()
        features = {"a": 0.5, "b": 0.3, "c": 0.2}
        top = analyzer.top_features(features, n=2)
        assert len(top) == 2
        assert top[0] == ("a", 0.5)

    def test_cumulative_importance(self):
        analyzer = FeatureImportanceAnalyzer()
        features = {"a": 50, "b": 30, "c": 15, "d": 5}
        result = analyzer.cumulative_importance(features, threshold=0.80)
        assert len(result) == 2  # a(50) + b(30) = 80/100
        assert result[0][0] == "a"

    def test_cumulative_empty(self):
        analyzer = FeatureImportanceAnalyzer()
        assert analyzer.cumulative_importance({}) == []


# ---------------------------------------------------------------------------
# Decision Path Engine
# ---------------------------------------------------------------------------

class TestDecisionPath:
    def test_build_path(self):
        engine = DecisionPathEngine()
        path = engine.build(["Fed Rate Cut", "Liquidity Improve", "NVDA Momentum", "BUY"])
        assert path == "Fed Rate Cut -> Liquidity Improve -> NVDA Momentum -> BUY"

    def test_build_single_node(self):
        engine = DecisionPathEngine()
        path = engine.build(["BUY"])
        assert path == "BUY"

    def test_build_with_weights(self):
        engine = DecisionPathEngine()
        nodes = [{"name": "Macro", "weight": 0.8}, {"name": "Flow", "weight": 0.6}]
        result = engine.build_with_weights(nodes)
        assert "Macro(0.80)" in result["path"]
        assert "Flow(0.60)" in result["path"]
        assert result["total_weight"] == pytest.approx(1.4)

    def test_build_with_weights_empty(self):
        engine = DecisionPathEngine()
        result = engine.build_with_weights([])
        assert result == {"path": "", "total_weight": 0.0}

    def test_validate_path_ok(self):
        engine = DecisionPathEngine()
        assert engine.validate_path(["a", "b", "c"]) is True

    def test_validate_path_too_short(self):
        engine = DecisionPathEngine()
        assert engine.validate_path(["a"]) is False

    def test_validate_path_expected_length(self):
        engine = DecisionPathEngine()
        assert engine.validate_path(["a", "b", "c"], expected_length=3) is True
        assert engine.validate_path(["a", "b"], expected_length=3) is False


# ---------------------------------------------------------------------------
# Confidence Analyzer
# ---------------------------------------------------------------------------

class TestConfidenceAnalyzer:
    def test_score_percentage(self):
        analyzer = ConfidenceAnalyzer()
        assert analyzer.score(0.94) == 94.0
        assert analyzer.score(0.5) == 50.0
        assert analyzer.score(0.0) == 0.0

    def test_score_clamping(self):
        analyzer = ConfidenceAnalyzer()
        assert analyzer.score(1.5) == 100.0
        assert analyzer.score(-0.1) == 0.0

    def test_level_very_high(self):
        analyzer = ConfidenceAnalyzer()
        assert analyzer.level(0.94) == ConfidenceLevel.VERY_HIGH

    def test_level_moderate(self):
        analyzer = ConfidenceAnalyzer()
        assert analyzer.level(0.45) == ConfidenceLevel.MODERATE

    def test_is_actionable(self):
        analyzer = ConfidenceAnalyzer()
        assert analyzer.is_actionable(0.94) is True
        assert analyzer.is_actionable(0.3) is False
        assert analyzer.is_actionable(0.7, min_confidence=70.0) is True
        assert analyzer.is_actionable(0.7, min_confidence=71.0) is False

    def test_analyze_full(self):
        analyzer = ConfidenceAnalyzer()
        result = analyzer.analyze(0.85)
        assert result["confidence_score"] == 85.0
        assert result["confidence_level"] == "very_high"
        assert result["actionable"] is True


# ---------------------------------------------------------------------------
# Rule Validation Engine
# ---------------------------------------------------------------------------

class TestRuleValidation:
    def test_validate_both_pass(self):
        engine = RuleValidationEngine()
        assert engine.validate(True, True) is True

    def test_validate_risk_fail(self):
        engine = RuleValidationEngine()
        assert engine.validate(False, True) is False

    def test_validate_position_fail(self):
        engine = RuleValidationEngine()
        assert engine.validate(True, False) is False

    def test_validate_all_pass(self):
        engine = RuleValidationEngine()
        result = engine.validate_all({"risk": True, "position": True})
        assert result.status == ValidationStatus.PASS

    def test_validate_all_fail(self):
        engine = RuleValidationEngine()
        result = engine.validate_all({"risk": True, "position": False})
        assert result.status == ValidationStatus.FAIL
        assert "position" in result.message

    def test_validate_all_empty(self):
        engine = RuleValidationEngine()
        result = engine.validate_all({})
        assert result.status == ValidationStatus.PASS

    def test_add_rule_and_summary(self):
        engine = RuleValidationEngine()
        engine.add_rule("blacklist", "Check blacklist")
        engine.check_rule("blacklist", True)
        engine.check_rule("risk", False, "Risk too high")
        summary = engine.summary()
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["all_pass"] is False


# ---------------------------------------------------------------------------
# Model Audit Engine
# ---------------------------------------------------------------------------

class TestModelAudit:
    def test_record_basic(self):
        engine = ModelAuditEngine()
        record = engine.record("momentum_model")
        assert record.model == "momentum_model"
        assert record.status == "RECORDED"
        assert record.model_version == "1.0.0"

    def test_record_with_versions(self):
        engine = ModelAuditEngine()
        record = engine.record("llm_strategy", model_version="2.1.0", prompt_version="3.0.0")
        assert record.model_version == "2.1.0"
        assert record.prompt_version == "3.0.0"

    def test_query_by_model(self):
        engine = ModelAuditEngine()
        engine.record("model_a")
        engine.record("model_b")
        engine.record("model_a")
        results = engine.query_by_model("model_a")
        assert len(results) == 2

    def test_record_count(self):
        engine = ModelAuditEngine()
        assert engine.record_count == 0
        engine.record("m1")
        engine.record("m2")
        assert engine.record_count == 2


# ---------------------------------------------------------------------------
# Human Explanation Generator
# ---------------------------------------------------------------------------

class TestHumanExplanation:
    def test_generate_basic(self):
        gen = HumanExplanationGenerator()
        result = gen.generate("BUY")
        assert "BUY" in result

    def test_generate_detailed(self):
        gen = HumanExplanationGenerator()
        result = gen.generate_detailed(
            signal="BUY",
            symbol="NVDA",
            attribution={"price_model": 0.4, "macro": 0.3, "sentiment": 0.3},
            confidence=94.0,
            reasons=["资金持续流入 AI 板块", "市场风险等级较低"],
            risk_level="Low",
        )
        assert "NVDA" in result
        assert "price_model" in result
        assert "40%" in result
        assert "94%" in result
        assert "Low" in result

    def test_generate_brief(self):
        gen = HumanExplanationGenerator()
        result = gen.generate_brief("BUY", 94.0, "strong momentum")
        assert "BUY" in result
        assert "94%" in result
        assert "strong momentum" in result


# ---------------------------------------------------------------------------
# Explainable Memory
# ---------------------------------------------------------------------------

class TestExplainableMemory:
    def test_save_and_query(self):
        mem = ExplainableMemory()
        mem.save({"strategy": "s1", "signal": "BUY", "confidence": 94})
        mem.save({"strategy": "s2", "signal": "SELL", "confidence": 70})
        assert mem.record_count == 2
        assert len(mem.query_by_strategy("s1")) == 1
        assert len(mem.query_by_signal("BUY")) == 1

    def test_query_recent(self):
        mem = ExplainableMemory()
        for i in range(5):
            mem.save({"strategy": f"s{i}", "signal": "BUY"})
        recent = mem.query_recent(n=3)
        assert len(recent) == 3

    def test_clear(self):
        mem = ExplainableMemory()
        mem.save({"strategy": "s1"})
        mem.clear()
        assert mem.record_count == 0

    def test_timestamp_auto_added(self):
        mem = ExplainableMemory()
        record = mem.save({"strategy": "s1"})
        assert "timestamp" in record


# ---------------------------------------------------------------------------
# Explainable AI Service (integration)
# ---------------------------------------------------------------------------

class TestExplainableAIService:
    def test_explain_basic(self):
        service = ExplainableAIService(HumanExplanationGenerator())
        result = service.explain("BUY")
        assert "BUY" in result

    def test_explain_full_pipeline(self):
        service = ExplainableAIService(HumanExplanationGenerator())
        report = service.explain_full(
            signal="BUY",
            symbol="NVDA",
            probability=0.94,
            scores={"price_model": 40, "macro": 25, "sentiment": 15, "flow": 20},
            features={"liquidity": 0.34, "momentum": 0.26, "volatility": 0.18},
            path_nodes=["Fed Cut", "Liquidity Up", "NVDA Buy"],
            risk_ok=True,
            position_ok=True,
            model_name="momentum_v2",
            reasons=["资金持续流入 AI 板块", "市场风险较低"],
        )
        assert report["signal"] == "BUY"
        assert report["symbol"] == "NVDA"
        assert "price_model" in report["attribution"]
        assert len(report["feature_importance"]) == 3
        assert "Fed Cut" in report["decision_path"]
        assert report["confidence"]["confidence_score"] == 94.0
        assert report["confidence"]["actionable"] is True
        assert report["validation_passed"] is True
        assert report["audit"]["model"] == "momentum_v2"
        assert "NVDA" in report["explanation"]
        assert "94%" in report["explanation"]

    def test_explain_full_failed_validation(self):
        service = ExplainableAIService(HumanExplanationGenerator())
        report = service.explain_full(
            signal="BUY",
            symbol="AAPL",
            probability=0.60,
            risk_ok=False,
            position_ok=True,
        )
        assert report["validation_passed"] is False

    def test_memory_persistence_in_pipeline(self):
        service = ExplainableAIService(HumanExplanationGenerator())
        service.explain_full(signal="BUY", symbol="TSLA", probability=0.80)
        assert service.memory.record_count == 1
        records = service.memory.query_by_signal("BUY")
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Original minimal test from spec
# ---------------------------------------------------------------------------

def test_explain():
    service = ExplainableAIService(HumanExplanationGenerator())
    result = service.explain("BUY")
    assert "BUY" in result
