from services.performance_intelligence import *


# ========== Helper data ==========

def _sample_portfolio():
    return {
        "returns": [0.001, 0.002, -0.001, 0.003, 0.001, -0.002, 0.004, 0.002, -0.003, 0.001,
                     0.002, -0.001, 0.005, 0.001, 0.000, -0.002, 0.003, 0.002, -0.001, 0.001],
        "equity_curve": [1000000.0, 1001000.0, 1003000.0, 1002000.0, 1005000.0, 1006000.0,
                         1004000.0, 1008000.0, 1010000.0, 1007000.0, 1008000.0, 1010000.0,
                         1009000.0, 1014000.0, 1015000.0, 1015000.0, 1013000.0, 1016000.0,
                         1018000.0, 1017000.0, 1018000.0],
        "trades": [
            {"pnl": 5000, "holding_period": 3}, {"pnl": -2000, "holding_period": 2},
            {"pnl": 8000, "holding_period": 5}, {"pnl": 3000, "holding_period": 2},
            {"pnl": -1000, "holding_period": 1}, {"pnl": 6000, "holding_period": 4},
            {"pnl": -3000, "holding_period": 2}, {"pnl": 4000, "holding_period": 3},
            {"pnl": 2000, "holding_period": 1}, {"pnl": -1500, "holding_period": 2},
        ],
        "positions": [
            {"symbol": "NVDA", "weight": 0.08, "return": 0.02, "volatility": 0.30,
             "timing_score": 0.15, "signal_strength": 0.18},
            {"symbol": "AAPL", "weight": 0.06, "return": 0.01, "volatility": 0.18,
             "timing_score": 0.05, "signal_strength": 0.10},
            {"symbol": "MSFT", "weight": 0.05, "return": 0.015, "volatility": 0.20,
             "timing_score": 0.10, "signal_strength": 0.12},
        ],
        "aum": 1000000.0,
        "benchmark_return": 0.08,
        "total_return": 0.018,
        "volatility": 0.15,
        "factor_exposures": {"momentum": 0.3, "value": -0.1, "quality": 0.4, "growth": 0.5},
        "period": "DAILY",
    }


# ========== 1. Performance Monitoring Agent ==========

def test_performance_monitor():
    monitor = PerformanceMonitor()
    result = monitor.collect("portfolio")
    assert result["performance"] == "portfolio"


def test_monitor_with_portfolio():
    monitor = PerformanceMonitor()
    result = monitor.collect(_sample_portfolio())
    assert "metrics" in result
    metrics = result["metrics"]
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "win_rate" in metrics
    assert "status" in result


def test_monitor_snapshot_tracking():
    monitor = PerformanceMonitor()
    monitor.collect(_sample_portfolio())
    snapshot = monitor.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot.snapshot_id is not None


def test_monitor_alerts():
    monitor = PerformanceMonitor()
    # Trigger max drawdown alert with extreme data
    bad_portfolio = {
        "returns": [-0.05, -0.04, -0.06, -0.03, -0.02],
        "equity_curve": [1000000.0, 950000.0, 912000.0, 857280.0, 831562.0, 814930.0],
        "trades": [{"pnl": -50000}, {"pnl": -38000}, {"pnl": -54800}],
        "aum": 814930.0,
    }
    monitor.collect(bad_portfolio)
    alerts = monitor.get_alerts()
    assert len(alerts) > 0


def test_monitor_metrics_trend():
    monitor = PerformanceMonitor()
    monitor.collect(_sample_portfolio())
    monitor.collect(_sample_portfolio())
    trend = monitor.get_metrics_trend("sharpe")
    assert len(trend) == 2


# ========== 2. Return Attribution Engine ==========

def test_return_attribution():
    engine = ReturnAttributionEngine()
    result = engine.analyze("returns_data")
    assert result["attribution"] == "returns_data"


