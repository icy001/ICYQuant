"""
ICYQuant Consensus Engine — multi-agent consensus building after debate.

Builds consensus from debate outcomes, vote results, and agent opinions.
Generates unified decisions with dissenting opinion tracking and confidence
scoring.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .agent_message import OpinionMessage, VoteMessage

logger = logging.getLogger(__name__)


class ConsensusLevel(str, Enum):
    FULL = "full"              # All agents agree
    STRONG = "strong"          # >80% agreement
    MODERATE = "moderate"      # 60-80% agreement
    WEAK = "weak"             # 50-60% agreement
    DIVIDED = "divided"        # No majority
    NO_CONSENSUS = "no_consensus"


@dataclass
class ConsensusResult:
    """Result of a consensus-building session."""
    consensus_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""

    # Agreement metrics
    level: ConsensusLevel = ConsensusLevel.NO_CONSENSUS
    agreement_score: float = 0.0  # 0-1 scale
    confidence: float = 0.0

    # Participant summary
    total_participants: int = 0
    agree_count: int = 0
    disagree_count: int = 0
    abstain_count: int = 0

    # Decision
    decision: str = ""
    decision_rationale: str = ""

    # Dissenting opinions (preserved for transparency)
    dissenting_opinions: list[OpinionMessage] = field(default_factory=list)
    minority_report: str = ""

    # Action items
    action_items: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ConsensusEngine:
    """Builds consensus from multi-agent deliberation.

    Process:
        1. Collect opinions from all participating agents
        2. Aggregate voting results
        3. Calculate agreement metrics
        4. Determine consensus level
        5. Generate unified decision
        6. Document dissenting opinions
        7. Produce minority report if needed
    """

    def __init__(self) -> None:
        self._results: dict[str, ConsensusResult] = {}
        self._total_consensus = 0

    async def build_consensus(self,
                              topic: str,
                              opinions: list[OpinionMessage],
                              votes: Optional[list[VoteMessage]] = None,
                              debate_outcome: Optional[Any] = None,
                              metadata: Optional[dict[str, Any]] = None) -> ConsensusResult:
        """Build consensus from collected opinions and votes."""
        result = ConsensusResult(topic=topic, metadata=metadata or {})
        self._results[result.consensus_id] = result
        self._total_consensus += 1

        # Count participants
        result.total_participants = len(opinions)

        # Count agreement from opinions
        agrees = [o for o in opinions if o.stance == "agree"]
        disagrees = [o for o in opinions if o.stance == "disagree"]
        neutrals = [o for o in opinions if o.stance == "neutral"]

        result.agree_count = len(agrees)
        result.disagree_count = len(disagrees)
        result.abstain_count = len(neutrals)

        # Calculate agreement score
        if result.total_participants > 0:
            result.agreement_score = result.agree_count / result.total_participants

        # Calculate confidence from opinion confidence scores
        confidences = [o.confidence for o in opinions if o.confidence > 0]
        if confidences:
            result.confidence = sum(confidences) / len(confidences)

        # Determine consensus level
        result.level = self._determine_level(result.agreement_score, result.total_participants)

        # Collect dissenting opinions
        result.dissenting_opinions = disagrees

        # Generate minority report if divided
        if result.level in (ConsensusLevel.DIVIDED, ConsensusLevel.NO_CONSENSUS):
            result.minority_report = self._generate_minority_report(disagrees)

        # Generate decision
        result.decision, result.decision_rationale = self._generate_decision(
            result, agrees, disagrees
        )

        # Generate action items
        result.action_items = self._generate_action_items(result)

        logger.info("Consensus built: level=%s score=%.2f participants=%d",
                     result.level.value, result.agreement_score, result.total_participants)

        return result

    def _determine_level(self, score: float, total: int) -> ConsensusLevel:
        """Determine consensus level from agreement score."""
        if total < 2:
            return ConsensusLevel.NO_CONSENSUS
        if score >= 1.0:
            return ConsensusLevel.FULL
        if score >= 0.8:
            return ConsensusLevel.STRONG
        if score >= 0.6:
            return ConsensusLevel.MODERATE
        if score >= 0.5:
            return ConsensusLevel.WEAK
        if score >= 0.3:
            return ConsensusLevel.DIVIDED
        return ConsensusLevel.NO_CONSENSUS

    def _generate_decision(self, result: ConsensusResult,
                           agrees: list[OpinionMessage],
                           disagrees: list[OpinionMessage]) -> tuple[str, str]:
        """Generate a decision statement from consensus."""
        if result.level == ConsensusLevel.FULL:
            return "APPROVED", "All agents unanimously agree."
        elif result.level == ConsensusLevel.STRONG:
            return "APPROVED", f"Strong consensus ({result.agreement_score:.0%} agreement)."
        elif result.level == ConsensusLevel.MODERATE:
            conds = [o.reasoning for o in disagrees[:2]]
            rationale = f"Moderate consensus with {result.disagree_count} dissenting. Conditions: {'; '.join(conds)}"
            return "APPROVED_WITH_CONDITIONS", rationale
        elif result.level == ConsensusLevel.WEAK:
            return "NEEDS_REVIEW", "Weak consensus — additional review required."
        elif result.level == ConsensusLevel.DIVIDED:
            return "ESCALATE", "Agents are divided. Escalating for human review."
        else:
            return "REJECTED", "No consensus reached."

    def _generate_minority_report(self, disagrees: list[OpinionMessage]) -> str:
        """Generate a minority report from dissenting opinions."""
        if not disagrees:
            return ""
        parts = []
        for op in disagrees[:3]:
            parts.append(f"[{op.author_id}] {op.reasoning}")
        return "\n".join(parts)

    def _generate_action_items(self, result: ConsensusResult) -> list[str]:
        """Generate action items from consensus outcome."""
        items = []
        if result.level == ConsensusLevel.MODERATE:
            items.append("Address conditions raised by dissenting agents")
            items.append("Validate with additional backtest under modified assumptions")
        elif result.level == ConsensusLevel.WEAK:
            items.append("Re-run analysis with expanded data window")
            items.append("Obtain second opinion from external reviewer agent")
        elif result.level in (ConsensusLevel.DIVIDED, ConsensusLevel.NO_CONSENSUS):
            items.append("Escalate to human portfolio manager for decision")
            items.append("Document all positions with evidence for audit trail")
        return items

    def get_result(self, consensus_id: str) -> Optional[ConsensusResult]:
        return self._results.get(consensus_id)

    @property
    def total_consensus(self) -> int:
        return self._total_consensus
