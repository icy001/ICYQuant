"""Risk Explanation Engine – explain risk drivers in natural language."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .risk import RiskProfile


@dataclass
class RiskExplanation:
    """A human-readable risk explanation.

    Breaks down why risk is at its current level, identifies the
    top contributing factors, and provides actionable recommendations.
    """

    portfolio_id: str
    risk_level: str
    score: float
    reason: str
    factors: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "risk_level": self.risk_level,
            "score": self.score,
            "reason": self.reason,
            "factors": self.factors,
            "recommendations": self.recommendations,
        }


class RiskExplanationEngine:
    """Generates human-readable explanations of portfolio risk.

    Translates quantitative risk metrics into structured, actionable
    explanations that traders and portfolio managers can understand.
    """

    def explain(self, risk: Any) -> dict:
        """Explain risk – supports RiskProfile, dict, or legacy string input.

        Args:
            risk: A RiskProfile, dict with risk metrics, or plain string.
        """
        if isinstance(risk, RiskProfile):
            return self._explain_profile(risk).to_dict()
        elif isinstance(risk, dict):
            return self._explain_dict(risk)
        elif isinstance(risk, str):
            return {"reason": risk}
        else:
            return {"reason": str(risk)}

    def _explain_profile(self, profile: RiskProfile) -> RiskExplanation:
        """Explain a full RiskProfile."""
        factors: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        # Build factor explanations
        attribution = profile.factor_attribution
        for factor_name, contrib in sorted(
            attribution.items(), key=lambda x: x[1], reverse=True
        ):
            if contrib >= 20:
                factors.append({
                    "name": factor_name,
                    "contribution": contrib,
                    "severity": "high",
                })
                # Generate recommendation
                rec = self._recommendation_for_factor(factor_name)
                if rec:
                    recommendations.append(rec)

        # Build summary reason
        reason_parts: List[str] = []
        if profile.risk_drivers:
            reason_parts.append(
                f"Risk level {profile.level.upper()} (score {profile.score:.0f}/100)."
            )
            reason_parts.append(
                f"Key drivers: {', '.join(profile.risk_drivers)}."
            )
        else:
            reason_parts.append(
                f"Risk level {profile.level.upper()} (score {profile.score:.0f}/100)."
            )

        if profile.volatility > 0.3:
            reason_parts.append(
                f"Volatility elevated at {profile.volatility:.1%}."
            )

        if profile.concentration > 0.3:
            reason_parts.append(
                f"Portfolio concentration at {profile.concentration:.1%}."
            )

        # Deduplicate recommendations
        unique_recs = list(dict.fromkeys(recommendations))

        return RiskExplanation(
            portfolio_id=profile.portfolio_id,
            risk_level=profile.level,
            score=profile.score,
            reason=" ".join(reason_parts),
            factors=factors,
            recommendations=unique_recs[:5],
        )

    def _explain_dict(self, risk_dict: dict) -> dict:
        """Explain a dict with risk metrics."""
        if "portfolio_id" in risk_dict:
            # Try to construct a RiskProfile
            try:
                profile = RiskProfile(
                    portfolio_id=risk_dict.get("portfolio_id", "unknown"),
                    score=risk_dict.get("score", 0),
                    level=risk_dict.get("level", "unknown"),
                    volatility=risk_dict.get("volatility", 0),
                    concentration=risk_dict.get("concentration", 0),
                    factor_attribution=risk_dict.get(
                        "factor_attribution", {}
                    ),
                    risk_drivers=risk_dict.get("risk_drivers", []),
                )
                return self._explain_profile(profile).to_dict()
            except Exception:
                pass
        return {"reason": str(risk_dict)}

    def _recommendation_for_factor(self, factor_name: str) -> Optional[str]:
        """Generate a recommendation for a given risk factor."""
        recommendations = {
            "Exposure": "Consider reducing overall portfolio exposure.",
            "Volatility": "Hedge with options or reduce high-vol positions.",
            "Drawdown": "Review stop-loss levels and position sizing.",
            "Concentration": "Diversify across sectors to reduce concentration risk.",
            "Sector": "Reduce sector-specific concentration through diversification.",
            "Beta": "Add non-correlated assets to reduce beta exposure.",
            "Market Beta": "Add non-correlated assets to reduce beta exposure.",
            "Currency": "Hedge currency exposure or diversify across currencies.",
            "VaR (95%)": "Reduce tail-risk positions or add protective hedges.",
        }
        return recommendations.get(factor_name)

    def explain_simple(self, risk: Any) -> dict:
        """Legacy interface returning {'reason': risk}."""
        return {"reason": str(risk)}
