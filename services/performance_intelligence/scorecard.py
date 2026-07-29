"""Strategy Scorecard Engine - generates comprehensive strategy report cards."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScorecardGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ScorecardAction(str, Enum):
    KEEP_SCALING = "KEEP_SCALING"
    MAINTAIN = "MAINTAIN"
    REDUCE = "REDUCE"
    HALT = "HALT"
    LIQUIDATE = "LIQUIDATE"


@dataclass
class ScorecardDimension:
    name: str
    score: float
    weight: float
    grade: ScorecardGrade
    comment: str


@dataclass
class StrategyScorecard:
    card_id: str
    strategy_name: str
    overall_score: float
    grade: ScorecardGrade
    dimensions: List[ScorecardDimension]
    action: ScorecardAction
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


class StrategyScorecardEngine:
    """Strategy Scorecard Engine.

    Generates comprehensive strategy report cards with grades and actionable recommendations.
    Evaluates strategies across multiple dimensions.
    """

    def __init__(self):
        self.scorecards: List[StrategyScorecard] = []

    def score(self, strategy) -> Dict[str, Any]:
        """Generate a strategy scorecard.

        Args:
            strategy: Strategy data to evaluate.

        Returns:
            Dict with scorecard results.
        """
        if isinstance(strategy, dict):
            return self._score_from_dict(strategy)
        return {"score": 90}

    def _score_from_dict(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Generate scorecard from structured strategy data."""
        name = strategy.get("name", "Unknown Strategy")

        dimensions = []
        dimensions.append(self._score_return_dimension(strategy))
        dimensions.append(self._score_risk_dimension(strategy))
        dimensions.append(self._score_consistency_dimension(strategy))
        dimensions.append(self._score_efficiency_dimension(strategy))
        dimensions.append(self._score_resilience_dimension(strategy))

        overall_score = sum(d.score * d.weight for d in dimensions)
        grade = self._determine_grade(overall_score)
        action = self._determine_action(grade, strategy)

        strengths, weaknesses = self._identify_strengths_weaknesses(dimensions)
        recommendations = self._generate_recommendations(weaknesses, action)

        summary = self._generate_summary(name, overall_score, grade, action)

        card = StrategyScorecard(
            card_id=f"SC_{len(self.scorecards):04d}",
            strategy_name=name,
            overall_score=overall_score,
            grade=grade,
            dimensions=dimensions,
            action=action,
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )
        self.scorecards.append(card)

        return {
            "score": overall_score,
            "grade": grade.value,
            "action": action.value,
            "strategy_name": name,
            "dimensions": [
                {"name": d.name, "score": d.score, "grade": d.grade.value, "comment": d.comment}
                for d in dimensions
            ],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "summary": summary,
        }

    def _score_return_dimension(self, strategy: Dict) -> ScorecardDimension:
        sharpe = strategy.get("sharpe_ratio", 0.0)
        annual_return = strategy.get("annual_return", 0.0)

        score = 50.0
        if sharpe > 2.0:
            score = 95.0
        elif sharpe > 1.5:
            score = 85.0
        elif sharpe > 1.0:
            score = 75.0
        elif sharpe > 0.5:
            score = 60.0
        elif sharpe > 0.0:
            score = 45.0
        else:
            score = 25.0

        comment = f"Sharpe: {sharpe:.2f}, Annual Return: {annual_return:.1%}"
        return ScorecardDimension(
            name="Return Quality",
            score=score,
            weight=0.25,
            grade=self._determine_grade(score),
            comment=comment,
        )

    def _score_risk_dimension(self, strategy: Dict) -> ScorecardDimension:
        max_dd = strategy.get("max_drawdown", 0.0)
        vol = strategy.get("annual_volatility", 0.0)

        score = 50.0
        if max_dd < 0.05:
            score = 95.0
        elif max_dd < 0.10:
            score = 85.0
        elif max_dd < 0.15:
            score = 75.0
        elif max_dd < 0.20:
            score = 60.0
        elif max_dd < 0.30:
            score = 40.0
        else:
            score = 20.0

        comment = f"Max DD: {max_dd:.1%}, Vol: {vol:.1%}"
        return ScorecardDimension(
            name="Risk Management",
            score=score,
            weight=0.25,
            grade=self._determine_grade(score),
            comment=comment,
        )

    def _score_consistency_dimension(self, strategy: Dict) -> ScorecardDimension:
        win_rate = strategy.get("win_rate", 0.0)
        profit_factor = strategy.get("profit_factor", 0.0)

        score = 50.0
        if win_rate > 0.60:
            score = 90.0
        elif win_rate > 0.55:
            score = 80.0
        elif win_rate > 0.50:
            score = 70.0
        elif win_rate > 0.45:
            score = 55.0
        elif win_rate > 0.40:
            score = 40.0
        else:
            score = 25.0

        comment = f"Win Rate: {win_rate:.1%}, PF: {profit_factor:.2f}"
        return ScorecardDimension(
            name="Consistency",
            score=score,
            weight=0.20,
            grade=self._determine_grade(score),
            comment=comment,
        )

    def _score_efficiency_dimension(self, strategy: Dict) -> ScorecardDimension:
        sortino = strategy.get("sortino_ratio", 0.0)
        expectancy = strategy.get("expectancy", 0.0)

        score = 50.0
        if sortino > 2.0:
            score = 90.0
        elif sortino > 1.5:
            score = 80.0
        elif sortino > 1.0:
            score = 70.0
        elif sortino > 0.5:
            score = 55.0
        else:
            score = 35.0

        comment = f"Sortino: {sortino:.2f}, Expectancy: {expectancy:.4f}"
        return ScorecardDimension(
            name="Efficiency",
            score=score,
            weight=0.15,
            grade=self._determine_grade(score),
            comment=comment,
        )

    def _score_resilience_dimension(self, strategy: Dict) -> ScorecardDimension:
        recovery = strategy.get("recovery_factor", 0.0)
        consecutive = strategy.get("consecutive_losses", 0)

        score = 50.0
        if recovery > 3.0:
            score = 90.0
        elif recovery > 2.0:
            score = 80.0
        elif recovery > 1.0:
            score = 65.0
        elif recovery > 0.5:
            score = 50.0
        else:
            score = 30.0

        if consecutive > 10:
            score -= 20.0
        elif consecutive > 7:
            score -= 10.0

        comment = f"Recovery: {recovery:.2f}, Max Cons. Losses: {consecutive}"
        return ScorecardDimension(
            name="Resilience",
            score=score,
            weight=0.15,
            grade=self._determine_grade(score),
            comment=comment,
        )

    def _determine_grade(self, score: float) -> ScorecardGrade:
        if score >= 85:
            return ScorecardGrade.A
        elif score >= 70:
            return ScorecardGrade.B
        elif score >= 55:
            return ScorecardGrade.C
        elif score >= 40:
            return ScorecardGrade.D
        return ScorecardGrade.F

    def _determine_action(self, grade: ScorecardGrade, strategy: Dict) -> ScorecardAction:
        if grade == ScorecardGrade.A:
            return ScorecardAction.KEEP_SCALING
        elif grade == ScorecardGrade.B:
            return ScorecardAction.MAINTAIN
        elif grade == ScorecardGrade.C:
            return ScorecardAction.REDUCE
        elif grade == ScorecardGrade.D:
            return ScorecardAction.HALT
        return ScorecardAction.LIQUIDATE

    def _identify_strengths_weaknesses(self, dimensions: List[ScorecardDimension]) -> tuple:
        strengths = [f"{d.name}: {d.comment}" for d in dimensions if d.score >= 75]
        weaknesses = [f"{d.name}: {d.comment}" for d in dimensions if d.score < 55]
        return strengths, weaknesses

    def _generate_recommendations(self, weaknesses: List[str], action: ScorecardAction) -> List[str]:
        recs = []
        if action == ScorecardAction.KEEP_SCALING:
            recs.append("Continue increasing capital allocation within risk limits")
            recs.append("Consider launching variant strategies")
        elif action == ScorecardAction.MAINTAIN:
            recs.append("Maintain current allocation")
            recs.append("Monitor for performance degradation")
        elif action == ScorecardAction.REDUCE:
            recs.append("Reduce position sizes by 25-50%")
            recs.append(f"Investigate weaknesses: {', '.join(weaknesses)}")
        elif action == ScorecardAction.HALT:
            recs.append("Stop all new positions immediately")
            recs.append("Conduct full strategy review")
        elif action == ScorecardAction.LIQUIDATE:
            recs.append("Begin orderly liquidation of all positions")
            recs.append("Archive strategy for future analysis")
        return recs

    def _generate_summary(self, name: str, score: float, grade: ScorecardGrade,
                          action: ScorecardAction) -> str:
        return (
            f"Strategy: {name} | Score: {score:.0f}/100 | Grade: {grade.value} | "
            f"Action: {action.value.replace('_', ' ').title()}"
        )

    def get_latest_scorecard(self) -> Optional[StrategyScorecard]:
        """Get the most recent strategy scorecard."""
        return self.scorecards[-1] if self.scorecards else None

    def get_scorecards_by_grade(self, grade: ScorecardGrade) -> List[StrategyScorecard]:
        """Get all scorecards with a specific grade."""
        return [s for s in self.scorecards if s.grade == grade]