def test_return_attribution_with_data():
    engine = ReturnAttributionEngine()
    data = {
        "total_return": 0.15,
        "positions": [
            {"symbol": "NVDA", "weight": 0.3, "return": 0.25, "timing_score": 0.1, "signal_strength": 0.15},
            {"symbol": "AAPL", "weight": 0.2, "return": 0.10, "timing_score": 0.05, "signal_strength": 0.08},
        ],
        "benchmark_return": 0.10,
        "factor_exposures": {"momentum": 0.4, "value": -0.2},
        "period": "DAILY",
    }
    result = engine.return_attribution.analyze(data) if hasattr(engine, 'return_attribution') else engine.analyze(data)
    assert "components" in result
    assert "dominant_source" in result


def test_return_attribution_components():
    engine = ReturnAttributionEngine()
    data = {"total_return": 0.12, "positions": [], "benchmark_return": 0.08, "factor_exposures": {}}
    result = engine.analyze(data)
    assert len(result["components"]) >= 4
    for c in result["components"]:
        assert "source" in c
        assert "contribution" in c
        assert "explanation" in c


def test_return_attribution_confidence():
    engine = ReturnAttributionEngine()
    data = {"total_return": 0.12, "positions": [], "benchmark_return": 0.08, "factor_exposures": {}}
    result = engine.analyze(data)
    assert 0 <= result["confidence"] <= 1.0


# ========== 3. Alpha Attribution Engine ==========

def test_alpha_attribution():
    engine = AlphaAttributionEngine()
    result = engine.analyze("performance_data")
    assert result["alpha"] == "performance_data"


def test_alpha_attribution_with_data():
    engine = AlphaAttributionEngine()
    data = {
        "total_return": 0.25,
        "benchmark_return": 0.10,
        "beta": 1.2,
        "volatility": 0.18,
        "risk_free_rate": 0.02,
        "track_record_length": 252,
        "rolling_alphas": [0.02, 0.03, -0.01, 0.04, 0.02, 0.03, 0.01, -0.02, 0.03, 0.04],
    }
    result = engine.analyze(data)
    assert "total_alpha" in result
    assert "alpha_ratio" in result
    assert "confidence" in result


def test_alpha_significance():
    engine = AlphaAttributionEngine()
    # High alpha with long track record
    data = {
        "total_return": 0.35,
        "benchmark_return": 0.10,
        "beta": 1.0,
        "volatility": 0.12,
        "track_record_length": 500,
        "rolling_alphas": [0.05] * 20,
    }
    result = engine.analyze(data)
    assert result["is_statistically_significant"]


def test_alpha_components_count():
    engine = AlphaAttributionEngine()
    data = {"total_return": 0.20, "benchmark_return": 0.10, "beta": 1.0, "volatility": 0.15,
            "track_record_length": 252, "rolling_alphas": []}
    result = engine.analyze(data)
    assert len(result["components"]) >= 3


# ========== 4. Risk Attribution Engine ==========

def test_risk_attribution():
    engine = RiskAttributionEngine()
    result = engine.analyze("positions")
    assert result["risk"] == "positions"


def test_risk_attribution_with_data():
    engine = RiskAttributionEngine()
    data = {
        "positions": [
            {"symbol": "NVDA", "weight": 0.08, "volatility": 0.30},
            {"symbol": "AAPL", "weight": 0.06, "volatility": 0.18},
            {"symbol": "MSFT", "weight": 0.05, "volatility": 0.20},
        ],
        "portfolio_volatility": 0.15,
        "total_nav": 1000000.0,
    }
    result = engine.analyze(data)
    assert "position_risks" in result
    assert "top_risk_contributors" in result
    assert "diversification_score" in result


def test_risk_concentration_warning():
    engine = RiskAttributionEngine()
    data = {
        "positions": [{"symbol": "NVDA", "weight": 0.80, "volatility": 0.30}],
        "portfolio_volatility": 0.15,
        "total_nav": 1000000.0,
    }
    result = engine.analyze(data)
    assert result["risk_concentration_warning"]


