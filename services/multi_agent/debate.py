"""Multi Agent Debate Engine - simulates investment debates between AI agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DebatePosition(Enum):
    """Position in a debate."""
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


class DebateRound(Enum):
    """Round structure of a formal debate."""
    OPENING = "OPENING"
    REBUTTAL = "REBUTTAL"
    CROSS_EXAMINATION = "CROSS_EXAMINATION"
    CLOSING = "CLOSING"


class ArgumentStrength(Enum):
    """Strength classification of an argument."""
    VERY_STRONG = "VERY_STRONG"
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    SPECULATIVE = "SPECULATIVE"


@dataclass
class Argument:
    """A single argument in a debate."""
    argument_id: str
    position: DebatePosition
    statement: str
    evidence: List[str] = field(default_factory=list)
    strength: ArgumentStrength = ArgumentStrength.MODERATE
    confidence: float = 0.5
    data_support: Dict[str, Any] = field(default_factory=dict)
    counter_arguments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "argument_id": self.argument_id,
            "position": self.position.value,
            "statement": self.statement,
            "evidence": self.evidence,
            "strength": self.strength.value,
            "confidence": self.confidence,
        }


@dataclass
class DebateRoundResult:
    """Result of a single debate round."""
    round_type: DebateRound
    bull_arguments: List[Argument] = field(default_factory=list)
    bear_arguments: List[Argument] = field(default_factory=list)
    neutral_arguments: List[Argument] = field(default_factory=list)
    winner: Optional[DebatePosition] = None
    key_insights: List[str] = field(default_factory=list)


@dataclass
class DebateResult:
    """Complete debate result."""
    topic: str
    rounds: List[DebateRoundResult] = field(default_factory=list)
    final_winner: Optional[DebatePosition] = None
    bull_score: float = 0.0
    bear_score: float = 0.0
    consensus_reached: bool = False
    consensus_position: Optional[DebatePosition] = None
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "rounds": len(self.rounds),
            "final_winner": self.final_winner.value if self.final_winner else "undecided",
            "bull_score": self.bull_score,
            "bear_score": self.bear_score,
            "consensus_reached": self.consensus_reached,
            "consensus": self.consensus_position.value if self.consensus_position else "none",
            "summary": self.summary,
            "recommendations": self.recommendations,
            "risk_flags": self.risk_flags,
        }


class MultiAgentDebateEngine:
    """Multi-agent debate engine for investment decision making.

    Simulates a formal investment debate:
    - Bull Analyst presents bullish case
    - Bear Analyst presents bearish case
    - Neutral Analyst provides balanced view
    - Multiple rounds of rebuttal
    - Final consensus building

    Example debate on NVDA:
    Bull: "AI CapEx continues growing"
    Bear: "Valuation is excessive"
    """

    def __init__(self):
        self._debate_history: List[DebateResult] = []

    def debate(self, topic: str) -> DebateResult:
        """Run a debate on a given topic.

        Args:
            topic: The investment topic to debate.

        Returns:
            DebateResult with the debate outcome.
        """
        result = DebateResult(topic=topic)

        # Round 1: Opening statements
        opening = self._run_opening_round(topic)
        result.rounds.append(opening)

        # Round 2: Rebuttal
        rebuttal = self._run_rebuttal_round(topic, opening)
        result.rounds.append(rebuttal)

        # Round 3: Cross examination
        cross = self._run_cross_examination(topic, opening, rebuttal)
        result.rounds.append(cross)

        # Round 4: Closing statements
        closing = self._run_closing_round(topic, opening, rebuttal, cross)
        result.rounds.append(closing)

        # Calculate final scores
        result.bull_score = self._calculate_score(DebatePosition.BULL, result.rounds)
        result.bear_score = self._calculate_score(DebatePosition.BEAR, result.rounds)

        # Determine winner
        if abs(result.bull_score - result.bear_score) < 0.1:
            result.consensus_position = DebatePosition.NEUTRAL
            result.consensus_reached = True
        elif result.bull_score > result.bear_score:
            result.final_winner = DebatePosition.BULL
        else:
            result.final_winner = DebatePosition.BEAR

        # Generate summary
        result.summary = self._generate_summary(topic, result)
        result.recommendations = self._generate_recommendations(topic, result)
        result.risk_flags = self._identify_risk_flags(topic, result)

        self._debate_history.append(result)
        return result

    def run_full_debate_with_analysts(self, topic: str,
                                       bull_arguments: List[Dict[str, Any]],
                                       bear_arguments: List[Dict[str, Any]],
                                       neutral_arguments: List[Dict[str, Any]] = None) -> DebateResult:
        """Run a debate with pre-defined analyst arguments.

        This simulates having multiple AI analyst agents providing their views.
        """
        result = DebateResult(topic=topic)

        # Convert input arguments
        bull_args = [
            Argument(
                argument_id=f"bull_{i}",
                position=DebatePosition.BULL,
                statement=arg["statement"],
                evidence=arg.get("evidence", []),
                strength=ArgumentStrength(arg.get("strength", "MODERATE")),
                confidence=arg.get("confidence", 0.5),
            )
            for i, arg in enumerate(bull_arguments)
        ]
        bear_args = [
            Argument(
                argument_id=f"bear_{i}",
                position=DebatePosition.BEAR,
                statement=arg["statement"],
                evidence=arg.get("evidence", []),
                strength=ArgumentStrength(arg.get("strength", "MODERATE")),
                confidence=arg.get("confidence", 0.5),
            )
            for i, arg in enumerate(bear_arguments)
        ]
        neutral_args = [
            Argument(
                argument_id=f"neutral_{i}",
                position=DebatePosition.NEUTRAL,
                statement=arg["statement"],
                evidence=arg.get("evidence", []),
                strength=ArgumentStrength(arg.get("strength", "MODERATE")),
                confidence=arg.get("confidence", 0.5),
            )
            for i, arg in enumerate(neutral_arguments or [])
        ]

        # Opening round
        opening = DebateRoundResult(
            round_type=DebateRound.OPENING,
            bull_arguments=bull_args,
            bear_arguments=bear_args,
            neutral_arguments=neutral_args,
            key_insights=[a.statement for a in bull_args + bear_args],
        )
        result.rounds.append(opening)

        # Score and determine winner
        result.bull_score = sum(a.confidence * self._strength_weight(a.strength) for a in bull_args)
        result.bear_score = sum(a.confidence * self._strength_weight(a.strength) for a in bear_args)

        if abs(result.bull_score - result.bear_score) < 0.3:
            result.consensus_position = DebatePosition.NEUTRAL
            result.consensus_reached = True
        elif result.bull_score > result.bear_score:
            result.final_winner = DebatePosition.BULL
        else:
            result.final_winner = DebatePosition.BEAR

        result.summary = self._generate_summary(topic, result)
        result.recommendations = self._generate_recommendations(topic, result)
        result.risk_flags = self._identify_risk_flags(topic, result)

        self._debate_history.append(result)
        return result

    def _run_opening_round(self, topic: str) -> DebateRoundResult:
        """Simulate opening statements round."""
        return DebateRoundResult(
            round_type=DebateRound.OPENING,
            bull_arguments=[
                Argument("op_bull_1", DebatePosition.BULL, f"Bull case for {topic}: positive momentum",
                         evidence=["trend analysis", "sector strength"], strength=ArgumentStrength.STRONG,
                         confidence=0.75),
            ],
            bear_arguments=[
                Argument("op_bear_1", DebatePosition.BEAR, f"Bear case for {topic}: risk factors present",
                         evidence=["valuation metrics", "market uncertainty"], strength=ArgumentStrength.MODERATE,
                         confidence=0.6),
            ],
            key_insights=[f"Opening debate on {topic}: both sides present valid arguments"],
        )

    def _run_rebuttal_round(self, topic: str, opening: DebateRoundResult) -> DebateRoundResult:
        """Simulate rebuttal round."""
        return DebateRoundResult(
            round_type=DebateRound.REBUTTAL,
            bull_arguments=[
                Argument("reb_bull_1", DebatePosition.BULL, f"Rebuttal: {topic} growth trajectory is sustainable",
                         evidence=["revenue growth", "market expansion"], strength=ArgumentStrength.MODERATE,
                         confidence=0.65),
            ],
            bear_arguments=[
                Argument("reb_bear_1", DebatePosition.BEAR, f"Rebuttal: {topic} faces headwinds",
                         evidence=["competition", "regulatory risk"], strength=ArgumentStrength.MODERATE,
                         confidence=0.55),
            ],
            key_insights=[f"Rebuttal on {topic}: both sides strengthen their positions"],
        )

    def _run_cross_examination(self, topic: str, opening: DebateRoundResult,
                                rebuttal: DebateRoundResult) -> DebateRoundResult:
        """Simulate cross examination round."""
        return DebateRoundResult(
            round_type=DebateRound.CROSS_EXAMINATION,
            key_insights=[
                f"Cross-examination on {topic}: key assumptions challenged",
                "Risk-reward profile needs careful evaluation",
            ],
        )

    def _run_closing_round(self, topic: str, opening: DebateRoundResult,
                            rebuttal: DebateRoundResult, cross: DebateRoundResult) -> DebateRoundResult:
        """Simulate closing statements round."""
        return DebateRoundResult(
            round_type=DebateRound.CLOSING,
            bull_arguments=[
                Argument("close_bull_1", DebatePosition.BULL, f"Closing bull case: {topic} presents opportunity",
                         strength=ArgumentStrength.STRONG, confidence=0.7),
            ],
            bear_arguments=[
                Argument("close_bear_1", DebatePosition.BEAR, f"Closing bear case: caution on {topic}",
                         strength=ArgumentStrength.MODERATE, confidence=0.5),
            ],
            key_insights=[f"Closing arguments on {topic}: balanced view with slight bullish tilt"],
        )

    def _calculate_score(self, position: DebatePosition, rounds: List[DebateRoundResult]) -> float:
        """Calculate cumulative score for a debate position."""
        score = 0.0
        for r in rounds:
            if position == DebatePosition.BULL:
                args = r.bull_arguments
            elif position == DebatePosition.BEAR:
                args = r.bear_arguments
            else:
                args = r.neutral_arguments
            score += sum(a.confidence * self._strength_weight(a.strength) for a in args)
        return score / max(len(rounds), 1)

    def _strength_weight(self, strength: ArgumentStrength) -> float:
        """Convert argument strength to numeric weight."""
        weights = {
            ArgumentStrength.VERY_STRONG: 1.0,
            ArgumentStrength.STRONG: 0.8,
            ArgumentStrength.MODERATE: 0.5,
            ArgumentStrength.WEAK: 0.3,
            ArgumentStrength.SPECULATIVE: 0.1,
        }
        return weights.get(strength, 0.5)

    def _generate_summary(self, topic: str, result: DebateResult) -> str:
        """Generate a debate summary."""
        if result.consensus_reached:
            return f"Consensus reached on {topic}: NEUTRAL - balanced risk-reward, further monitoring recommended"
        if result.final_winner == DebatePosition.BULL:
            return f"Debate conclusion on {topic}: BULL case prevails (score: {result.bull_score:.2f} vs {result.bear_score:.2f})"
        if result.final_winner == DebatePosition.BEAR:
            return f"Debate conclusion on {topic}: BEAR case prevails (score: {result.bear_score:.2f} vs {result.bull_score:.2f})"
        return f"Debate on {topic}: inconclusive"

    def _generate_recommendations(self, topic: str, result: DebateResult) -> List[str]:
        """Generate actionable recommendations from debate."""
        recommendations = []
        if result.final_winner == DebatePosition.BULL:
            recommendations.append(f"Consider initiating position in {topic}")
            recommendations.append("Set stop-loss at support levels")
            recommendations.append("Monitor for adverse developments")
        elif result.final_winner == DebatePosition.BEAR:
            recommendations.append(f"Avoid or reduce exposure to {topic}")
            recommendations.append("Wait for better entry point")
            recommendations.append("Consider hedging strategies")
        else:
            recommendations.append(f"Maintain neutral stance on {topic}")
            recommendations.append("Gather more data before decision")
            recommendations.append("Set up monitoring alerts")
        return recommendations

    def _identify_risk_flags(self, topic: str, result: DebateResult) -> List[str]:
        """Identify risk flags from the debate."""
        flags = []
        if result.bull_score > result.bear_score * 1.5:
            flags.append("Strong bullish consensus - guard against groupthink")
        if result.bear_score > result.bull_score * 1.5:
            flags.append("Strong bearish consensus - may miss opportunities")
        if abs(result.bull_score - result.bear_score) < 0.15:
            flags.append("Highly contested - high uncertainty environment")
        return flags
