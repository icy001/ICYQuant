from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OpportunityRating(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    REJECT = "REJECT"


class ValuationLevel(str, Enum):
    UNDERVALUED = "UNDERVALUED"
    FAIR_VALUE = "FAIR_VALUE"
    OVERVALUED = "OVERVALUED"
    EXTREMELY_OVERVALUED = "EXTREMELY_OVERVALUED"


@dataclass
class OpportunityProfile:
    symbol: str
    sector: str = ""
    market_cap: float = 0.0
    growth_rate: float = 0.0
    pe_ratio: float = 0.0
    competitive_moat: str = ""
    risk_score: float = 0.0  # 0-100, higher = more risk
    market_opportunity: str = ""
    description: str = ""


@dataclass
class OpportunityEvaluation:
    symbol: str
    rating: OpportunityRating
    market_opportunity_score: float = 0.0  # 0-100
    competitive_advantage_score: float = 0.0
    growth_potential_score: float = 0.0
    valuation_score: float = 0.0
    risk_adjusted_score: float = 0.0
    valuation_level: ValuationLevel = ValuationLevel.FAIR_VALUE
    summary: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    total_score: float = 0.0


class OpportunityEvaluationEngine:
    """Opportunity Evaluation Engine - evaluates investment opportunities across multiple dimensions."""

    def __init__(self):
        self.evaluations: List[OpportunityEvaluation] = []

    def evaluate(self, asset):
        """Evaluate an investment asset.

        Args:
            asset: The asset to evaluate (str, dict, or OpportunityProfile).

        Returns:
            Dict containing the evaluation result.
        """
        if isinstance(asset, OpportunityProfile):
            return self._evaluate_profile(asset)
        if isinstance(asset, dict):
            return self._evaluate_dict(asset)
        return {"evaluation": asset}

    def _evaluate_profile(self, profile: OpportunityProfile) -> dict:
        market_opp = self._score_market_opportunity(profile)
        comp_adv = self._score_competitive_advantage(profile)
        growth = self._score_growth(profile)
        valuation = self._score_valuation(profile)

        total = (market_opp * 0.25 + comp_adv * 0.20 + growth * 0.25 + valuation * 0.30)
        risk_adjusted = total * (1 - min(profile.risk_score / 100, 0.5))

        rating = self._determine_rating(risk_adjusted)

        evaluation = OpportunityEvaluation(
            symbol=profile.symbol,
            rating=rating,
            market_opportunity_score=round(market_opp, 1),
            competitive_advantage_score=round(comp_adv, 1),
            growth_potential_score=round(growth, 1),
            valuation_score=round(valuation, 1),
            risk_adjusted_score=round(risk_adjusted, 1),
            valuation_level=self._determine_valuation(profile),
            summary=self._generate_summary(profile, rating, risk_adjusted),
            strengths=self._identify_strengths(profile),
            weaknesses=self._identify_weaknesses(profile),
            total_score=round(total, 1),
        )
        self.evaluations.append(evaluation)
        return self._to_dict(evaluation)

    def _evaluate_dict(self, data: dict) -> dict:
        profile = OpportunityProfile(
            symbol=data.get("symbol", "UNKNOWN"),
            sector=data.get("sector", ""),
            market_cap=data.get("market_cap", 0.0),
            growth_rate=data.get("growth_rate", 0.0),
            pe_ratio=data.get("pe_ratio", 0.0),
            competitive_moat=data.get("competitive_moat", ""),
            risk_score=data.get("risk_score", 0.0),
            market_opportunity=data.get("market_opportunity", ""),
        )
        return self._evaluate_profile(profile)

    def _score_market_opportunity(self, profile: OpportunityProfile) -> float:
        score = 50.0
        if profile.market_cap > 0:
            score += 10.0
        if profile.sector:
            score += 10.0
        if profile.market_opportunity:
            score += 15.0
        return min(100.0, score)

    def _score_competitive_advantage(self, profile: OpportunityProfile) -> float:
        score = 50.0
        moat_score = {
            "strong": 30, "moderate": 20, "weak": 5, "none": 0,
        }
        score += moat_score.get(profile.competitive_moat.lower(), 0)
        return min(100.0, score)

    def _score_growth(self, profile: OpportunityProfile) -> float:
        if profile.growth_rate <= 0:
            return 30.0
        if profile.growth_rate < 0.05:
            return 50.0
        if profile.growth_rate < 0.15:
            return 70.0
        if profile.growth_rate < 0.30:
            return 85.0
        return 95.0

    def _score_valuation(self, profile: OpportunityProfile) -> float:
        if profile.pe_ratio <= 0:
            return 50.0
        if profile.pe_ratio < 12:
            return 85.0
        if profile.pe_ratio < 18:
            return 75.0
        if profile.pe_ratio < 25:
            return 60.0
        if profile.pe_ratio < 40:
            return 40.0
        return 20.0

    def _determine_rating(self, score: float) -> OpportunityRating:
        if score >= 80:
            return OpportunityRating.EXCELLENT
        if score >= 65:
            return OpportunityRating.GOOD
        if score >= 45:
            return OpportunityRating.FAIR
        if score >= 25:
            return OpportunityRating.POOR
        return OpportunityRating.REJECT

    def _determine_valuation(self, profile: OpportunityProfile) -> ValuationLevel:
        if profile.pe_ratio <= 0:
            return ValuationLevel.FAIR_VALUE
        if profile.pe_ratio < 12:
            return ValuationLevel.UNDERVALUED
        if profile.pe_ratio < 25:
            return ValuationLevel.FAIR_VALUE
        if profile.pe_ratio < 40:
            return ValuationLevel.OVERVALUED
        return ValuationLevel.EXTREMELY_OVERVALUED

    def _generate_summary(self, profile: OpportunityProfile, rating: OpportunityRating, score: float) -> str:
        return (
            f"{profile.symbol}: {rating.value} opportunity "
            f"(score: {score:.1f}/100). "
            f"Sector: {profile.sector or 'N/A'}, "
            f"Growth: {profile.growth_rate:.1%}, "
            f"P/E: {profile.pe_ratio:.1f}"
        )

    def _identify_strengths(self, profile: OpportunityProfile) -> List[str]:
        strengths = []
        if profile.growth_rate > 0.15:
            strengths.append(f"Strong growth rate ({profile.growth_rate:.1%})")
        if profile.competitive_moat in ("strong", "moderate"):
            strengths.append(f"{profile.competitive_moat.title()} competitive moat")
        if profile.pe_ratio < 15 and profile.pe_ratio > 0:
            strengths.append("Attractive valuation")
        if profile.risk_score < 30:
            strengths.append("Low risk profile")
        return strengths

    def _identify_weaknesses(self, profile: OpportunityProfile) -> List[str]:
        weaknesses = []
        if profile.growth_rate < 0.05 and profile.growth_rate > 0:
            weaknesses.append(f"Low growth rate ({profile.growth_rate:.1%})")
        if profile.pe_ratio > 30:
            weaknesses.append(f"Elevated valuation (P/E: {profile.pe_ratio:.1f})")
        if profile.risk_score > 60:
            weaknesses.append(f"High risk score ({profile.risk_score:.0f}/100)")
        if profile.competitive_moat == "none":
            weaknesses.append("No competitive moat")
        return weaknesses

    def _to_dict(self, evaluation: OpportunityEvaluation) -> dict:
        return {
            "evaluation": {
                "symbol": evaluation.symbol,
                "rating": evaluation.rating.value,
                "market_opportunity_score": evaluation.market_opportunity_score,
                "competitive_advantage_score": evaluation.competitive_advantage_score,
                "growth_potential_score": evaluation.growth_potential_score,
                "valuation_score": evaluation.valuation_score,
                "risk_adjusted_score": evaluation.risk_adjusted_score,
                "valuation_level": evaluation.valuation_level.value,
                "total_score": evaluation.total_score,
                "summary": evaluation.summary,
                "strengths": evaluation.strengths,
                "weaknesses": evaluation.weaknesses,
            }
        }

    def get_history(self, symbol: Optional[str] = None) -> List[OpportunityEvaluation]:
        """Get evaluation history, optionally filtered by symbol."""
        if symbol:
            return [e for e in self.evaluations if e.symbol == symbol]
        return list(self.evaluations)
