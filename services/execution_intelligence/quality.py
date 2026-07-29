from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityGrade(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"
    UNACCEPTABLE = "UNACCEPTABLE"


@dataclass
class ExecutionMetrics:
    order_id: str
    symbol: str
    side: str
    total_quantity: int
    filled_quantity: int
    avg_execution_price: float
    arrival_price: float
    vwap_benchmark: float
    implementation_shortfall_bps: float
    fill_rate: float
    duration_seconds: float
    slippage_vs_arrival_bps: float
    slippage_vs_vwap_bps: float
    venue_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class QualityReport:
    order_id: str
    symbol: str
    overall_grade: QualityGrade
    implementation_shortfall_bps: float
    fill_rate_grade: str
    timing_grade: str
    cost_efficiency_grade: str
    recommendations: List[str] = field(default_factory=list)


class ExecutionQualityAnalyzer:
    """Execution Quality Analyzer - evaluates execution quality post-trade."""

    def __init__(self):
        self.excellent_threshold_bps = 2.0
        self.good_threshold_bps = 5.0
        self.poor_threshold_bps = 20.0
        self.min_acceptable_fill_rate = 0.90

    def analyze(self, execution):
        """Analyze execution quality.

        Args:
            execution: Execution data - can be ExecutionMetrics dataclass or dict/symbol.

        Returns:
            Dict containing quality analysis.
        """
        if isinstance(execution, ExecutionMetrics):
            return self._analyze_execution(execution)
        return {"quality": execution}

    def _analyze_execution(self, metrics: ExecutionMetrics) -> dict:
        grade = self._determine_grade(metrics)
        fill_rate_grade = self._grade_fill_rate(metrics.fill_rate)
        timing_grade = self._grade_timing(metrics)
        cost_efficiency = self._grade_cost(metrics.implementation_shortfall_bps)

        recommendations = self._generate_recommendations(metrics, grade)

        return {
            "quality": {
                "order_id": metrics.order_id,
                "symbol": metrics.symbol,
                "overall_grade": grade.value,
                "implementation_shortfall_bps": round(metrics.implementation_shortfall_bps, 2),
                "fill_rate": round(metrics.fill_rate, 4),
                "fill_rate_grade": fill_rate_grade,
                "timing_grade": timing_grade,
                "cost_efficiency_grade": cost_efficiency,
                "slippage_vs_arrival_bps": round(metrics.slippage_vs_arrival_bps, 2),
                "slippage_vs_vwap_bps": round(metrics.slippage_vs_vwap_bps, 2),
                "recommendations": recommendations,
            }
        }

    def _determine_grade(self, metrics: ExecutionMetrics) -> QualityGrade:
        abs_shortfall = abs(metrics.implementation_shortfall_bps)

        if metrics.fill_rate < self.min_acceptable_fill_rate:
            return QualityGrade.POOR

        if abs_shortfall <= self.excellent_threshold_bps:
            return QualityGrade.EXCELLENT
        elif abs_shortfall <= self.good_threshold_bps:
            return QualityGrade.GOOD
        elif abs_shortfall <= self.poor_threshold_bps:
            return QualityGrade.AVERAGE
        return QualityGrade.POOR

    def _grade_fill_rate(self, fill_rate: float) -> str:
        if fill_rate >= 0.98:
            return "EXCELLENT"
        elif fill_rate >= 0.95:
            return "GOOD"
        elif fill_rate >= 0.90:
            return "ADEQUATE"
        return "POOR"

    def _grade_timing(self, metrics: ExecutionMetrics) -> str:
        """Grade execution timing quality."""
        avg_qty_per_second = metrics.filled_quantity / max(metrics.duration_seconds, 1)
        if avg_qty_per_second > 100:
            return "FAST"
        elif avg_qty_per_second > 10:
            return "NORMAL"
        return "SLOW"

    def _grade_cost(self, shortfall_bps: float) -> str:
        abs_sf = abs(shortfall_bps)
        if abs_sf <= self.excellent_threshold_bps:
            return "EXCELLENT"
        elif abs_sf <= self.good_threshold_bps:
            return "GOOD"
        elif abs_sf <= self.poor_threshold_bps:
            return "AVERAGE"
        return "HIGH"

    def _generate_recommendations(self, metrics: ExecutionMetrics, grade: QualityGrade) -> List[str]:
        recommendations = []
        if metrics.fill_rate < self.min_acceptable_fill_rate:
            recommendations.append("Consider increasing participation rate for better fill")
        if abs(metrics.slippage_vs_arrival_bps) > self.good_threshold_bps:
            recommendations.append("Review arrival price benchmark and execution timing")
        if grade == QualityGrade.POOR:
            recommendations.append("Significant execution quality issues - review algorithm choice")
        if not recommendations:
            recommendations.append("Execution quality is satisfactory")
        return recommendations
