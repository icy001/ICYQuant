"""Tests for AI Trading Review & Learning Engine."""

import pytest
from services.trading_learning import (
    TradeResult,
    OutcomeAnalyzer,
    OutcomeReport,
    StrategyFeedbackEngine,
    StrategyFeedback,
    MistakeDetector,
    MistakeReport,
    LearningMemory,
    LearningRecord,
    AttributionEngine,
    AttributionResult,
    TradingJournalGenerator,
    JournalEntry,
    TradingLearningService,
)


# ======================================================================
# TradeResult
# ======================================================================

class TestTradeResult:
    """Tests for the TradeResult model."""

    def test_create_basic(self):
        t = TradeResult(trade_id="T001", pnl=1000, holding_days=5)
        assert t.trade_id == "T001"
        assert t.pnl == 1000
        assert t.holding_days == 5

    def test_is_profitable(self):
        assert TradeResult("T001", pnl=100).is_profitable
        assert not TradeResult("T002", pnl=-100).is_profitable
        assert not TradeResult("T003", pnl=0).is_profitable

    def test_is_loss(self):
        assert TradeResult("T001", pnl=-100).is_loss
        assert not TradeResult("T002", pnl=100).is_loss

    def test_is_breakeven(self):
        assert TradeResult("T001", pnl=0).is_breakeven
        assert not TradeResult("T002", pnl=100).is_breakeven

    def test_outcome_property(self):
        assert TradeResult("T001", pnl=100).outcome == "win"
        assert TradeResult("T002", pnl=-50).outcome == "loss"
        assert TradeResult("T003", pnl=0).outcome == "breakeven"

    def test_execution_quality_entry(self):
        t = TradeResult("T001", entry_slippage_bps=0.5)
        assert t.execution_quality_entry == "excellent"
        t.entry_slippage_bps = 3.0
        assert t.execution_quality_entry == "good"
        t.entry_slippage_bps = 10.0
        assert t.execution_quality_entry == "fair"
        t.entry_slippage_bps = 20.0
        assert t.execution_quality_entry == "poor"

    def test_execution_quality_exit(self):
        t = TradeResult("T001", exit_slippage_bps=0.5)
        assert t.execution_quality_exit == "excellent"
        t.exit_slippage_bps = 20.0
        assert t.execution_quality_exit == "poor"

    def test_full_trade_result(self):
        t = TradeResult(
            trade_id="T-2024-001",
            symbol="NVDA",
            side="LONG",
            entry_price=100.0,
            exit_price=108.0,
            target_price=110.0,
            stop_loss=95.0,
            pnl=8000,
            pnl_pct=8.0,
            holding_days=5,
            quantity=1000,
            strategy_id="ST-MOM",
            strategy_name="Momentum Alpha",
            decision_reason="Breakout above 20-day high",
            market_regime="trending",
            risk_score=0.4,
            entry_slippage_bps=2.0,
            exit_slippage_bps=1.5,
            tags=["momentum", "breakout"],
        )
        assert t.symbol == "NVDA"
        assert t.outcome == "win"
        assert t.is_profitable
        assert t.entry_slippage_bps == 2.0
        assert "momentum" in t.tags

    def test_to_dict(self):
        t = TradeResult(trade_id="T001", symbol="NVDA", side="LONG",
                        pnl=500, pnl_pct=5.0, holding_days=3)
        d = t.to_dict()
        assert d["trade_id"] == "T001"
        assert d["symbol"] == "NVDA"
        assert d["pnl"] == 500


# ======================================================================
# OutcomeAnalyzer
# ======================================================================

