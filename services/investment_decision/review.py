from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewOutcome(str, Enum):
    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    INCORRECT = "INCORRECT"
    INCONCLUSIVE = "INCONCLUSIVE"


class ErrorSource(str, Enum):
    NONE = "NONE"
    THESIS_ERROR = "THESIS_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    TIMING_ERROR = "TIMING_ERROR"
    RISK_ASSESSMENT_ERROR = "RISK_ASSESSMENT_ERROR"
    MARKET_REGIME_ERROR = "MARKET_REGIME_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass
class DecisionReview:
    review_id: str
    decision_id: str
    symbol: str
    original_decision: str
    predicted_outcome: str
    actual_outcome: str
    prediction_correct: bool
    outcome: ReviewOutcome
    error_source: ErrorSource
    analysis: str
    lessons_learned: List[str] = field(default_factory=list)
    improvement_actions: List[str] = field(default_factory=list)
    review_score: float = 0.0  # 0-100


class DecisionReviewEngine:
    """Decision Review Engine - conducts post-mortem analysis on investment decisions."""

    def __init__(self):
        self.reviews: List[DecisionReview] = []
        self.review_count = 0

    def review(self, result):
        """Review an investment decision outcome.

        Args:
            result: The result to review (str, dict, or DecisionReview).

        Returns:
            Dict containing the review analysis.
        """
        if isinstance(result, DecisionReview):
            return self._process_review(result)
        if isinstance(result, dict):
            return self._review_dict(result)
        return {"review": result}

    def _process_review(self, review: DecisionReview) -> dict:
        self.reviews.append(review)
        return self._to_dict(review)

    def _review_dict(self, data: dict) -> dict:
        self.review_count += 1

        decision_id = data.get("decision_id", f"DEC_{self.review_count}")
        symbol = data.get("symbol", "UNKNOWN")
        original_decision = data.get("decision", "UNKNOWN")
        predicted_outcome = data.get("predicted_outcome", "")
        actual_outcome = data.get("actual_outcome", "")
        conviction = data.get("conviction_score", 50)

        # Compare prediction vs reality
        prediction_correct = self._compare_outcomes(predicted_outcome, actual_outcome)
        outcome = self._determine_outcome(prediction_correct, predicted_outcome, actual_outcome)
        error_source = self._identify_error_source(prediction_correct, original_decision, actual_outcome, data)

        # Generate analysis
        analysis = self._generate_analysis(
            original_decision, conviction, predicted_outcome, actual_outcome, prediction_correct
        )

        # Extract lessons
        lessons = self._extract_lessons(prediction_correct, error_source, data)

        # Generate improvement actions
        improvements = self._generate_improvements(error_source)

        review_score = self._calculate_review_score(prediction_correct, outcome, data)

        review = DecisionReview(
            review_id=f"REV_{self.review_count:04d}",
            decision_id=decision_id,
            symbol=symbol,
            original_decision=original_decision,
            predicted_outcome=predicted_outcome,
            actual_outcome=actual_outcome,
            prediction_correct=prediction_correct,
            outcome=outcome,
            error_source=error_source,
            analysis=analysis,
            lessons_learned=lessons,
            improvement_actions=improvements,
            review_score=round(review_score, 1),
        )
        self.reviews.append(review)
        return self._to_dict(review)

    def _compare_outcomes(self, predicted: str, actual: str) -> bool:
        if not predicted or not actual:
            return False
        pred_lower = predicted.lower()
        actual_lower = actual.lower()
        return pred_lower in actual_lower or actual_lower in pred_lower

    def _determine_outcome(self, correct: bool, predicted: str, actual: str) -> ReviewOutcome:
        if correct:
            return ReviewOutcome.CORRECT
        if predicted and actual:
            return ReviewOutcome.PARTIALLY_CORRECT
        return ReviewOutcome.INCONCLUSIVE

    def _identify_error_source(
        self, correct: bool, decision: str, actual: str, data: dict
    ) -> ErrorSource:
        if correct:
            return ErrorSource.NONE

        thesis = data.get("thesis", {})
        if not thesis or not thesis.get("why_buy"):
            return ErrorSource.THESIS_ERROR

        if decision in ("BUY", "STRONG_BUY") and "down" in actual.lower():
            return ErrorSource.MARKET_REGIME_ERROR
        if decision in ("SELL", "REDUCE") and "up" in actual.lower():
            return ErrorSource.TIMING_ERROR

        conviction = data.get("conviction_score", 50)
        if conviction > 70:
            return ErrorSource.MODEL_ERROR

        return ErrorSource.RISK_ASSESSMENT_ERROR

    def _generate_analysis(
        self, decision: str, conviction: float, predicted: str, actual: str, correct: bool
    ) -> str:
        if correct:
            return (
                f"Decision ({decision}, conviction {conviction:.0f}/100) was CORRECT. "
                f"Predicted: {predicted}. Actual: {actual}. "
                "The investment thesis and risk assessment were accurate."
            )
        return (
            f"Decision ({decision}, conviction {conviction:.0f}/100) was INCORRECT. "
            f"Predicted: {predicted}. Actual: {actual}. "
            "Review the thesis, model inputs, and risk assumptions for errors."
        )

    def _extract_lessons(self, correct: bool, error_source: ErrorSource, data: dict) -> List[str]:
        if correct:
            return [
                "Thesis validation process worked effectively",
                "Risk assessment was well-calibrated",
                "Decision framework produced accurate result",
            ]

        lessons = {
            ErrorSource.THESIS_ERROR: [
                "Thesis generation needs stronger evidence requirements",
                "Consider adding counter-thesis validation step",
                "Improve catalyst verification process",
            ],
            ErrorSource.MODEL_ERROR: [
                "Model parameters need recalibration",
                "Consider ensemble approach for higher conviction decisions",
                "Add uncertainty quantification to model outputs",
            ],
            ErrorSource.TIMING_ERROR: [
                "Entry/exit timing signals need improvement",
                "Consider technical analysis overlay for timing",
                "Add momentum confirmation before execution",
            ],
            ErrorSource.RISK_ASSESSMENT_ERROR: [
                "Risk models underestimated actual risk",
                "Increase risk buffer for high-conviction decisions",
                "Add tail-risk scenario testing",
            ],
            ErrorSource.MARKET_REGIME_ERROR: [
                "Market regime detection needs refinement",
                "Add regime-dependent position sizing",
                "Improve regime transition detection",
            ],
        }
        return lessons.get(error_source, ["Review decision process for unidentified errors"])

    def _generate_improvements(self, error_source: ErrorSource) -> List[str]:
        if error_source == ErrorSource.NONE:
            return ["Continue current process", "Document successful pattern"]

        improvements = {
            ErrorSource.THESIS_ERROR: [
                "Implement thesis quality scoring",
                "Add peer review step for theses",
                "Require minimum 3 supporting data points",
            ],
            ErrorSource.MODEL_ERROR: [
                "Schedule model retraining",
                "Add cross-validation to model pipeline",
                "Implement A/B testing for model changes",
            ],
            ErrorSource.TIMING_ERROR: [
                "Add execution timing optimization",
                "Implement phased entry/exit protocols",
                "Add volatility-adjusted timing",
            ],
            ErrorSource.RISK_ASSESSMENT_ERROR: [
                "Recalibrate risk models with new data",
                "Increase risk factor weights",
                "Add stress testing scenarios",
            ],
            ErrorSource.MARKET_REGIME_ERROR: [
                "Add real-time regime monitoring",
                "Implement regime-contingent decision rules",
                "Increase regime detection sensitivity",
            ],
        }
        return improvements.get(error_source, ["Conduct thorough root cause analysis"])

    def _calculate_review_score(self, correct: bool, outcome: ReviewOutcome, data: dict) -> float:
        base = 100.0 if correct else 0.0
        if outcome == ReviewOutcome.PARTIALLY_CORRECT:
            base = 50.0
        if outcome == ReviewOutcome.INCONCLUSIVE:
            base = 30.0

        # Deduct for lack of data
        if not data.get("thesis"):
            base -= 20
        if not data.get("predicted_outcome"):
            base -= 15
        if not data.get("actual_outcome"):
            base -= 15

        return max(0.0, base)

    def _to_dict(self, review: DecisionReview) -> dict:
        return {
            "review": {
                "review_id": review.review_id,
                "decision_id": review.decision_id,
                "symbol": review.symbol,
                "original_decision": review.original_decision,
                "predicted_outcome": review.predicted_outcome,
                "actual_outcome": review.actual_outcome,
                "prediction_correct": review.prediction_correct,
                "outcome": review.outcome.value,
                "error_source": review.error_source.value,
                "analysis": review.analysis,
                "lessons_learned": review.lessons_learned,
                "improvement_actions": review.improvement_actions,
                "review_score": review.review_score,
            }
        }

    def get_reviews(self, decision_id: Optional[str] = None) -> List[DecisionReview]:
        """Get all reviews, optionally filtered by decision_id."""
        if decision_id:
            return [r for r in self.reviews if r.decision_id == decision_id]
        return list(self.reviews)

    def get_lessons_all(self) -> List[str]:
        """Get all lessons learned across all reviews."""
        lessons = []
        for r in self.reviews:
            lessons.extend(r.lessons_learned)
        return lessons

    def get_error_rate(self) -> float:
        """Calculate the overall error rate."""
        if not self.reviews:
            return 0.0
        incorrect = sum(1 for r in self.reviews if r.outcome != ReviewOutcome.CORRECT)
        return round(incorrect / len(self.reviews), 2)
