"""Tests for AI Trading Copilot."""

import pytest
from services.trading_copilot import (
    MarketAnalysis,
    MarketAnalyst,
    PositionAnalysis,
    PositionAssistant,
    RiskAlert,
    RiskMonitor,
    TradePlan,
    TradePlanner,
    TradeReview,
    TradeReviewer,
    TradingMemory,
    MemoryRecord,
    TradingCopilot,
    TradingCopilotService,
)


# ====================================================================
# Market Analysis
# ====================================================================

class TestMarketAnalyst:
    def test_bullish_analysis(self):
        analyst = MarketAnalyst()
        result = analyst.analyze(
            symbol="NVDA",
            price_momentum=0.8,
            volume_confirmation=0.6,
            volatility=0.2,
            sector_strength=0.7,
            news_sentiment=0.5,
        )
        assert result.symbol == "NVDA"
        assert result.trend == "bullish"
        assert result.risk_level == "low"
        assert len(result.factors) > 0
        assert result.summary != ""

    def test_bearish_analysis(self):
        analyst = MarketAnalyst()
        result = analyst.analyze(
            symbol="TSLA",
            price_momentum=-0.9,
            volume_confirmation=-0.7,
            volatility=0.6,
            sector_strength=-0.5,
        )
        assert result.trend == "bearish"

    def test_neutral_analysis(self):
        analyst = MarketAnalyst()
        result = analyst.analyze(
            symbol="SPY",
            price_momentum=0.1,
            volume_confirmation=0.0,
            volatility=0.4,
            sector_strength=0.0,
        )
        assert result.trend == "neutral"

    def test_high_volatility_risk(self):
        analyst = MarketAnalyst()
        result = analyst.analyze(
            symbol="MSTR",
            price_momentum=0.2,
            volume_confirmation=0.1,
            volatility=0.9,
            sector_strength=0.0,
        )
        assert result.risk_level == "high"

    def test_to_dict(self):
        ma = MarketAnalysis(symbol="AAPL", trend="bullish", risk_level="low")
        d = ma.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["trend"] == "bullish"


# ====================================================================
# Position Analysis
# ====================================================================

class TestPositionAssistant:
    def test_strong_position(self):
        assistant = PositionAssistant()
        result = assistant.analyze_position(
            symbol="NVDA",
            exposure=0.20,
            momentum=0.7,
            valuation_high=False,
            sector_concentration=0.1,
            volatility=0.2,
        )
        assert "Momentum Strong" in result.strengths
        assert "Valuation High" not in result.risks

    def test_risky_position(self):
        assistant = PositionAssistant()
        result = assistant.analyze_position(
            symbol="MSTR",
            exposure=0.30,
            momentum=-0.5,
            valuation_high=True,
            sector_concentration=0.6,
            volatility=0.8,
        )
        assert "Valuation High" in result.risks
        assert "Sector Concentration" in result.risks
        assert "High Volatility" in result.risks

    def test_portfolio_overview(self):
        assistant = PositionAssistant()
        p1 = PositionAnalysis(symbol="A", exposure=0.3)
        p2 = PositionAnalysis(symbol="B", exposure=0.4)
        overview = assistant.portfolio_overview([p1, p2])
        assert abs(overview["total_exposure"] - 0.7) < 1e-9
        assert overview["position_count"] == 2

    def test_concentration_warning(self):
        assistant = PositionAssistant()
        p1 = PositionAnalysis(symbol="A", exposure=0.5)
        p2 = PositionAnalysis(symbol="B", exposure=0.5)
        overview = assistant.portfolio_overview([p1, p2])
        assert overview["concentration_warning"] is not None

    def test_to_dict(self):
        pa = PositionAnalysis(symbol="NVDA", exposure=0.2, comment="ok")
        d = pa.to_dict()
        assert d["symbol"] == "NVDA"
        assert abs(d["exposure"] - 0.2) < 1e-9


# ====================================================================
# Risk Alert
# ====================================================================

class TestRiskMonitor:
    def test_no_alerts_when_safe(self):
        monitor = RiskMonitor()
        alerts = monitor.check(exposure=0.5, drawdown=0.05, volatility=0.2, sector_concentration=0.1)
        assert len(alerts) == 0

    def test_critical_exposure(self):
        monitor = RiskMonitor(max_exposure=1.0)
        alerts = monitor.check(exposure=1.2)
        assert any(a.level == "critical" and a.source == "exposure" for a in alerts)

    def test_warning_exposure_approaching(self):
        monitor = RiskMonitor(max_exposure=1.0)
        alerts = monitor.check(exposure=0.85)
        assert any(a.level == "warning" and a.source == "exposure" for a in alerts)

    def test_critical_drawdown(self):
        monitor = RiskMonitor(max_drawdown=0.2)
        alerts = monitor.check(drawdown=0.25)
        assert any(a.level == "critical" and a.source == "drawdown" for a in alerts)

    def test_sector_concentration(self):
        monitor = RiskMonitor(max_sector_concentration=0.4)
        alerts = monitor.check(sector_concentration=0.55)
        assert any(a.source == "concentration" for a in alerts)

    def test_has_critical(self):
        monitor = RiskMonitor()
        alerts = [
            RiskAlert(level="warning", message="warn"),
            RiskAlert(level="critical", message="crit"),
        ]
        assert monitor.has_critical(alerts) is True

    def test_to_dict(self):
        ra = RiskAlert(level="warning", message="test", source="volatility", threshold=0.5, current_value=0.7)
        d = ra.to_dict()
        assert d["level"] == "warning"
        assert d["current_value"] == 0.7