class TestOutcomeAnalyzer:
    """Tests for the OutcomeAnalyzer."""

    def test_analyze_basic(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=5)
        result = analyzer.analyze(trade)
        assert "pnl" in result
        assert "quality" in result
        assert "score" in result

    def test_analyze_profitable_trade(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            entry_price=100, exit_price=108,
                            pnl=8000, pnl_pct=8.0, holding_days=5,
                            entry_slippage_bps=1.0, exit_slippage_bps=1.0)
        result = analyzer.analyze_detailed(trade)
        assert result.quality in ("excellent", "good", "fair")
        assert result.score > 50
        assert result.pnl > 0

    def test_analyze_losing_trade(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T002", symbol="NVDA", side="LONG",
                            pnl=-5000, pnl_pct=-5.0, holding_days=10,
                            entry_slippage_bps=15.0, exit_slippage_bps=20.0,
                            stop_loss=95.0, exit_price=90.0)
        result = analyzer.analyze_detailed(trade)
        assert result.quality in ("poor", "fair")
        assert result.score < 60

    def test_outcome_categories(self):
        analyzer = OutcomeAnalyzer()
        # Quick win
        t1 = TradeResult("T001", pnl=500, pnl_pct=3.0, holding_days=1)
        r1 = analyzer.analyze_detailed(t1)
        assert r1.outcome_category == "quick_win"

        # Cut loss
        t2 = TradeResult("T002", pnl=-500, pnl_pct=-2.0, holding_days=1)
        r2 = analyzer.analyze_detailed(t2)
        assert r2.outcome_category == "cut_loss"

    def test_analyze_detailed_has_strengths(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=8000, pnl_pct=8.0, holding_days=3,
                            entry_slippage_bps=0.5, exit_slippage_bps=0.5)
        result = analyzer.analyze_detailed(trade)
        assert len(result.strengths) > 0

    def test_analyze_detailed_has_weaknesses(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T002", symbol="NVDA", side="LONG",
                            pnl=-8000, pnl_pct=-8.0, holding_days=5,
                            entry_slippage_bps=15.0, exit_slippage_bps=15.0)
        result = analyzer.analyze_detailed(trade)
        assert len(result.weaknesses) > 0

    def test_analyze_detailed_has_recommendations(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=8000, pnl_pct=8.0, holding_days=5,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = analyzer.analyze_detailed(trade)
        assert len(result.recommendations) > 0

    def test_analyze_batch(self):
        analyzer = OutcomeAnalyzer()
        trades = [
            TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-500, pnl_pct=-3.0, holding_days=2),
        ]
        results = analyzer.analyze_batch(trades)
        assert len(results) == 2
        assert all(isinstance(r, OutcomeReport) for r in results)

    def test_batch_summary(self):
        analyzer = OutcomeAnalyzer()
        trades = [
            TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-500, pnl_pct=-3.0, holding_days=2),
            TradeResult("T003", pnl=2000, pnl_pct=10.0, holding_days=7),
        ]
        reports = analyzer.analyze_batch(trades)
        summary = analyzer.batch_summary(reports)
        assert summary["total_trades"] == 3
        assert abs(summary["win_rate"] - 2 / 3) < 0.01
        assert "quality_distribution" in summary

    def test_batch_summary_empty(self):
        analyzer = OutcomeAnalyzer()
        summary = analyzer.batch_summary([])
        assert summary["total_trades"] == 0

    def test_score_pnl_breakpoints(self):
        analyzer = OutcomeAnalyzer()
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=15)) == 40
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=6)) == 35
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=3)) == 30
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=1)) == 20
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=-1)) == 10
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=-3)) == 5
        assert analyzer._score_pnl(TradeResult("T", pnl_pct=-10)) == 0

    def test_holding_efficiency_label(self):
        analyzer = OutcomeAnalyzer()
        # 10% / 5 days = 2% daily → excellent
        assert analyzer._holding_efficiency_label(
            TradeResult("T", pnl_pct=10, holding_days=5)) == "excellent"
        assert analyzer._holding_efficiency_label(
            TradeResult("T", pnl_pct=10, holding_days=2)) == "excellent"
        assert analyzer._holding_efficiency_label(
            TradeResult("T", pnl_pct=2, holding_days=5)) == "fair"
        assert analyzer._holding_efficiency_label(
            TradeResult("T", pnl_pct=-1, holding_days=5)) == "negative"

    def test_quality_excellent(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=10000, pnl_pct=12.0, holding_days=5,
                            entry_slippage_bps=0.5, exit_slippage_bps=0.5,
                            target_price=110, exit_price=108)
        result = analyzer.analyze_detailed(trade)
        assert result.quality == "excellent"


# ======================================================================
# StrategyFeedbackEngine
# ======================================================================

class TestStrategyFeedbackEngine:
    """Tests for the StrategyFeedbackEngine."""

    def test_generate_with_trades(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=3,
                        strategy_name="Momentum"),
            TradeResult("T002", pnl=-200, pnl_pct=-1.0, holding_days=2,
                        strategy_name="Momentum"),
            TradeResult("T003", pnl=800, pnl_pct=4.0, holding_days=4,
                        strategy_name="Momentum"),
        ]
        result = engine.generate(trades, strategy_name="Momentum")
        assert isinstance(result, StrategyFeedback)
        assert result.win_rate > 0.5
        assert result.profit_factor > 1.0
        assert result.status in ("improving", "stable", "deteriorating", "critical")
        assert result.action in ("increase", "maintain", "reduce", "pause", "stop")

    def test_generate_empty(self):
        engine = StrategyFeedbackEngine()
        result = engine.generate([], strategy_name="Test")
        assert result.status == "stable"
        assert result.action == "maintain"

    def test_generate_all_losses(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=-500, pnl_pct=-3.0, holding_days=2),
            TradeResult("T002", pnl=-300, pnl_pct=-2.0, holding_days=1),
            TradeResult("T003", pnl=-700, pnl_pct=-4.0, holding_days=3),
        ]
        result = engine.generate(trades)
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.status in ("deteriorating", "critical")

    def test_generate_all_wins(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=300, pnl_pct=3.0, holding_days=2),
            TradeResult("T003", pnl=700, pnl_pct=7.0, holding_days=4),
        ]
        result = engine.generate(trades)
        assert result.win_rate == 1.0
        assert result.status == "improving"
        assert result.action == "increase"

    def test_generate_has_suggestions(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=-500, pnl_pct=-6.0, holding_days=2),
            TradeResult("T002", pnl=-300, pnl_pct=-4.0, holding_days=1),
        ]
        result = engine.generate(trades)
        assert len(result.suggestions) > 0

    def test_generate_has_explanation(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
        ]
        result = engine.generate(trades)
        assert len(result.explanation) > 0

    def test_to_dict(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3,
                        strategy_name="TestStrat"),
        ]
        result = engine.generate(trades, strategy_name="TestStrat")
        d = result.to_dict()
        assert d["strategy_name"] == "TestStrat"
        assert "win_rate" in d
        assert "action" in d

    def test_legacy_generate_from_result(self):
        engine = StrategyFeedbackEngine()
        result = engine.generate_from_result({"key": "value"})
        assert result["feedback"] == {"key": "value"}

    def test_few_trades_maintain(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-300, pnl_pct=-3.0, holding_days=1),
        ]
        result = engine.generate(trades)
        # Less than 3 trades → maintain
        assert result.action == "maintain"

    def test_critical_drawdown(self):
        engine = StrategyFeedbackEngine()
        trades = [
            TradeResult("T001", pnl=-800, pnl_pct=-8.0, holding_days=2),
            TradeResult("T002", pnl=-800, pnl_pct=-8.0, holding_days=2),
            TradeResult("T003", pnl=-800, pnl_pct=-8.0, holding_days=2),
        ]
        result = engine.generate(trades)
        assert result.status == "critical"
        assert result.action == "pause"


