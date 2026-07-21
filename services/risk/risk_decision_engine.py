"""
Risk decision engine.
"""

from .risk_decision import RiskDecision


class RiskDecisionEngine:

    def decide(
        self,
        risk_score,
    ):

        if risk_score >= 0.8:

            return RiskDecision(
                False,
                risk_score,
                "Risk threshold exceeded",
            )

        return RiskDecision(
            True,
            risk_score,
            "Approved",
        )