"""
ICYQuant Hypothesis Engine — systematic hypothesis generation and validation.

Guides the research process from observation → hypothesis → evidence
→ validation → conclusion, ensuring rigorous quantitative methodology.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class HypothesisType(str, Enum):
    DIRECTIONAL = "directional"
    NON_DIRECTIONAL = "non_directional"
    CAUSAL = "causal"
    CORRELATIONAL = "correlational"


@dataclass
class Hypothesis:
    """A testable research hypothesis."""
    hypothesis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    statement: str = ""
    null_hypothesis: str = ""
    alternative_hypothesis: str = ""
    hypothesis_type: HypothesisType = HypothesisType.DIRECTIONAL
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0
    supporting_evidence: list[dict[str, Any]] = field(default_factory=list)
    counter_evidence: list[dict[str, Any]] = field(default_factory=list)
    test_methodology: str = ""
    test_results: Optional[dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class HypothesisEngine:
    """Systematic hypothesis generation and validation engine.

    Research workflow:
        Observation → Hypothesis → Evidence → Validation → Conclusion

    Supports:
        - Multiple hypothesis types (directional, non-directional, causal, correlational)
        - Null/alternative formulation
        - Evidence tracking (supporting + counter)
        - Confidence scoring
        - Test methodology specification
    """

    def __init__(self) -> None:
        self._hypotheses: dict[str, Hypothesis] = {}
        self._total_generated = 0

    async def generate(
        self,
        question: str,
        documents: list[dict[str, Any]],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Generate testable hypotheses from a research question and context.

        In production, this would use an LLM. Here we use pattern-based generation.
        """
        self._total_generated += 1

        hypotheses: list[Hypothesis] = []
        question_lower = question.lower()

        # Pattern 1: Directional hypothesis
        if any(kw in question_lower for kw in ["increase", "decrease", "higher", "lower", "more", "less"]):
            h = Hypothesis(
                statement=f"Directional effect for: {question[:100]}",
                null_hypothesis="There is no directional effect",
                alternative_hypothesis="There is a statistically significant directional effect",
                hypothesis_type=HypothesisType.DIRECTIONAL,
                confidence=0.6,
            )
            hypotheses.append(h)

        # Pattern 2: Correlational hypothesis
        if any(kw in question_lower for kw in ["correlation", "relationship", "link", "association"]):
            h = Hypothesis(
                statement=f"Correlation exists for: {question[:100]}",
                null_hypothesis="There is no significant correlation",
                alternative_hypothesis="There is a statistically significant correlation",
                hypothesis_type=HypothesisType.CORRELATIONAL,
                confidence=0.5,
            )
            hypotheses.append(h)

        # Pattern 3: Causal hypothesis
        if any(kw in question_lower for kw in ["cause", "effect", "impact", "influence", "drive"]):
            h = Hypothesis(
                statement=f"Causal relationship for: {question[:100]}",
                null_hypothesis="There is no causal relationship",
                alternative_hypothesis="There is a statistically significant causal relationship",
                hypothesis_type=HypothesisType.CAUSAL,
                confidence=0.4,
            )
            hypotheses.append(h)

        # Default: at least one hypothesis
        if not hypotheses:
            h = Hypothesis(
                statement=f"Research hypothesis for: {question[:100]}",
                null_hypothesis="No significant effect exists",
                alternative_hypothesis="A significant effect exists",
                hypothesis_type=HypothesisType.NON_DIRECTIONAL,
                confidence=0.5,
            )
            hypotheses.append(h)

        # Register all generated hypotheses
        for h in hypotheses:
            self._hypotheses[h.hypothesis_id] = h

        # Add document evidence
        for h in hypotheses:
            for doc in documents[:5]:
                h.supporting_evidence.append({
                    "doc_id": doc.get("doc_id", ""),
                    "title": doc.get("title", ""),
                    "relevance": doc.get("score", 0.0),
                })

        return [
            {
                "hypothesis_id": h.hypothesis_id,
                "statement": h.statement,
                "null_hypothesis": h.null_hypothesis,
                "alternative_hypothesis": h.alternative_hypothesis,
                "type": h.hypothesis_type.value,
                "status": h.status.value,
                "confidence": h.confidence,
                "evidence_count": len(h.supporting_evidence),
            }
            for h in hypotheses
        ]

    def validate(self, hypothesis_id: str, test_results: dict[str, Any]) -> Hypothesis:
        """Record test results and update hypothesis status."""
        h = self._hypotheses.get(hypothesis_id)
        if h is None:
            raise ValueError(f"Hypothesis {hypothesis_id} not found")

        h.test_results = test_results
        h.status = HypothesisStatus.TESTING

        p_value = test_results.get("p_value", 1.0)
        if p_value < 0.05:
            h.status = HypothesisStatus.SUPPORTED
            h.confidence = 1.0 - p_value
        elif p_value < 0.10:
            h.status = HypothesisStatus.INCONCLUSIVE
            h.confidence = 0.5
        else:
            h.status = HypothesisStatus.REJECTED
            h.confidence = 0.0

        return h

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        return self._hypotheses.get(hypothesis_id)

    @property
    def total_generated(self) -> int:
        return self._total_generated

    @property
    def active_count(self) -> int:
        return sum(1 for h in self._hypotheses.values() if h.status in (
            HypothesisStatus.PROPOSED, HypothesisStatus.TESTING
        ))