# ======================================================================
# MistakeDetector
# ======================================================================

class TestMistakeDetector:
    """Tests for the MistakeDetector."""

    def test_detect_no_mistakes(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", side="LONG",
                            entry_slippage_bps=1.0, exit_slippage_bps=1.0,
                            stop_loss=95.0, exit_price=100.0,
                            risk_score=0.3, holding_days=5,
                            pnl_pct=5.0)
        result = detector.detect(trade)
        # Should only have "No stop-loss set" or "none"
        assert isinstance(result, list)

    def test_detect_late_entry(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", entry_slippage_bps=15.0,
                            exit_slippage_bps=2.0, stop_loss=95.0,
                            exit_price=100.0, side="LONG",
                            risk_score=0.3, holding_days=5)
        result = detector.detect(trade)
        assert any("Late entry" in m for m in result)

    def test_detect_poor_exit(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", exit_slippage_bps=15.0,
                            entry_slippage_bps=2.0, stop_loss=95.0,
                            exit_price=100.0, side="LONG",
                            risk_score=0.3, holding_days=5)
        result = detector.detect(trade)
        assert any("Poor exit" in m for m in result)

    def test_detect_stop_loss_violation(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", side="LONG",
                            stop_loss=95.0, exit_price=90.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            risk_score=0.3, holding_days=5)
        result = detector.detect(trade)
        assert any("Stop-loss violation" in m for m in result)

    def test_detect_over_positioning(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", risk_score=0.85,
                            quantity=10000, side="LONG",
                            stop_loss=95.0, exit_price=100.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            holding_days=5)
        result = detector.detect(trade)
        assert any("Over-positioning" in m for m in result)

    def test_detect_early_exit(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", pnl_pct=3.0, holding_days=0,
                            side="LONG", stop_loss=95.0,
                            exit_price=100.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            risk_score=0.3)
        result = detector.detect(trade)
        assert any("Early exit" in m for m in result)

    def test_detect_holding_loser(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", pnl_pct=-5.0, holding_days=35,
                            side="LONG", stop_loss=95.0,
                            exit_price=90.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            risk_score=0.3)
        result = detector.detect(trade)
        assert any("Holding loser" in m for m in result)

    def test_detect_emotion_bias(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", side="LONG",
                            entry_slippage_bps=10.0, exit_slippage_bps=10.0,
                            stop_loss=95.0, exit_price=100.0,
                            risk_score=0.3, holding_days=5)
        result = detector.detect(trade)
        assert any("Emotion bias" in m for m in result)

    def test_detect_no_stop_loss(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", stop_loss=0, side="LONG",
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            exit_price=100.0, risk_score=0.3,
                            holding_days=5)
        result = detector.detect(trade)
        assert any("No stop-loss" in m for m in result)

    def test_detect_detailed(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", side="LONG",
                            entry_slippage_bps=15.0, exit_slippage_bps=15.0,
                            stop_loss=95.0, exit_price=90.0,
                            risk_score=0.85, quantity=10000,
                            pnl_pct=-5.0, holding_days=35)
        result = detector.detect_detailed(trade)
        assert isinstance(result, MistakeReport)
        assert result.has_mistakes()
        assert result.severity in ("major", "critical")
        assert result.error_count > 0

    def test_detect_detailed_no_mistakes(self):
        detector = MistakeDetector()
        trade = TradeResult("T001", side="LONG",
                            entry_slippage_bps=1.0, exit_slippage_bps=1.0,
                            stop_loss=95.0, exit_price=100.0,
                            risk_score=0.2, quantity=100,
                            pnl_pct=2.0, holding_days=5)
        result = detector.detect_detailed(trade)
        assert not result.has_mistakes()
        assert result.severity == "none"

    def test_detect_batch(self):
        detector = MistakeDetector()
        trades = [
            TradeResult("T001", entry_slippage_bps=15.0, exit_slippage_bps=2.0,
                        stop_loss=95.0, exit_price=100.0, side="LONG",
                        risk_score=0.3, holding_days=5),
            TradeResult("T002", entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                        stop_loss=95.0, exit_price=100.0, side="LONG",
                        risk_score=0.3, holding_days=5),
        ]
        results = detector.detect_batch(trades)
        assert len(results) == 2
        assert all(isinstance(r, MistakeReport) for r in results)

    def test_batch_summary(self):
        detector = MistakeDetector()
        trades = [
            TradeResult("T001", entry_slippage_bps=15.0, exit_slippage_bps=2.0,
                        stop_loss=95.0, exit_price=100.0, side="LONG",
                        risk_score=0.3, holding_days=5),
            TradeResult("T002", entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                        stop_loss=95.0, exit_price=100.0, side="LONG",
                        risk_score=0.3, holding_days=5),
        ]
        reports = detector.detect_batch(trades)
        summary = detector.batch_summary(reports)
        assert summary["total_trades"] == 2
        assert "common_mistakes" in summary

    def test_severity_none(self):
        detector = MistakeDetector()
        assert detector._assess_severity(["none"], TradeResult("T")) == "none"

    def test_severity_critical(self):
        detector = MistakeDetector()
        mistakes = ["Stop-loss violation", "Over-positioning"]
        trade = TradeResult("T", pnl_pct=-10)
        assert detector._assess_severity(mistakes, trade) == "critical"

    def test_mistake_report_to_dict(self):
        report = MistakeReport(
            trade_id="T001",
            mistakes=["Late entry", "Poor exit"],
            severity="moderate",
            error_count=2,
        )
        d = report.to_dict()
        assert d["trade_id"] == "T001"
        assert d["severity"] == "moderate"
        assert d["has_mistakes"]


