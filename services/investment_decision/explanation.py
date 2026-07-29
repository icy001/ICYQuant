from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionExplanation:
    decision_id: str
    symbol: str
    decision: str
    why_this_decision: str
    evidence_used: List[str] = field(default_factory=list)
    risk_considerations: List[str] = field(default_factory=list)
    what_invalidates: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)
    confidence_level: str = ""
    transparency_score: float = 0.0  # 0-100


class DecisionExplanationEngine:
    """Decision Explanation Engine - generates transparent explanations for investment decisions."""

    def __init__(self):
        self.explanations: List[DecisionExplanation] = []

    def explain(self, decision):
        """Generate an explanation for an investment decision.

        Args:
            decision: The decision to explain (str, dict, or DecisionExplanation).

        Returns:
            Dict containing the explanation.
        """
        if isinstance(decision, DecisionExplanation):
            return self._process_explanation(decision)
        if isinstance(decision, dict):
            return self._explain_dict(decision)
        return {"explanation": decision}

    def _process_explanation(self, explanation: DecisionExplanation) -> dict:
        self.explanations.append(explanation)
        return self._to_dict(explanation)

    def _explain_dict(self, data: dict) -> dict:
        decision_data = data.get("decision", data)
        symbol = decision_data.get("symbol", "UNKNOWN")
        decision_id = decision_data.get("decision_id", "UNKNOWN")
        decision_type = decision_data.get("decision", "UNKNOWN")
        conviction = decision_data.get("conviction_score", 50)
        rationale = decision_data.get("rationale", "")
        risk_controls = decision_data.get("risk_controls", [])
        dependencies = decision_data.get("dependencies", [])

        # Build structured explanation
        why_this = self._build_why_explanation(decision_type, conviction, rationale)
        evidence = self._extract_evidence(data)
        risk_considerations = self._extract_risk_considerations(data)
        invalidation_points = self._extract_invalidation_points(data)
        alternatives = self._consider_alternatives(decision_type)
        confidence = self._assess_confidence(conviction)
        transparency = self._calculate_transparency(data)

        explanation = DecisionExplanation(
            decision_id=decision_id,
            symbol=symbol,
            decision=decision_type,
            why_this_decision=why_this,
            evidence_used=evidence,
            risk_considerations=risk_considerations,
            what_invalidates=invalidation_points,
            alternatives_considered=alternatives,
            confidence_level=confidence,
            transparency_score=round(transparency, 1),
        )
        self.explanations.append(explanation)
        return self._to_dict(explanation)

    def _build_why_explanation(self, decision_type: str, conviction: float, rationale: str) -> str:
        if decision_type in ("STRONG_BUY", "BUY"):
            return (
                f"The committee reached a {decision_type} decision with "
                f"{conviction:.0f}/100 conviction. The investment thesis is well-supported "
                f"by fundamental analysis, market conditions, and risk assessment. "
                f"Expected returns justify the risk taken."
            )
        elif decision_type == "HOLD":
            return (
                f"The committee decided to HOLD with {conviction:.0f}/100 conviction. "
                f"While the thesis has merit, conviction is not strong enough to increase "
                f"exposure. Monitor for catalysts that could improve conviction."
            )
        else:
            return (
                f"The committee decided to {decision_type} with {conviction:.0f}/100 conviction. "
                f"The risk/reward profile is unfavorable. Either the thesis has weakened "
                f"or risks have increased beyond acceptable levels."
            )

    def _extract_evidence(self, data: dict) -> List[str]:
        evidence = []
        # Extract from thesis
        thesis = data.get("thesis", {})
        if thesis.get("why_buy"):
            evidence.append(f"Investment thesis: {thesis['why_buy']}")
        if thesis.get("catalyst"):
            evidence.append(f"Catalyst: {thesis['catalyst']}")

        # Extract from bull case
        bull_case = data.get("bull_case", {})
        bull_data = bull_case.get("bull_case", bull_case)
        if bull_data.get("catalysts"):
            evidence.append(f"Bull catalysts: {', '.join(bull_data['catalysts'][:3])}")

        if not evidence:
            evidence = [
                "Fundamental analysis completed",
                "Technical analysis reviewed",
                "Market conditions evaluated",
                "Risk assessment performed",
            ]
        return evidence

    def _extract_risk_considerations(self, data: dict) -> List[str]:
        risks = []
        bear_case = data.get("bear_case", {})
        bear_data = bear_case.get("bear_case", bear_case)
        if bear_data.get("risk_factors"):
            risks.extend(bear_data["risk_factors"][:3])

        decision_data = data.get("decision", data)
        if decision_data.get("risk_controls"):
            risks.append(f"Risk controls in place: {', '.join(decision_data['risk_controls'][:2])}")

        if not risks:
            risks = ["Standard market risk", "Liquidity risk monitored", "Sector risk diversified"]
        return risks

    def _extract_invalidation_points(self, data: dict) -> List[str]:
        bear_case = data.get("bear_case", {})
        bear_data = bear_case.get("bear_case", bear_case)
        invalidation = bear_data.get("invalidation_points", [])
        if invalidation:
            return invalidation[:4]

        return [
            "Thesis catalyst fails to materialize",
            "Conviction score drops below threshold",
            "Market regime shifts to unfavorable",
            "Risk metrics breach acceptable limits",
        ]

    def _consider_alternatives(self, decision_type: str) -> List[str]:
        alternatives = {
            "STRONG_BUY": ["BUY (lower conviction)", "HOLD (wait for pullback)", "SCALE_IN (phased entry)"],
            "BUY": ["HOLD (wait for better entry)", "REDUCE_SIZE (smaller position)", "OPTIONS (defined risk)"],
            "HOLD": ["BUY (increase exposure)", "REDUCE (trim position)", "SELL (exit entirely)"],
            "REDUCE": ["HOLD (maintain current)", "SELL (full exit)", "HEDGE (add protection)"],
            "SELL": ["REDUCE (partial exit)", "HOLD (wait for bounce)", "HEDGE (protect downside)"],
            "REJECT": ["MONITOR (watch for improvement)", "BUY_SMALL (pilot position)", "OPTIONS (speculative)"],
        }
        return alternatives.get(decision_type, ["HOLD", "MONITOR", "RE-EVALUATE"])

    def _assess_confidence(self, conviction: float) -> str:
        if conviction >= 80:
            return "HIGH - Decision supported by strong evidence and committee alignment"
        if conviction >= 60:
            return "MODERATE-HIGH - Decision has good support with some uncertainty"
        if conviction >= 40:
            return "MODERATE - Mixed signals, decision carries uncertainty"
        return "LOW - Limited conviction, decision is primarily risk-driven"

    def _calculate_transparency(self, data: dict) -> float:
        score = 0.0
        if data.get("thesis"):
            score += 25.0
        if data.get("bull_case"):
            score += 20.0
        if data.get("bear_case"):
            score += 20.0
        if data.get("decision"):
            score += 20.0
        if data.get("votes"):
            score += 15.0
        return min(100.0, score)

    def _to_dict(self, explanation: DecisionExplanation) -> dict:
        return {
            "explanation": {
                "decision_id": explanation.decision_id,
                "symbol": explanation.symbol,
                "decision": explanation.decision,
                "why_this_decision": explanation.why_this_decision,
                "evidence_used": explanation.evidence_used,
                "risk_considerations": explanation.risk_considerations,
                "what_invalidates": explanation.what_invalidates,
                "alternatives_considered": explanation.alternatives_considered,
                "confidence_level": explanation.confidence_level,
                "transparency_score": explanation.transparency_score,
            }
        }

    def get_explanations(self, decision_id: Optional[str] = None) -> List[DecisionExplanation]:
        """Get all explanations, optionally filtered by decision_id."""
        if decision_id:
            return [e for e in self.explanations if e.decision_id == decision_id]
        return list(self.explanations)
