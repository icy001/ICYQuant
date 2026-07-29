"""Performance Intelligence Service - orchestrates the full autonomous performance analysis loop."""

from typing import Any, Dict, List, Optional

from .monitor import PerformanceMonitor
from .return_attribution import ReturnAttributionEngine
from .alpha import AlphaAttributionEngine
from .risk import RiskAttributionEngine
from .analyzer import StrategyPerformanceAnalyzer
from .scorecard import StrategyScorecardEngine
from .benchmark import PerformanceBenchmarkEngine
from .drawdown import DrawdownIntelligenceEngine
from .improvement import ContinuousImprovementEngine
from .memory import PerformanceMemory, PerformanceMemoryEntry, PerformanceEvent, PerformanceOutcome


class PerformanceIntelligenceService:
    """Performance Intelligence Service.

    Orchestrates the full autonomous performance intelligence loop:
    1. Performance Monitoring
    2. Return Attribution
    3. Alpha Attribution
    4. Risk Attribution
    5. Strategy Analysis
    6. Strategy Scorecard
    7. Benchmark Comparison
    8. Drawdown Intelligence
    9. Continuous Improvement
    10. Performance Memory
    """

    def __init__(self, monitor):
        self.monitor = monitor
        self.return_attribution = ReturnAttributionEngine()
        self.alpha_attribution = AlphaAttributionEngine()
        self.risk_attribution = RiskAttributionEngine()
        self.analyzer = StrategyPerformanceAnalyzer()
        self.scorecard = StrategyScorecardEngine()
        self.benchmark = PerformanceBenchmarkEngine()
        self.drawdown = DrawdownIntelligenceEngine()
        self.improvement = ContinuousImprovementEngine()
        self.memory = PerformanceMemory()

    def evaluate(self, portfolio) -> Dict[str, Any]:
        """Evaluate portfolio performance.

        Args:
            portfolio: Portfolio data to evaluate.

        Returns:
            Dict with performance evaluation.
        """
        return self.monitor.collect(portfolio)

    def run_full_loop(self, portfolio_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the complete autonomous performance intelligence loop.

        Steps:
        1. Collect performance metrics
        2. Attribute returns
        3. Attribute alpha
        4. Attribute risk
        5. Analyze strategy performance
        6. Generate scorecard
        7. Compare against benchmarks
        8. Analyze drawdowns
        9. Generate improvement plan
        10. Save to memory
        """
        if portfolio_data is None:
            portfolio_data = {}

        strategy_name = portfolio_data.get("strategy_name", "Portfolio")

        # Step 1: Collect performance metrics
        performance = self.monitor.collect(portfolio_data)

        # Step 2: Return attribution
        returns_data = {
            "total_return": portfolio_data.get("total_return", 0.0),
            "positions": portfolio_data.get("positions", []),
            "benchmark_return": portfolio_data.get("benchmark_return", 0.0),
            "factor_exposures": portfolio_data.get("factor_exposures", {}),
            "period": portfolio_data.get("period", "DAILY"),
        }
        return_attribution = self.return_attribution.analyze(returns_data)

        # Step 3: Alpha attribution
        alpha_data = {
            "total_return": portfolio_data.get("total_return", 0.0),
            "benchmark_return": portfolio_data.get("benchmark_return", 0.0),
            "beta": portfolio_data.get("beta", 1.0),
            "volatility": portfolio_data.get("volatility", 0.15),
            "risk_free_rate": 0.02,
            "track_record_length": portfolio_data.get("track_record_length", 252),
            "rolling_alphas": portfolio_data.get("rolling_alphas", []),
            "smart_beta_contribution": portfolio_data.get("smart_beta_contribution", 0.0),
        }
        alpha_attribution = self.alpha_attribution.analyze(alpha_data)

        # Step 4: Risk attribution
        risk_data = {
            "positions": portfolio_data.get("positions", []),
            "portfolio_volatility": portfolio_data.get("volatility", 0.15),
            "total_nav": portfolio_data.get("total_nav", portfolio_data.get("aum", 1000000.0)),
        }
        risk_attribution = self.risk_attribution.analyze(risk_data)

        # Step 5: Strategy analysis
        strategy_data = {
            "name": strategy_name,
            "trades": portfolio_data.get("trades", []),
            "returns": portfolio_data.get("returns", []),
            "equity_curve": portfolio_data.get("equity_curve", []),
            "max_drawdown": portfolio_data.get("max_drawdown", 0.0),
        }
        strategy_analysis = self.analyzer.analyze(strategy_data)

        # Step 6: Generate scorecard
        metrics = strategy_analysis.get("metrics", {})
        scorecard_data = {
            "name": strategy_name,
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "annual_return": metrics.get("annual_return", 0.0),
            "annual_volatility": metrics.get("annual_volatility", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "win_rate": metrics.get("win_rate", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "expectancy": metrics.get("expectancy", 0.0),
            "recovery_factor": metrics.get("recovery_factor", 0.0),
            "consecutive_losses": metrics.get("consecutive_losses", 0),
        }
        scorecard_result = self.scorecard.score(scorecard_data)

        # Step 7: Benchmark comparison
        benchmark_data = {
            "strategy_name": strategy_name,
            "total_return": portfolio_data.get("total_return", 0.0),
            "volatility": portfolio_data.get("volatility", 0.15),
            "benchmarks": portfolio_data.get("benchmarks", []),
            "period": portfolio_data.get("period", "YTD"),
        }
        benchmark_result = self.benchmark.compare(benchmark_data)

        # Step 8: Drawdown analysis
        drawdown_data = {
            "equity_curve": portfolio_data.get("equity_curve", []),
            "positions": portfolio_data.get("positions", []),
            "dates": portfolio_data.get("dates", []),
        }
        drawdown_result = self.drawdown.analyze(drawdown_data)

        # Step 9: Continuous improvement
        improvement_data = {
            "name": strategy_name,
            "trigger_event": "Scheduled performance review",
            "metrics": metrics,
        }
        improvement_result = self.improvement.improve(improvement_data)

        # Step 10: Save to memory
        entry = PerformanceMemoryEntry(
            entry_id=f"MEM_{len(self.memory.history):04d}",
            event=PerformanceEvent.DAILY_SUMMARY,
            outcome=(PerformanceOutcome.POSITIVE
                     if portfolio_data.get("total_return", 0.0) > 0
                     else PerformanceOutcome.NEGATIVE),
            strategy=strategy_name,
            metrics={
                "return": portfolio_data.get("total_return", 0.0),
                "sharpe": metrics.get("sharpe_ratio", 0.0),
                "max_dd": metrics.get("max_drawdown", 0.0),
                "win_rate": metrics.get("win_rate", 0.0),
            },
            result=f"Score: {scorecard_result.get('score', 0):.0f}, Grade: {scorecard_result.get('grade', 'N/A')}",
            lesson=improvement_result.get("improvement_plan", {}).get("root_causes", [{}])[0].get("description",
                        "Continue monitoring") if improvement_result.get("improvement_plan", {}).get("root_causes")
                        else "Continue monitoring",
        )
        self.memory.save(entry)

        return {
            "performance": performance,
            "return_attribution": return_attribution,
            "alpha_attribution": alpha_attribution,
            "risk_attribution": risk_attribution,
            "strategy_analysis": strategy_analysis,
            "scorecard": scorecard_result,
            "benchmark": benchmark_result,
            "drawdown": drawdown_result,
            "improvement": improvement_result,
            "memory_summary": {
                "total_events": len(self.memory.history),
                "lessons_learned": len(self.memory.lessons),
            },
            "status": "COMPLETED",
        }