# ====================================================================
# Trade Plan
# ====================================================================

class TestTradePlanner:
    def test_buy_signal(self):
        planner = TradePlanner()
        plan = planner.plan(symbol="NVDA", current_price=100.0, signal=0.7)
        assert plan.action == "buy"
        assert plan.entry_price == 100.0
        assert plan.stop_loss < plan.entry_price
        assert plan.take_profit > plan.entry_price

    def test_sell_signal(self):
        planner = TradePlanner()
        plan = planner.plan(symbol="TSLA", current_price=200.0, signal=-0.8)
        assert plan.action == "sell"
        assert plan.stop_loss > plan.entry_price  # stop above for sell
        assert plan.take_profit < plan.entry_price

    def test_hold_signal(self):
        planner = TradePlanner()
        plan = planner.plan(symbol="SPY", current_price=400.0, signal=0.1)
        assert plan.action == "hold"
        assert plan.position_size == 0.0

    def test_risk_limit_caps_position(self):
        planner = TradePlanner(default_position_size=0.5)
        plan = planner.plan(symbol="NVDA", current_price=100.0, signal=0.9, risk_limit=0.05)
        assert plan.position_size <= 0.05

    def test_strategy_name_in_rationale(self):
        planner = TradePlanner()
        plan = planner.plan(symbol="AAPL", current_price=150.0, signal=0.6, strategy_name="Momentum")
        assert "Momentum" in plan.rationale

    def test_to_dict(self):
        tp = TradePlan(symbol="NVDA", action="buy", stop_loss=95.0)
        d = tp.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["action"] == "buy"


# ====================================================================
# Trade Review
# ====================================================================

class TestTradeReviewer:
    def test_winning_trade(self):
        reviewer = TradeReviewer()
        result = reviewer.review(
            trade_id="T001",
            symbol="NVDA",
            entry_price=100.0,
            exit_price=115.0,
            take_profit=115.0,
            planned_action="buy",
            actual_action="buy",
        )
        assert result.result == "win"
        assert result.entry_quality == "good"
        assert result.exit_quality == "good"

    def test_losing_trade(self):
        reviewer = TradeReviewer()
        result = reviewer.review(
            trade_id="T002",
            symbol="TSLA",
            entry_price=200.0,
            exit_price=180.0,
            stop_loss=190.0,
        )
        assert result.result == "loss"

    def test_early_exit_detection(self):
        reviewer = TradeReviewer()
        result = reviewer.review(
            trade_id="T003",
            symbol="AAPL",
            entry_price=150.0,
            exit_price=158.0,
            take_profit=165.0,
        )
        assert any("Exited before target" in issue for issue in result.issues)

    def test_breakeven(self):
        reviewer = TradeReviewer()
        result = reviewer.review(
            trade_id="T004",
            symbol="SPY",
            entry_price=400.0,
            exit_price=400.5,
        )
        assert result.result == "breakeven"

    def test_to_dict(self):
        tr = TradeReview(trade_id="T1", result="win", feedback="good")
        d = tr.to_dict()
        assert d["trade_id"] == "T1"
        assert d["result"] == "win"


# ====================================================================
# Trading Memory
# ====================================================================