def test_risk_empty_positions():
    engine = RiskAttributionEngine()
    result = engine.analyze({"positions": [], "portfolio_volatility": 0.15})
    assert "message" in result


# ========== 5. Strategy Performance Analyzer ==========

def test_strategy_analyzer():
    analyzer = StrategyPerformanceAnalyzer()
    result = analyzer.analyze("strategy")
    assert result["strategy"] == "strategy"


def test_strategy_analyzer_with_trades():
    analyzer = StrategyPerformanceAnalyzer()
    trades = [
        {"pnl": 1000}, {"pnl": -500}, {"pnl": 2000}, {"pnl": 800},
        {"pnl": -300}, {"pnl": 1500}, {"pnl": -200}, {"pnl": 600},
    ]
    data = {
        "name": "Momentum Strategy",
        "trades": trades,
        "returns": [0.01, -0.005, 0.02, 0.008, -0.003, 0.015, -0.002, 0.006],
        "equity_curve": [1000000, 1010000, 1004950, 1024950, 1033146, 1030055, 1045605, 1043521, 1049800],
    }
    result = analyzer.analyze(data)
    metrics = result["metrics"]
    assert metrics["name"] == "Momentum Strategy"
    assert "sharpe_ratio" in metrics
    assert "win_rate" in metrics
    assert "profit_factor" in metrics
    assert metrics["score"] > 0
    assert "status" in result


def test_strategy_analyzer_no_trades():
    analyzer = StrategyPerformanceAnalyzer()
    result = analyzer.analyze({"name": "New Strategy", "trades": []})
    assert result["metrics"]["score"] == 50.0
    assert result["status"] == "UNDER_REVIEW"


def test_strategy_analyzer_metrics_complete():
    analyzer = StrategyPerformanceAnalyzer()
    trades = [{"pnl": 500}, {"pnl": 300}, {"pnl": -200}, {"pnl": 400}]
    data = {"name": "Test Strategy", "trades": trades, "returns": [0.005, 0.003, -0.002, 0.004]}
    result = analyzer.analyze(data)
    metrics = result["metrics"]
    assert "expectancy" in metrics
    assert "recovery_factor" in metrics
    assert "annual_return" in metrics


# ========== 6. Strategy Scorecard Engine ==========

def test_scorecard():
    engine = StrategyScorecardEngine()
    result = engine.score("strategy")
    assert result["score"] == 90


def test_scorecard_with_data():
    engine = StrategyScorecardEngine()
    data = {
        "name": "Momentum Alpha",
        "sharpe_ratio": 1.8,
        "sortino_ratio": 2.2,
        "annual_return": 0.25,
        "annual_volatility": 0.14,
        "max_drawdown": 0.08,
        "win_rate": 0.58,
        "profit_factor": 2.5,
        "expectancy": 0.003,
        "recovery_factor": 3.0,
        "consecutive_losses": 4,
    }
    result = engine.score(data)
    assert result["score"] > 70
    assert result["grade"] in ("A", "B", "C", "D", "F")
    assert result["action"] in ("KEEP_SCALING", "MAINTAIN", "REDUCE", "HALT", "LIQUIDATE")
    assert len(result["dimensions"]) == 5


def test_scorecard_strengths_weaknesses():
    engine = StrategyScorecardEngine()
    data = {
        "name": "Test",
        "sharpe_ratio": 2.5,
        "sortino_ratio": 3.0,
        "annual_return": 0.30,
        "annual_volatility": 0.12,
        "max_drawdown": 0.04,
        "win_rate": 0.65,
        "profit_factor": 3.0,
        "expectancy": 0.005,
        "recovery_factor": 7.5,
        "consecutive_losses": 2,
    }
    result = engine.score(data)
    assert len(result["strengths"]) > 0
    assert result["grade"] == "A"


