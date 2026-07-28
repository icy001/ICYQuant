from typing import Dict, Optional


class DecisionScoringEngine:
    """Computes a unified decision score from alpha, model confidence, and risk penalty.

    Formula: Decision Score = Alpha + Model Confidence - Risk Penalty
    """

    def __init__(
        self,
        alpha_weight: float = 1.0,
        model_weight: float = 1.0,
        risk_weight: float = 1.0,
        min_threshold: float = 0.3,
    ):
        self.alpha_weight = alpha_weight
        self.model_weight = model_weight
        self.risk_weight = risk_weight
        self.min_threshold = min_threshold

    def score(self, alpha: float, risk: float) -> float:
        """Basic scoring: alpha minus risk.

        Args:
            alpha: Alpha score (0-1 scale).
            risk: Risk penalty (0-1 scale).

        Returns:
            Decision score.
        """
        return round(alpha - risk, 4)

    def score_full(
        self,
        alpha: float,
        model_confidence: float = 0.0,
        risk_penalty: float = 0.0,
    ) -> Dict[str, float]:
        """Full scoring with alpha, model confidence, and risk penalty.

        Returns:
            Dict with 'raw_score', 'final_score', 'actionable'.
        """
        raw = (
            self.alpha_weight * alpha
            + self.model_weight * model_confidence
            - self.risk_weight * risk_penalty
        )
        final = round(max(raw, 0.0), 4)
        return {
            "raw_score": raw,
            "final_score": final,
            "actionable": final >= self.min_threshold,
            "alpha": alpha,
            "model_confidence": model_confidence,
            "risk_penalty": risk_penalty,
        }

    def score_multi_factor(
        self,
        factor_scores: Dict[str, float],
        factor_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Score using multiple named factors with optional weights.

        Args:
            factor_scores: Dict of factor name -> score.
            factor_weights: Optional per-factor weights.

        Returns:
            Weighted total score.
        """
        if not factor_scores:
            return 0.0

        total = 0.0
        total_weight = 0.0

        for name, value in factor_scores.items():
            w = (factor_weights or {}).get(name, 1.0)
            total += value * w
            total_weight += w

        return round(total / total_weight, 4) if total_weight > 0 else 0.0

    def determine_action(
        self, alpha: float, risk: float, threshold: float = 0.2
    ) -> str:
        """Determine BUY/SELL/HOLD based on alpha and risk."""
        score = alpha - risk
        if score > threshold:
            return "BUY"
        elif score < -threshold:
            return "SELL"
        return "HOLD"