class TestTradingMemory:
    def test_save_and_history(self):
        mem = TradingMemory()
        record = MemoryRecord(
            trade_id="T1", symbol="NVDA", action="buy",
            decision_reason="momentum signal", outcome="win", pnl_pct=0.05,
        )
        mem.save(record)
        assert len(mem.history()) == 1

    def test_by_symbol(self):
        mem = TradingMemory()
        mem.save(MemoryRecord(trade_id="T1", symbol="NVDA", action="buy", decision_reason="r1"))
        mem.save(MemoryRecord(trade_id="T2", symbol="AAPL", action="sell", decision_reason="r2"))
        assert len(mem.by_symbol("NVDA")) == 1
        assert len(mem.by_symbol("AAPL")) == 1

    def test_by_outcome(self):
        mem = TradingMemory()
        mem.save(MemoryRecord(trade_id="T1", symbol="A", action="buy", decision_reason="r", outcome="win"))
        mem.save(MemoryRecord(trade_id="T2", symbol="B", action="buy", decision_reason="r", outcome="loss"))
        assert len(mem.by_outcome("win")) == 1
        assert len(mem.by_outcome("loss")) == 1

    def test_win_rate(self):
        mem = TradingMemory()
        mem.save(MemoryRecord(trade_id="T1", symbol="A", action="buy", decision_reason="r", outcome="win"))
        mem.save(MemoryRecord(trade_id="T2", symbol="B", action="buy", decision_reason="r", outcome="loss"))
        assert abs(mem.win_rate() - 0.5) < 1e-9

    def test_recent(self):
        mem = TradingMemory()
        for i in range(5):
            mem.save(MemoryRecord(trade_id=f"T{i}", symbol="A", action="buy", decision_reason="r"))
        assert len(mem.recent(3)) == 3

    def test_clear(self):
        mem = TradingMemory()
        mem.save(MemoryRecord(trade_id="T1", symbol="A", action="buy", decision_reason="r"))
        mem.clear()
        assert len(mem.history()) == 0

    def test_to_dict(self):
        record = MemoryRecord(
            trade_id="T1", symbol="NVDA", action="buy",
            decision_reason="momentum", outcome="win", pnl_pct=0.05,
        )
        d = record.to_dict()
        assert d["trade_id"] == "T1"
        assert d["pnl_pct"] == 0.05


# ====================================================================
# Trading Copilot (Integration)
# ====================================================================

class TestTradingCopilot:
    def test_analyze_generic(self):
        copilot = TradingCopilot()
        result = copilot.analyze("Analyze NVDA")
        assert result["analysis"] == "Analyze NVDA"

    def test_suggest_generic(self):
        copilot = TradingCopilot()
        result = copilot.suggest("buy")
        assert result["action"] == "buy"

    def test_market_analysis_integration(self):
        copilot = TradingCopilot()
        result = copilot.analyze_market(
            symbol="NVDA",
            price_momentum=0.8,
            volume_confirmation=0.6,
            volatility=0.2,
            sector_strength=0.7,
        )
        assert result.trend == "bullish"

    def test_position_analysis_integration(self):
        copilot = TradingCopilot()
        result = copilot.analyze_position(
            symbol="NVDA", exposure=0.2, momentum=0.7,
        )
        assert "Momentum Strong" in result.strengths

    def test_risk_check_integration(self):
        copilot = TradingCopilot()
        alerts = copilot.check_risks(exposure=1.2)
        assert len(alerts) > 0
        assert any(a.level == "critical" for a in alerts)

    def test_plan_trade_integration(self):
        copilot = TradingCopilot()
        plan = copilot.plan_trade(symbol="NVDA", current_price=100.0, signal=0.8)
        assert plan.action == "buy"

    def test_review_trade_integration(self):
        copilot = TradingCopilot()
        review = copilot.review_trade(
            trade_id="T1", symbol="NVDA",
            entry_price=100.0, exit_price=115.0,
            take_profit=115.0,
        )
        assert review.result == "win"

    def test_remember_integration(self):
        copilot = TradingCopilot()
        copilot.remember(
            trade_id="T1", symbol="NVDA", action="buy",
            decision_reason="momentum", outcome="win", pnl_pct=0.05,
        )
        assert len(copilot.memory_history()) == 1
        assert abs(copilot.memory_win_rate() - 1.0) < 1e-9


# ====================================================================
# Trading Copilot Service
# ====================================================================

class TestTradingCopilotService:
    def test_ask(self):
        service = TradingCopilotService()
        result = service.ask("Analyze NVDA")
        assert result["analysis"] == "Analyze NVDA"

    def test_service_wraps_copilot(self):
        service = TradingCopilotService()
        # Market analysis
        ma = service.analyze_market(
            symbol="AAPL",
            price_momentum=-0.8,
            volume_confirmation=-0.5,
            volatility=0.6,
            sector_strength=-0.5,
        )
        assert ma.trend == "bearish"

        # Position
        pa = service.analyze_position(symbol="AAPL", exposure=0.1)
        assert pa.symbol == "AAPL"

        # Risks
        alerts = service.check_risks(exposure=1.2)
        assert len(alerts) > 0

        # Trade plan
        plan = service.plan_trade(symbol="NVDA", current_price=100.0, signal=0.7)
        assert plan.action == "buy"

        # Review
        review = service.review_trade(
            trade_id="T1", symbol="NVDA",
            entry_price=100.0, exit_price=110.0,
        )
        assert review.result == "win"

        # Memory
        service.remember(
            trade_id="T1", symbol="NVDA", action="buy",
            decision_reason="momentum", outcome="win",
        )
        assert len(service.memory_history()) == 1

    def test_portfolio_overview_service(self):
        service = TradingCopilotService()
        p1 = PositionAnalysis(symbol="A", exposure=0.3)
        p2 = PositionAnalysis(symbol="B", exposure=0.4)
        overview = service.portfolio_overview([p1, p2])
        assert overview["position_count"] == 2