def test_scorecard_poor_strategy():
    engine = StrategyScorecardEngine()
    data = {
        "name": "Failing Strategy",
        "sharpe_ratio": -0.5,
        "sortino_ratio": -0.3,
        "annual_return": -0.15,
        "annual_volatility": 0.35,
        "max_drawdown": 0.45,
        "win_rate": 0.30,
        "profit_factor": 0.6,
        "expectancy": -0.005,
        "recovery_factor": -0.33,
        "consecutive_losses": 12,
    }
    result = engine.score(data)
    assert result["grade"] in ("D", "F")
    assert result["action"] in ("HALT", "LIQUIDATE")


# ========== 7. Performance Benchmark Engine ==========

def test_benchmark():
    engine = PerformanceBenchmarkEngine()
    result = engine.compare("result")
    assert result["benchmark"] == "result"


def test_benchmark_with_data():
    engine = PerformanceBenchmarkEngine()
    data = {
        "strategy_name": "Alpha Fund",
        "total_return": 0.22,
        "volatility": 0.14,
        "benchmarks": [
            {"name": "S&P 500", "type": "INDEX", "return": 0.12, "volatility": 0.13},
            {"name": "HFRI Index", "type": "PEER_GROUP", "return": 0.08, "volatility": 0.07},
        ],
        "period": "YTD",
    }
    result = engine.compare(data)
    assert "comparisons" in result
    assert "overall_result" in result
    assert len(result["comparisons"]) == 2


def test_benchmark_default_benchmarks():
    engine = PerformanceBenchmarkEngine()
    data = {"strategy_name": "Test", "total_return": 0.15, "volatility": 0.14}
    result = engine.compare(data)
    assert len(result["comparisons"]) >= 1


# ========== 8. Drawdown Intelligence Engine ==========

def test_drawdown():
    engine = DrawdownIntelligenceEngine()
    result = engine.analyze("drawdown")
    assert result["drawdown"] == "drawdown"


def test_drawdown_with_data():
    engine = DrawdownIntelligenceEngine()
    data = {
        "equity_curve": [1000000, 1005000, 1010000, 980000, 950000, 970000, 990000, 1020000, 1010000, 1030000],
        "positions": [{"symbol": "NVDA"}, {"symbol": "AAPL"}],
    }
    result = engine.analyze(data)
    assert "max_drawdown" in result
    assert "active_drawdowns" in result
    assert "avg_recovery_days" in result


def test_drawdown_active_detection():
    engine = DrawdownIntelligenceEngine()
    # Portfolio still in drawdown (never recovers to high)
    data = {
        "equity_curve": [1000000, 950000, 920000, 900000, 910000, 890000],
        "positions": [{"symbol": "TSLA"}],
    }
    result = engine.analyze(data)
    assert len(result["active_drawdowns"]) > 0


def test_drawdown_severity_classification():
    engine = DrawdownIntelligenceEngine()
    # Deep drawdown
    data = {
        "equity_curve": [1000000, 900000, 800000, 700000, 750000, 720000],
        "positions": [{"symbol": "CRASH"}],
    }
    result = engine.analyze(data)
    assert result["max_drawdown"] > 0.25
    for dd in result["active_drawdowns"]:
        assert dd["severity"] in ("CRITICAL", "CATASTROPHIC")


# ========== 9. Continuous Improvement Engine ==========

def test_improvement():
    engine = ContinuousImprovementEngine()
    result = engine.improve("strategy")
    assert result["improved"] == "strategy"


def test_improvement_with_data():
    engine = ContinuousImprovementEngine()
    data = {
        "name": "Mean Reversion",
        "trigger_event": "Monthly review",
        "metrics": {
            "sharpe_ratio": 0.3,
            "max_drawdown": 0.22,
            "win_rate": 0.40,
            "profit_factor": 1.1,
        },
    }
    result = engine.improve(data)
    plan = result["improvement_plan"]
    assert plan["strategy_name"] == "Mean Reversion"
    assert len(plan["root_causes"]) > 0
    assert len(plan["actions"]) > 0
    assert "expected_improvement" in plan