# ======================================================================
# LearningMemory
# ======================================================================

class TestLearningMemory:
    """Tests for the LearningMemory."""

    def test_store_and_retrieve(self):
        mem = LearningMemory()
        record = LearningRecord(record_id="LR-0001", trade_id="T001",
                                symbol="NVDA", outcome="win")
        mem.store(record)
        assert len(mem.get_all()) == 1

    def test_store_trade_result(self):
        mem = LearningMemory()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, pnl_pct=5.0, strategy_id="ST-1",
                            market_regime="trending")
        record = mem.store_trade_result(trade, quality_score=85.0,
                                        mistakes=["Late entry"],
                                        strengths=["Good timing"],
                                        lesson="Be patient on entry",
                                        tags=["momentum"])
        assert record.trade_id == "T001"
        assert record.symbol == "NVDA"
        assert record.outcome == "win"
        assert record.quality_score == 85.0
        assert "Late entry" in record.mistakes
        assert "Good timing" in record.strengths
        assert record.lesson == "Be patient on entry"
        assert "momentum" in record.tags

    def test_query_by_symbol(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", symbol="NVDA"))
        mem.store(LearningRecord("LR-2", "T002", symbol="AAPL"))
        mem.store(LearningRecord("LR-3", "T003", symbol="NVDA"))
        results = mem.query_by_symbol("NVDA")
        assert len(results) == 2

    def test_query_by_strategy(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", strategy_id="ST-1"))
        mem.store(LearningRecord("LR-2", "T002", strategy_id="ST-2"))
        mem.store(LearningRecord("LR-3", "T003", strategy_id="ST-1"))
        results = mem.query_by_strategy("ST-1")
        assert len(results) == 2

    def test_query_by_outcome(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", outcome="win"))
        mem.store(LearningRecord("LR-2", "T002", outcome="loss"))
        mem.store(LearningRecord("LR-3", "T003", outcome="win"))
        results = mem.query_by_outcome("win")
        assert len(results) == 2

    def test_query_by_market_regime(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", market_regime="trending"))
        mem.store(LearningRecord("LR-2", "T002", market_regime="ranging"))
        results = mem.query_by_market_regime("trending")
        assert len(results) == 1

    def test_query_by_tag(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", tags=["momentum", "tech"]))
        mem.store(LearningRecord("LR-2", "T002", tags=["value", "finance"]))
        results = mem.query_by_tag("momentum")
        assert len(results) == 1

    def test_win_rate_by_symbol(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", symbol="NVDA", outcome="win"))
        mem.store(LearningRecord("LR-2", "T002", symbol="NVDA", outcome="loss"))
        result = mem.win_rate_by_symbol("NVDA")
        assert result["total"] == 2
        assert result["win_rate"] == 0.5

    def test_win_rate_by_symbol_empty(self):
        mem = LearningMemory()
        result = mem.win_rate_by_symbol("UNKNOWN")
        assert result["total"] == 0

    def test_win_rate_by_regime(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", market_regime="trending",
                                 outcome="win"))
        mem.store(LearningRecord("LR-2", "T002", market_regime="trending",
                                 outcome="loss"))
        mem.store(LearningRecord("LR-3", "T003", market_regime="ranging",
                                 outcome="win"))
        result = mem.win_rate_by_regime()
        assert "trending" in result
        assert "ranging" in result

    def test_top_mistakes(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001",
                                 mistakes=["Late entry", "Poor exit"]))
        mem.store(LearningRecord("LR-2", "T002",
                                 mistakes=["Late entry"]))
        top = mem.top_mistakes()
        assert len(top) >= 1
        assert top[0]["mistake"] == "Late entry"
        assert top[0]["count"] == 2

    def test_summary(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001", outcome="win",
                                 quality_score=85.0, symbol="NVDA",
                                 strategy_id="ST-1"))
        mem.store(LearningRecord("LR-2", "T002", outcome="loss",
                                 quality_score=40.0, symbol="AAPL",
                                 strategy_id="ST-1"))
        summary = mem.summary()
        assert summary["total_records"] == 2
        assert summary["win_rate"] == 0.5
        assert summary["unique_symbols"] == 2
        assert summary["unique_strategies"] == 1

    def test_summary_empty(self):
        mem = LearningMemory()
        summary = mem.summary()
        assert summary["total_records"] == 0

    def test_clear(self):
        mem = LearningMemory()
        mem.store(LearningRecord("LR-1", "T001"))
        mem.clear()
        assert len(mem.get_all()) == 0

    def test_learning_record_to_dict(self):
        record = LearningRecord(
            record_id="LR-0001",
            trade_id="T001",
            symbol="NVDA",
            outcome="win",
            quality_score=85.0,
            mistakes=["Late entry"],
            strengths=["Good timing"],
            lesson="Be patient",
            tags=["momentum"],
            strategy_id="ST-1",
            market_regime="trending",
        )
        d = record.to_dict()
        assert d["record_id"] == "LR-0001"
        assert d["trade_id"] == "T001"


# ======================================================================
# AttributionEngine
# ======================================================================

class TestAttributionEngine:
    """Tests for the AttributionEngine."""

    def test_analyze_basic(self):
        engine = AttributionEngine()
        trade = TradeResult("T001", pnl_pct=10.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = engine.analyze(trade)
        assert "alpha" in result
        assert "market_beta" in result

    def test_analyze_detailed(self):
        engine = AttributionEngine()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl_pct=10.0, holding_days=5,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = engine.analyze_detailed(trade, market_return_pct=3.0,
                                         sector_return_pct=5.0, beta=1.2)
        assert isinstance(result, AttributionResult)
        assert result.total_pnl_pct == 10.0
        assert result.market_beta != 0
        # Alpha + market + sector + timing + execution ≈ total
        explained = (result.alpha + result.market_beta + result.sector +
                     result.timing + result.execution)
        assert abs(explained - result.total_pnl_pct) < 0.01

    def test_analyze_with_high_slippage(self):
        engine = AttributionEngine()
        trade = TradeResult("T001", pnl_pct=5.0,
                            entry_slippage_bps=20.0, exit_slippage_bps=20.0)
        result = engine.analyze_detailed(trade)
        # High slippage should negatively impact execution attribution
        assert result.execution < 0

    def test_analyze_batch(self):
        engine = AttributionEngine()
        trades = [
            TradeResult("T001", pnl_pct=5.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
            TradeResult("T002", pnl_pct=-3.0, entry_slippage_bps=2.0,
                        exit_slippage_bps=2.0),
        ]
        results = engine.analyze_batch(trades)
        assert len(results) == 2
        assert all(isinstance(r, AttributionResult) for r in results)

    def test_aggregate(self):
        engine = AttributionEngine()
        trades = [
            TradeResult("T001", pnl_pct=5.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
            TradeResult("T002", pnl_pct=3.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
        ]
        results = engine.analyze_batch(trades)
        agg = engine.aggregate(results)
        assert agg["total_trades"] == 2
        assert abs(agg["total_pnl_pct"] - 8.0) < 0.1
        assert "alpha_contribution" in agg

    def test_aggregate_empty(self):
        engine = AttributionEngine()
        agg = engine.aggregate([])
        assert agg["total_trades"] == 0

    def test_attribution_result_to_dict(self):
        result = AttributionResult(
            trade_id="T001",
            total_pnl_pct=10.0,
            alpha=6.0,
            market_beta=3.0,
            sector=1.0,
            timing=0.5,
            execution=-0.5,
            confidence=0.8,
        )
        d = result.to_dict()
        assert d["trade_id"] == "T001"
        assert d["alpha"] == 6.0
        assert d["confidence"] == 0.8

    def test_timing_positive_market_up(self):
        engine = AttributionEngine()
        # Positive entry slippage = bought above reference, market went up
        timing = engine._estimate_timing(
            TradeResult("T", entry_slippage_bps=5.0), market_return_pct=5.0)
        assert timing < 0  # negative timing: bought above reference

    def test_timing_negative_market_down(self):
        engine = AttributionEngine()
        timing = engine._estimate_timing(
            TradeResult("T", entry_slippage_bps=-5.0), market_return_pct=-5.0)
        assert timing < 0


# ======================================================================
# TradingJournalGenerator
# ======================================================================

class TestTradingJournalGenerator:
    """Tests for the TradingJournalGenerator."""

    def test_generate(self):
        generator = TradingJournalGenerator()
        trade = TradeResult(
            trade_id="T001", symbol="NVDA", side="LONG",
            entry_price=100, exit_price=108,
            pnl=8000, pnl_pct=8.0, holding_days=5,
            quantity=1000,
            decision_reason="Breakout above resistance",
            market_regime="trending",
            strategy_name="Momentum Alpha",
            entry_slippage_bps=2.0, exit_slippage_bps=1.5,
            risk_score=0.4, stop_loss=95.0,
            tags=["momentum", "breakout"],
        )
        entry = generator.generate(
            trade,
            thesis="NVDA breaking out on strong volume",
            entry_reason="Price crossed 20-day high with volume confirmation",
            exit_reason="Target reached after 5 days of trend continuation",
            lesson="Momentum breakouts work well in trending markets",
            improvement_plan="Scale position size on high-confidence setups",
        )
        assert isinstance(entry, JournalEntry)
        assert entry.trade_id == "T001"
        assert entry.symbol == "NVDA"
        assert entry.pnl == 8000
        assert entry.outcome == "win"

    def test_generate_from_trade(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", pnl=1000)
        result = generator.generate_from_trade(trade)
        assert result["journal"] == "T001"
        assert "entry" in result

    def test_generate_batch(self):
        generator = TradingJournalGenerator()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, symbol="NVDA",
                        side="LONG", holding_days=3),
            TradeResult("T002", pnl=-200, pnl_pct=-2.0, symbol="AAPL",
                        side="SHORT", holding_days=2),
        ]
        entries = generator.generate_batch(trades)
        assert len(entries) == 2
        assert all(isinstance(e, JournalEntry) for e in entries)

    def test_journal_to_dict(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, pnl_pct=5.0, holding_days=3,
                            entry_price=100, quantity=100)
        entry = generator.generate(trade)
        d = entry.to_dict()
        assert d["trade_id"] == "T001"
        assert d["symbol"] == "NVDA"
        assert "thesis" in d
        assert "lesson" in d

    def test_journal_to_markdown(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, pnl_pct=5.0, holding_days=3,
                            strategy_name="Test", market_regime="trending",
                            entry_price=100, quantity=100,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                            stop_loss=95.0, risk_score=0.3,
                            tags=["test"])
        entry = generator.generate(trade)
        md = entry.to_markdown()
        assert "# Trading Journal" in md
        assert "T001" in md
        assert "NVDA" in md
        assert "## Trade Thesis" in md
        assert "## Outcome" in md
        assert "## Reflection" in md

    def test_infer_exit_reason_target(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", side="LONG",
                            target_price=100, exit_price=99)
        reason = generator._infer_exit_reason(trade)
        assert "Target reached" in reason

    def test_infer_exit_reason_stop(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", side="LONG",
                            stop_loss=95, exit_price=90)
        reason = generator._infer_exit_reason(trade)
        assert "Stop-loss" in reason

    def test_infer_exit_reason_time(self):
        generator = TradingJournalGenerator()
        trade = TradeResult("T001", side="LONG", holding_days=25)
        reason = generator._infer_exit_reason(trade)
        assert "Time-based" in reason

    def test_assess_risk(self):
        generator = TradingJournalGenerator()
        assert "Conservative" in generator._assess_risk(
            TradeResult("T", risk_score=0.2))
        assert "Moderate" in generator._assess_risk(
            TradeResult("T", risk_score=0.5))
        assert "Aggressive" in generator._assess_risk(
            TradeResult("T", risk_score=0.7))
        assert "High risk" in generator._assess_risk(
            TradeResult("T", risk_score=0.9))


# ======================================================================
# TradingLearningService
# ======================================================================

class TestTradingLearningService:
    """Integration tests for the TradingLearningService."""

    def test_create_service(self):
        service = TradingLearningService()
        assert service is not None

    def test_review_legacy(self):
        analyzer = OutcomeAnalyzer()
        service = TradingLearningService(analyzer=analyzer)
        trade = TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=5)
        result = service.review(trade)
        assert result["quality"] in ("excellent", "good", "fair", "poor")

    def test_review_detailed(self):
        service = TradingLearningService()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=8000, pnl_pct=8.0, holding_days=5,
                            entry_slippage_bps=1.0, exit_slippage_bps=1.0)
        result = service.review_detailed(trade)
        assert isinstance(result, OutcomeReport)
        assert result.trade_id == "T001"

    def test_strategy_feedback(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-200, pnl_pct=-2.0, holding_days=1),
            TradeResult("T003", pnl=300, pnl_pct=3.0, holding_days=2),
        ]
        result = service.strategy_feedback(trades, strategy_name="Test")
        assert isinstance(result, StrategyFeedback)
        assert result.win_rate > 0.5

    def test_detect_mistakes(self):
        service = TradingLearningService()
        trade = TradeResult("T001", entry_slippage_bps=15.0,
                            exit_slippage_bps=2.0, stop_loss=95.0,
                            exit_price=100.0, side="LONG",
                            risk_score=0.3, holding_days=5)
        result = service.detect_mistakes(trade)
        assert isinstance(result, list)

    def test_store_learning(self):
        service = TradingLearningService()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, pnl_pct=5.0, strategy_id="ST-1",
                            market_regime="trending")
        record = service.store_learning(trade, quality_score=85.0,
                                        mistakes=["Late entry"],
                                        strengths=["Good timing"],
                                        lesson="Patience on entry",
                                        tags=["momentum"])
        assert record.trade_id == "T001"
        assert len(service._memory.get_all()) == 1

    def test_query_learning(self):
        service = TradingLearningService()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, strategy_id="ST-1",
                            market_regime="trending")
        service.store_learning(trade)
        results = service.query_learning(symbol="NVDA")
        assert len(results) == 1

    def test_attribute(self):
        service = TradingLearningService()
        trade = TradeResult("T001", pnl_pct=10.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = service.attribute(trade)
        assert "alpha" in result
        assert "market_beta" in result

    def test_attribute_detailed(self):
        service = TradingLearningService()
        trade = TradeResult("T001", pnl_pct=10.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = service.attribute_detailed(trade, market_return_pct=3.0,
                                            sector_return_pct=5.0)
        assert isinstance(result, AttributionResult)

    def test_generate_journal(self):
        service = TradingLearningService()
        trade = TradeResult("T001", symbol="NVDA", side="LONG",
                            pnl=1000, pnl_pct=5.0, holding_days=3,
                            entry_price=100, quantity=100,
                            strategy_name="Test", market_regime="trending")
        entry = service.generate_journal(trade, thesis="Test thesis")
        assert isinstance(entry, JournalEntry)
        assert entry.trade_id == "T001"

    def test_learning_summary(self):
        service = TradingLearningService()
        trade = TradeResult("T001", pnl=1000, symbol="NVDA")
        service.store_learning(trade)
        summary = service.learning_summary()
        assert summary["total_records"] == 1

    def test_review_batch(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-200, pnl_pct=-2.0, holding_days=1),
        ]
        results = service.review_batch(trades)
        assert len(results) == 2

    def test_review_summary(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", pnl=-200, pnl_pct=-2.0, holding_days=1),
        ]
        reports = service.review_batch(trades)
        summary = service.review_summary(reports)
        assert summary["total_trades"] == 2

    def test_attribute_batch(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", pnl_pct=5.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
            TradeResult("T002", pnl_pct=3.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
        ]
        results = service.attribute_batch(trades)
        assert len(results) == 2

    def test_attribute_aggregate(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", pnl_pct=5.0, entry_slippage_bps=1.0,
                        exit_slippage_bps=1.0),
        ]
        results = service.attribute_batch(trades)
        agg = service.attribute_aggregate(results)
        assert agg["total_trades"] == 1

    def test_generate_journal_batch(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", symbol="NVDA", side="LONG",
                        pnl=500, pnl_pct=5.0, holding_days=3),
            TradeResult("T002", symbol="AAPL", side="SHORT",
                        pnl=-200, pnl_pct=-2.0, holding_days=1),
        ]
        entries = service.generate_journal_batch(trades)
        assert len(entries) == 2

    # ------------------------------------------------------------------
    # Full Learning Loop
    # ------------------------------------------------------------------

    def test_learn(self):
        service = TradingLearningService()
        trade = TradeResult(
            trade_id="T001",
            symbol="NVDA",
            side="LONG",
            entry_price=100.0,
            exit_price=108.0,
            pnl=8000,
            pnl_pct=8.0,
            holding_days=5,
            quantity=1000,
            entry_slippage_bps=2.0,
            exit_slippage_bps=1.5,
            strategy_id="ST-1",
            strategy_name="Momentum Alpha",
            decision_reason="Breakout signal",
            market_regime="trending",
            risk_score=0.4,
            stop_loss=95.0,
            target_price=110.0,
            tags=["momentum"],
        )
        result = service.learn(
            trade,
            market_return_pct=3.0,
            sector_return_pct=5.0,
            beta=1.2,
            thesis="NVDA breakout on strong volume",
            entry_reason="20-day high break with volume",
            exit_reason="Target area reached",
        )
        assert "outcome" in result
        assert "attribution" in result
        assert "mistakes" in result
        assert "learning_record" in result
        assert "journal" in result
        assert "lesson" in result
        assert len(result["lesson"]) > 0

    def test_learn_loss_trade(self):
        service = TradingLearningService()
        trade = TradeResult(
            trade_id="T002",
            symbol="AAPL",
            side="LONG",
            pnl=-5000,
            pnl_pct=-5.0,
            holding_days=10,
            entry_slippage_bps=10.0,
            exit_slippage_bps=15.0,
            stop_loss=140.0,
            exit_price=135.0,
            risk_score=0.6,
            strategy_name="Mean Reversion",
            market_regime="volatile",
        )
        result = service.learn(trade)
        assert result["outcome"]["quality"] in ("fair", "poor")
        assert result["mistakes"]["has_mistakes"]

    def test_learn_batch(self):
        service = TradingLearningService()
        trades = [
            TradeResult("T001", symbol="NVDA", side="LONG",
                        pnl=500, pnl_pct=5.0, holding_days=3,
                        entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                        strategy_name="Test", market_regime="trending"),
            TradeResult("T002", symbol="AAPL", side="SHORT",
                        pnl=-200, pnl_pct=-2.0, holding_days=1,
                        entry_slippage_bps=2.0, exit_slippage_bps=2.0,
                        strategy_name="Test", market_regime="volatile"),
        ]
        result = service.learn_batch(trades)
        assert "individual_results" in result
        assert "outcome_summary" in result
        assert "attribution_aggregate" in result
        assert "learning_summary" in result
        assert len(result["individual_results"]) == 2

    def test_derive_lesson(self):
        service = TradingLearningService()
        outcome = OutcomeReport(
            trade_id="T001", quality="good",
            outcome_category="trend_win", score=75.0,
        )
        mistakes = MistakeReport(trade_id="T001", mistakes=["none"])
        attribution = AttributionResult(trade_id="T001", alpha=5.0,
                                        execution=-0.2)
        lesson = service._derive_lesson(outcome, mistakes, attribution)
        assert len(lesson) > 0
        assert "trend_win" in lesson

    def test_derive_tags(self):
        service = TradingLearningService()
        trade = TradeResult("T001", pnl=500, tags=["momentum"],
                            market_regime="trending")
        outcome = OutcomeReport(trade_id="T001", quality="good",
                                outcome_category="trend_win")
        tags = service._derive_tags(trade, outcome)
        assert "momentum" in tags
        assert "win" in tags or "loss" in tags
        assert "trending" in tags


# ======================================================================
# End-to-End Workflow
# ======================================================================

class TestEndToEndWorkflow:
    """End-to-end learning workflow tests."""

    def test_complete_learning_loop(self):
        """Simulate: Trade → Review → Learn → Store → Feedback → Journal"""
        service = TradingLearningService()

        # 1. A completed trade arrives
        trade = TradeResult(
            trade_id="T-E2E-001",
            symbol="NVDA",
            side="LONG",
            entry_price=100.0,
            exit_price=108.0,
            target_price=110.0,
            stop_loss=95.0,
            pnl=8000,
            pnl_pct=8.0,
            holding_days=5,
            quantity=1000,
            entry_slippage_bps=2.0,
            exit_slippage_bps=1.5,
            strategy_id="ST-MOM-01",
            strategy_name="Momentum Alpha",
            decision_reason="Breakout above 20-day high with volume",
            market_regime="trending",
            risk_score=0.4,
            tags=["momentum", "tech"],
        )

        # 2. Run the full learning loop
        result = service.learn(trade, market_return_pct=3.0,
                               sector_return_pct=5.0, beta=1.2)

        # 3. Verify outcome analysis
        assert result["outcome"]["quality"] in ("excellent", "good")
        assert result["outcome"]["score"] > 50

        # 4. Verify performance attribution
        assert "alpha" in result["attribution"]

        # 5. Verify mistakes detected
        assert "severity" in result["mistakes"]

        # 6. Verify learning stored
        assert result["learning_record"]["trade_id"] == "T-E2E-001"

        # 7. Verify journal generated
        assert result["journal"]["trade_id"] == "T-E2E-001"

        # 8. Verify lesson extracted
        assert len(result["lesson"]) > 0

    def test_multi_trade_strategy_feedback_loop(self):
        """Simulate multiple trades → strategy feedback → action"""
        service = TradingLearningService()

        # Simulate 10 trades for a strategy (7 wins, 3 losses → improving)
        trades = []
        for i in range(10):
            win = i < 7  # 7 wins, 3 losses
            pnl_pct = 5.0 if win else -2.0
            trade = TradeResult(
                trade_id=f"T-{i:03d}",
                symbol="NVDA",
                side="LONG",
                pnl=pnl_pct * 100,
                pnl_pct=pnl_pct,
                holding_days=3,
                strategy_name="Momentum Alpha",
                strategy_id="ST-MOM-01",
                entry_slippage_bps=2.0,
                exit_slippage_bps=2.0,
            )
            trades.append(trade)
            service.store_learning(trade, quality_score=70.0 if win else 40.0)

        # Get strategy feedback
        feedback = service.strategy_feedback(trades, strategy_name="Momentum Alpha")

        assert feedback.win_rate == 0.7
        assert feedback.profit_factor > 2.0
        assert feedback.status == "improving"
        assert feedback.action == "increase"

    def test_mistake_pattern_detection(self):
        """Detect repeated mistakes across trades."""
        service = TradingLearningService()

        # Simulate trades with late entry pattern
        for i in range(5):
            trade = TradeResult(
                trade_id=f"T-{i:03d}",
                symbol="NVDA",
                side="LONG",
                pnl=-200,
                pnl_pct=-2.0,
                entry_slippage_bps=15.0,  # consistently late
                exit_slippage_bps=2.0,
                stop_loss=95.0,
                exit_price=100.0,
                holding_days=3,
                risk_score=0.3,
            )
            mistakes = service.detect_mistakes_detailed(trade)
            service.store_learning(trade, mistakes=mistakes.mistakes)

        # Check top mistakes
        top = service._memory.top_mistakes()
        assert len(top) >= 1
        assert any("Late entry" in m["mistake"] for m in top)


# ======================================================================
# Edge Cases
# ======================================================================

class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_zero_pnl_trade(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", pnl=0, pnl_pct=0.0, holding_days=5)
        result = analyzer.analyze_detailed(trade)
        assert result.quality in ("fair", "poor")

    def test_zero_holding_days(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", pnl=1000, pnl_pct=5.0, holding_days=0)
        result = analyzer.analyze_detailed(trade)
        assert result.holding_efficiency == "N/A"

    def test_very_large_pnl(self):
        analyzer = OutcomeAnalyzer()
        trade = TradeResult("T001", pnl=100000, pnl_pct=100.0, holding_days=1)
        result = analyzer.analyze_detailed(trade)
        assert result.score > 0

    def test_short_trade(self):
        trade = TradeResult("T001", side="SHORT",
                            entry_price=100, exit_price=90,
                            stop_loss=110, pnl=1000, pnl_pct=10.0,
                            holding_days=3)
        assert trade.is_profitable

    def test_empty_feedback(self):
        engine = StrategyFeedbackEngine()
        result = engine.generate([])
        assert result.status == "stable"
        assert result.action == "maintain"

    def test_attribution_zero_pnl(self):
        engine = AttributionEngine()
        trade = TradeResult("T001", pnl_pct=0.0,
                            entry_slippage_bps=2.0, exit_slippage_bps=2.0)
        result = engine.analyze_detailed(trade, market_return_pct=0.0)
        assert result.total_pnl_pct == 0.0

    def test_mistake_detector_custom_thresholds(self):
        detector = MistakeDetector(
            entry_slippage_threshold_bps=5.0,
            exit_slippage_threshold_bps=5.0,
        )
        trade = TradeResult("T001", entry_slippage_bps=8.0,
                            exit_slippage_bps=3.0, stop_loss=95.0,
                            exit_price=100.0, side="LONG",
                            risk_score=0.3, holding_days=5)
        result = detector.detect(trade)
        assert any("Late entry" in m for m in result)

    def test_memory_query_no_results(self):
        mem = LearningMemory()
        assert len(mem.query_by_symbol("UNKNOWN")) == 0
        assert len(mem.query_by_strategy("UNKNOWN")) == 0
        assert len(mem.query_by_outcome("UNKNOWN")) == 0
