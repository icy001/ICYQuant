from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EfficiencyRating(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ADEQUATE = "ADEQUATE"
    POOR = "POOR"
    INEFFICIENT = "INEFFICIENT"


@dataclass
class EfficiencyMetrics:
    capital_utilization: float  # 0-1
    return_on_capital: float
    risk_adjusted_return: float
    idle_capital_pct: float
    turnover_ratio: float
    cash_drag: float
    opportunity_cost: float


@dataclass
class EfficiencyAnalysis:
    analysis_id: str
    metrics: EfficiencyMetrics
    rating: EfficiencyRating
    total_capital: float
    deployed_capital: float
    idle_capital: float
    recommendations: List[str] = field(default_factory=list)
    summary: str = ""


class CapitalEfficiencyAnalyzer:
    """Capital Efficiency Analyzer - measures and optimizes capital utilization."""

    def __init__(self):
        self.analyses: List[EfficiencyAnalysis] = []
        self.analysis_count = 0

    def analyze(self, capital):
        """Analyze capital efficiency.

        Args:
            capital: Capital data (str, dict, or EfficiencyAnalysis).

        Returns:
            Dict containing efficiency analysis.
        """
        if isinstance(capital, EfficiencyAnalysis):
            return self._process_analysis(capital)
        if isinstance(capital, dict):
            return self._analyze_dict(capital)
        return {"efficiency": capital}

    def _process_analysis(self, analysis: EfficiencyAnalysis) -> dict:
        self.analyses.append(analysis)
        return self._to_dict(analysis)

    def _analyze_dict(self, data: dict) -> dict:
        self.analysis_count += 1

        total_capital = data.get("total_capital", data.get("aum", 1000000.0))
        deployed = data.get("deployed_capital", data.get("deployed", total_capital * 0.8))
        idle = total_capital - deployed

        # Calculate efficiency metrics
        capital_util = deployed / total_capital if total_capital > 0 else 0
        roc = data.get("return_on_capital", data.get("roc", data.get("return", 0.0)))
        risk = data.get("risk", data.get("volatility", 0.15))
        risk_adj_return = (roc - 0.02) / risk if risk > 0 else 0  # excess return / risk
        idle_pct = idle / total_capital if total_capital > 0 else 0
        turnover = data.get("turnover", data.get("turnover_ratio", 0.5))
        cash_drag = idle_pct * 0.03  # opportunity cost of idle cash
        opp_cost = idle * 0.08  # estimated missed return

        metrics = EfficiencyMetrics(
            capital_utilization=round(capital_util, 4),
            return_on_capital=round(roc, 4),
            risk_adjusted_return=round(risk_adj_return, 2),
            idle_capital_pct=round(idle_pct, 4),
            turnover_ratio=round(turnover, 4),
            cash_drag=round(cash_drag, 4),
            opportunity_cost=round(opp_cost, 2),
        )

        # Rating
        rating = self._determine_rating(metrics)

        # Recommendations
        recommendations = self._generate_recommendations(metrics, rating)

        analysis = EfficiencyAnalysis(
            analysis_id=f"EFF_{self.analysis_count:04d}",
            metrics=metrics,
            rating=rating,
            total_capital=round(total_capital, 2),
            deployed_capital=round(deployed, 2),
            idle_capital=round(idle, 2),
            recommendations=recommendations,
            summary=self._generate_summary(metrics, rating),
        )
        self.analyses.append(analysis)
        return self._to_dict(analysis)

    def _determine_rating(self, metrics: EfficiencyMetrics) -> EfficiencyRating:
        score = 0.0
        score += metrics.capital_utilization * 40  # max 40
        score += max(0, min(20, metrics.risk_adjusted_return * 10))  # max 20
        score += max(0, min(20, (1 - metrics.idle_capital_pct) * 20))  # max 20
        score += max(0, min(20, metrics.return_on_capital * 100))  # max 20

        if score >= 85:
            return EfficiencyRating.EXCELLENT
        if score >= 70:
            return EfficiencyRating.GOOD
        if score >= 50:
            return EfficiencyRating.ADEQUATE
        if score >= 30:
            return EfficiencyRating.POOR
        return EfficiencyRating.INEFFICIENT

    def _generate_recommendations(self, metrics: EfficiencyMetrics, rating: EfficiencyRating) -> List[str]:
        recs = []

        if metrics.capital_utilization < 0.60:
            recs.append(f"Low capital utilization ({metrics.capital_utilization:.0%}) - deploy idle capital")

        if metrics.idle_capital_pct > 0.10:
            recs.append(f"Excessive idle capital ({metrics.idle_capital_pct:.0%}) - reduce cash drag")

        if metrics.risk_adjusted_return < 0.5:
            recs.append(f"Low risk-adjusted return ({metrics.risk_adjusted_return:.1f}) - improve capital efficiency")

        if metrics.turnover_ratio > 2.0:
            recs.append(f"High turnover ({metrics.turnover_ratio:.1f}x) - consider reducing trading costs")

        if rating == EfficiencyRating.EXCELLENT:
            recs.append("Capital efficiency is excellent - maintain current strategy")

        return recs

    def _generate_summary(self, metrics: EfficiencyMetrics, rating: EfficiencyRating) -> str:
        return (
            f"Capital Efficiency: {rating.value}. "
            f"Utilization: {metrics.capital_utilization:.0%}, "
            f"ROC: {metrics.return_on_capital:.1%}, "
            f"Risk-adj return: {metrics.risk_adjusted_return:.1f}, "
            f"Idle: {metrics.idle_capital_pct:.0%}"
        )

    def _to_dict(self, analysis: EfficiencyAnalysis) -> dict:
        return {
            "efficiency": {
                "analysis_id": analysis.analysis_id,
                "metrics": {
                    "capital_utilization": analysis.metrics.capital_utilization,
                    "return_on_capital": analysis.metrics.return_on_capital,
                    "risk_adjusted_return": analysis.metrics.risk_adjusted_return,
                    "idle_capital_pct": analysis.metrics.idle_capital_pct,
                    "turnover_ratio": analysis.metrics.turnover_ratio,
                    "cash_drag": analysis.metrics.cash_drag,
                    "opportunity_cost": analysis.metrics.opportunity_cost,
                },
                "rating": analysis.rating.value,
                "total_capital": analysis.total_capital,
                "deployed_capital": analysis.deployed_capital,
                "idle_capital": analysis.idle_capital,
                "recommendations": analysis.recommendations,
                "summary": analysis.summary,
            }
        }

    def get_analysis(self) -> Optional[EfficiencyAnalysis]:
        """Get the latest efficiency analysis."""
        return self.analyses[-1] if self.analyses else None