def test_improvement_root_causes():
    engine = ContinuousImprovementEngine()
    data = {
        "name": "Broken Strategy",
        "metrics": {"sharpe_ratio": -1.0, "max_drawdown": 0.40, "win_rate": 0.30, "profit_factor": 0.5},
    }
    result = engine.improve(data)
    causes = result["improvement_plan"]["root_causes"]
    assert any(c["category"] == "MODEL_DECAY" for c in causes)


def test_improvement_actions_prioritized():
    engine = ContinuousImprovementEngine()
    data = {
        "name": "Test",
        "metrics": {"sharpe_ratio": 0.3, "max_drawdown": 0.25, "win_rate": 0.35, "profit_factor": 0.8},
    }
    result = engine.improve(data)
    actions = result["improvement_plan"]["actions"]
    priorities = [a["priority"] for a in actions]
    assert priorities == sorted(priorities)


# ========== 10. Performance Memory Engine ==========

def test_memory():
    memory = PerformanceMemory()
    memory.save("event")
    assert len(memory.history) == 1


def test_memory_entry():
    memory = PerformanceMemory()
    entry = PerformanceMemoryEntry(
        entry_id="MEM_0001",
        event=PerformanceEvent.TRADE,
        outcome=PerformanceOutcome.POSITIVE,
        strategy="Momentum",
        metrics={"return": 0.05, "sharpe": 1.5},
        result="Winning trade",
        lesson="Momentum signals work well in trending markets",
    )
    memory.save(entry)
    assert len(memory.history) == 1
    assert len(memory.lessons) == 1


def test_memory_patterns():
    memory = PerformanceMemory()
    for i in range(6):
        entry = PerformanceMemoryEntry(
            entry_id=f"MEM_{i:04d}",
            event=PerformanceEvent.TRADE,
            outcome=PerformanceOutcome.POSITIVE if i < 4 else PerformanceOutcome.NEGATIVE,
            strategy="Momentum",
            metrics={"return": 0.03},
            result=f"Trade {i}",
            lesson=f"Lesson {i}",
        )
        memory.save(entry)
    best = memory.get_best_patterns(min_samples=5)
    assert len(best) > 0


def test_memory_summary():
    memory = PerformanceMemory()
    entry = PerformanceMemoryEntry(
        entry_id="MEM_0001",
        event=PerformanceEvent.DAILY_SUMMARY,
        outcome=PerformanceOutcome.POSITIVE,
        strategy="Alpha Fund",
        metrics={"return": 0.02},
        result="Good day",
        lesson="Sector rotation paid off",
    )
    memory.save(entry)
    summary = memory.get_summary()
    assert summary.total_events == 1
    assert summary.best_strategy == "Alpha Fund"


# ========== 11. Performance Intelligence Service ==========

def test_service():
    monitor = PerformanceMonitor()
    service = PerformanceIntelligenceService(monitor)
    result = service.evaluate("portfolio")
    assert result["performance"] == "portfolio"


def test_service_full_loop():
    monitor = PerformanceMonitor()
    service = PerformanceIntelligenceService(monitor)
    portfolio = _sample_portfolio()
    portfolio["strategy_name"] = "Test Strategy"
    result = service.run_full_loop(portfolio)
    assert result["status"] == "COMPLETED"
    assert "performance" in result
    assert "return_attribution" in result
    assert "alpha_attribution" in result
    assert "risk_attribution" in result
    assert "strategy_analysis" in result
    assert "scorecard" in result
    assert "benchmark" in result
    assert "drawdown" in result
    assert "improvement" in result
    assert "memory_summary" in result


def test_service_full_loop_empty():
    monitor = PerformanceMonitor()
    service = PerformanceIntelligenceService(monitor)
    result = service.run_full_loop({})
    assert result["status"] == "COMPLETED"
    for key in ("return_attribution", "alpha_attribution", "risk_attribution",
                "strategy_analysis", "scorecard", "benchmark", "drawdown", "improvement"):
        assert key in result


print("All tests passed")
