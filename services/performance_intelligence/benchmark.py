"""Performance Benchmark Engine - compares strategy performance against benchmarks."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BenchmarkType(str, Enum):
    INDEX = "INDEX"
    PEER_GROUP = "PEER_GROUP"
    ALTERNATIVE_STRATEGY = "ALTERNATIVE_STRATEGY"
    ABSOLUTE_RETURN = "ABSOLUTE_RETURN"
    RISK_FREE = "RISK_FREE"


class ComparisonResult(str, Enum):
    OUTPERFORM = "OUTPERFORM"
    MATCH = "MATCH"
    UNDERPERFORM = "UNDERPERFORM"
    SIGNIFICANTLY_UNDER = "SIGNIFICANTLY_UNDER"


@dataclass
class BenchmarkComparison:
    benchmark_name: str
    benchmark_type: BenchmarkType
    strategy_return: float
    benchmark_return: float
    excess_return: float
    tracking_error: float
    information_ratio: float
    beta: float
    correlation: float
    up_capture: float
    down_capture: float
    result: ComparisonResult


@dataclass
class BenchmarkReport:
    report_id: str
    strategy_name: str
    period: str
    comparisons: List[BenchmarkComparison]
    overall_result: ComparisonResult
    best_benchmark: str
    worst_benchmark: str


class PerformanceBenchmarkEngine:
    """Performance Benchmark Engine.

    Compares strategy performance against indices, peers, and alternative strategies.
    Provides relative performance assessment.
    """

    def __init__(self):
        self.reports: List[BenchmarkReport] = []

    def compare(self, result) -> Dict[str, Any]:
        """Compare performance against benchmarks.

        Args:
            result: Performance result to compare.

        Returns:
            Dict with benchmark comparison results.
        """
        if isinstance(result, dict):
            return self._compare_from_dict(result)
        return {"benchmark": result}

    def _compare_from_dict(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Compare performance from structured data."""
        strategy_name = result.get("strategy_name", "Unknown")
        strategy_return = result.get("total_return", 0.0)
        strategy_vol = result.get("volatility", 0.15)
        benchmarks = result.get("benchmarks", [])

        if not benchmarks:
            benchmarks = [
                {"name": "S&P 500", "type": "INDEX", "return": 0.10, "volatility": 0.14},
                {"name": "Risk-Free", "type": "RISK_FREE", "return": 0.02, "volatility": 0.0},
            ]

        comparisons = []
        for bm in benchmarks:
            bm_return = bm.get("return", 0.0)
            bm_vol = bm.get("volatility", 0.0)
            bm_type = BenchmarkType(bm.get("type", "INDEX"))
            bm_name = bm.get("name", "Unknown Benchmark")

            excess = strategy_return - bm_return
            tracking_error = self._compute_tracking_error(strategy_vol, bm_vol)
            info_ratio = excess / tracking_error if tracking_error > 0 else 0.0
            beta = strategy_vol / bm_vol if bm_vol > 0 else 1.0
            correlation = bm.get("correlation", 0.7)

            up_capture = self._compute_up_capture(
                result.get("up_periods", []), bm.get("up_periods", []))
            down_capture = self._compute_down_capture(
                result.get("down_periods", []), bm.get("down_periods", []))

            comp_result = self._determine_comparison(excess, info_ratio)

            comparisons.append(BenchmarkComparison(
                benchmark_name=bm_name,
                benchmark_type=bm_type,
                strategy_return=strategy_return,
                benchmark_return=bm_return,
                excess_return=excess,
                tracking_error=tracking_error,
                information_ratio=info_ratio,
                beta=beta,
                correlation=correlation,
                up_capture=up_capture,
                down_capture=down_capture,
                result=comp_result,
            ))

        overall = self._determine_overall(comparisons)
        best = max(comparisons, key=lambda c: c.excess_return).benchmark_name
        worst = min(comparisons, key=lambda c: c.excess_return).benchmark_name

        report = BenchmarkReport(
            report_id=f"BM_{len(self.reports):04d}",
            strategy_name=strategy_name,
            period=result.get("period", "YTD"),
            comparisons=comparisons,
            overall_result=overall,
            best_benchmark=best,
            worst_benchmark=worst,
        )
        self.reports.append(report)

        return {
            "benchmark": result,
            "strategy_name": strategy_name,
            "comparisons": [
                {
                    "benchmark": c.benchmark_name,
                    "type": c.benchmark_type.value,
                    "strategy_return": c.strategy_return,
                    "benchmark_return": c.benchmark_return,
                    "excess_return": c.excess_return,
                    "information_ratio": c.information_ratio,
                    "beta": c.beta,
                    "up_capture": c.up_capture,
                    "down_capture": c.down_capture,
                    "result": c.result.value,
                }
                for c in comparisons
            ],
            "overall_result": overall.value,
            "best_vs_benchmark": best,
            "worst_vs_benchmark": worst,
        }

    def _compute_tracking_error(self, strategy_vol: float, benchmark_vol: float) -> float:
        correlation = 0.7
        return (strategy_vol**2 + benchmark_vol**2 -
                2 * correlation * strategy_vol * benchmark_vol) ** 0.5

    def _compute_up_capture(self, strategy_up: List[float], benchmark_up: List[float]) -> float:
        if not benchmark_up or not strategy_up:
            return 1.0
        strat_avg = sum(strategy_up) / len(strategy_up) if strategy_up else 0.0
        bench_avg = sum(benchmark_up) / len(benchmark_up) if benchmark_up else 0.001
        return strat_avg / bench_avg if bench_avg != 0 else 1.0

    def _compute_down_capture(self, strategy_down: List[float], benchmark_down: List[float]) -> float:
        if not benchmark_down or not strategy_down:
            return 1.0
        strat_avg = sum(strategy_down) / len(strategy_down) if strategy_down else 0.0
        bench_avg = sum(benchmark_down) / len(benchmark_down) if benchmark_down else 0.001
        return strat_avg / bench_avg if bench_avg != 0 else 1.0

    def _determine_comparison(self, excess: float, info_ratio: float) -> ComparisonResult:
        if excess > 0.03 or info_ratio > 1.0:
            return ComparisonResult.OUTPERFORM
        elif excess > -0.01:
            return ComparisonResult.MATCH
        elif excess > -0.05:
            return ComparisonResult.UNDERPERFORM
        return ComparisonResult.SIGNIFICANTLY_UNDER

    def _determine_overall(self, comparisons: List[BenchmarkComparison]) -> ComparisonResult:
        results = [c.result for c in comparisons]
        if ComparisonResult.SIGNIFICANTLY_UNDER in results:
            return ComparisonResult.SIGNIFICANTLY_UNDER
        if ComparisonResult.UNDERPERFORM in results:
            return ComparisonResult.UNDERPERFORM
        if all(r == ComparisonResult.OUTPERFORM for r in results):
            return ComparisonResult.OUTPERFORM
        return ComparisonResult.MATCH

    def get_latest_report(self) -> Optional[BenchmarkReport]:
        """Get the most recent benchmark report."""
        return self.reports[-1] if self.reports else None

    def get_outperforming_comparisons(self) -> List[BenchmarkComparison]:
        """Get all comparisons where strategy outperformed."""
        if not self.reports:
            return []
        return [c for c in self.reports[-1].comparisons
                if c.result == ComparisonResult.OUTPERFORM]
