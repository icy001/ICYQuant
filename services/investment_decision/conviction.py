from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConvictionLevel(str, Enum):
    VERY_STRONG = "VERY_STRONG"
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NO_CONVICTION = "NO_CONVICTION"


@dataclass
class ConvictionScore:
    symbol: str
    score: float  # 0-100
    level: ConvictionLevel
    bull_contribution: float
    bear_penalty: float
    risk_adjustment: float
    committee_alignment: float
    factors: Dict[str, float] = field(default_factory=dict)
    label: str = ""


class ConvictionScoreEngine:
    """Conviction Score Engine - calculates investment conviction based on multi-dimensional analysis."""

    def __init__(self):
        self.scores: List[ConvictionScore] = []

    def score(self, analysis):
        """Score the conviction level of an investment analysis.

        Args:
            analysis: The analysis data (int, dict, or ConvictionScore).

        Returns:
            Dict containing the conviction score.
        """
        if isinstance(analysis, ConvictionScore):
            return self._process_score(analysis)
        if isinstance(analysis, dict):
            return self._score_dict(analysis)
        if isinstance(analysis, (int, float)):
            return {"score": int(analysis)}
        return {"score": 80}

    def _process_score(self, score: ConvictionScore) -> dict:
        self.scores.append(score)
        return self._to_dict(score)

    def _score_dict(self, data: dict) -> dict:
        symbol = data.get("symbol", "UNKNOWN")
        bull_case = data.get("bull_case", {})
        bear_case = data.get("bear_case", {})
        votes = data.get("votes", [])

        # Calculate contributions
        bull_contribution = self._calc_bull_contribution(bull_case)
        bear_penalty = self._calc_bear_penalty(bear_case)
        risk_adjustment = self._calc_risk_adjustment(bear_case)
        committee_alignment = self._calc_committee_alignment(votes)

        # Weighted scoring
        raw_score = (
            bull_contribution * 0.35
            + (100 - bear_penalty) * 0.25
            + (100 - risk_adjustment) * 0.20
            + committee_alignment * 0.20
        )

        # Clamp to 0-100
        final_score = max(0.0, min(100.0, raw_score))
        level = self._determine_level(final_score)
        label = self._generate_label(final_score)

        score = ConvictionScore(
            symbol=symbol,
            score=round(final_score, 1),
            level=level,
            bull_contribution=round(bull_contribution, 1),
            bear_penalty=round(bear_penalty, 1),
            risk_adjustment=round(risk_adjustment, 1),
            committee_alignment=round(committee_alignment, 1),
            factors={
                "bull": round(bull_contribution, 1),
                "bear": round(bear_penalty, 1),
                "risk": round(risk_adjustment, 1),
                "committee": round(committee_alignment, 1),
            },
            label=label,
        )
        self.scores.append(score)
        return self._to_dict(score)

    def _calc_bull_contribution(self, bull_case: dict) -> float:
        bull_data = bull_case.get("bull_case", bull_case)
        base = 50.0

        conviction = bull_data.get("bullish_conviction", 0.5)
        if isinstance(conviction, (int, float)):
            base += conviction * 40

        catalysts = bull_data.get("catalysts", [])
        if isinstance(catalysts, list) and len(catalysts) > 0:
            base += min(len(catalysts) * 5, 15)

        growth_drivers = bull_data.get("growth_drivers", [])
        if isinstance(growth_drivers, list) and len(growth_drivers) > 2:
            base += 10

        return min(100.0, base)

    def _calc_bear_penalty(self, bear_case: dict) -> float:
        bear_data = bear_case.get("bear_case", bear_case)
        base = 20.0

        risk_intensity = bear_data.get("risk_intensity", 0.3)
        if isinstance(risk_intensity, (int, float)):
            base += risk_intensity * 60

        risk_factors = bear_data.get("risk_factors", [])
        if isinstance(risk_factors, list) and len(risk_factors) > 3:
            base += 10

        bubble_indicators = bear_data.get("bubble_indicators", [])
        if isinstance(bubble_indicators, list) and len(bubble_indicators) > 0:
            base += 15

        return min(100.0, base)

    def _calc_risk_adjustment(self, bear_case: dict) -> float:
        bear_data = bear_case.get("bear_case", bear_case)
        base = 15.0

        max_drawdown = bear_data.get("max_drawdown_estimate", 0.15)
        if isinstance(max_drawdown, (int, float)):
            if max_drawdown > 0.3:
                base += 40
            elif max_drawdown > 0.2:
                base += 25
            elif max_drawdown > 0.1:
                base += 10

        failure_scenarios = bear_data.get("failure_scenarios", [])
        if isinstance(failure_scenarios, list) and len(failure_scenarios) > 3:
            base += 10

        return min(100.0, base)

    def _calc_committee_alignment(self, votes: list) -> float:
        if not votes:
            return 50.0

        vote_values = {
            "STRONG_BUY": 100, "BUY": 75, "HOLD": 50,
            "SELL": 25, "STRONG_SELL": 0, "ABSTAIN": 50,
        }

        if isinstance(votes[0], dict):
            scores = [vote_values.get(v.get("vote", "HOLD"), 50) for v in votes]
        else:
            scores = [vote_values.get(getattr(v, "vote", None), 50) for v in votes]

        avg = sum(scores) / len(scores) if scores else 50.0

        # Higher dispersion = lower alignment
        if len(scores) > 1:
            dispersion = max(scores) - min(scores)
            alignment_penalty = dispersion * 0.5
            return max(0, avg - alignment_penalty)

        return avg

    def _determine_level(self, score: float) -> ConvictionLevel:
        if score >= 85:
            return ConvictionLevel.VERY_STRONG
        if score >= 70:
            return ConvictionLevel.STRONG
        if score >= 50:
            return ConvictionLevel.MODERATE
        if score >= 30:
            return ConvictionLevel.WEAK
        return ConvictionLevel.NO_CONVICTION

    def _generate_label(self, score: float) -> str:
        if score >= 90:
            return "STRONG BUY - Very High Conviction"
        if score >= 75:
            return "BUY - High Conviction"
        if score >= 60:
            return "BUY - Moderate Conviction"
        if score >= 50:
            return "HOLD - Balanced Risk/Reward"
        if score >= 35:
            return "REDUCE - Weak Conviction"
        if score >= 20:
            return "SELL - Low Conviction"
        return "SELL - No Conviction"

    def _to_dict(self, score: ConvictionScore) -> dict:
        return {
            "score": {
                "symbol": score.symbol,
                "score": score.score,
                "level": score.level.value,
                "bull_contribution": score.bull_contribution,
                "bear_penalty": score.bear_penalty,
                "risk_adjustment": score.risk_adjustment,
                "committee_alignment": score.committee_alignment,
                "factors": score.factors,
                "label": score.label,
            }
        }

    def get_scores(self, symbol: Optional[str] = None) -> List[ConvictionScore]:
        """Get conviction scores, optionally filtered by symbol."""
        if symbol:
            return [s for s in self.scores if s.symbol == symbol]
        return list(self.scores)
