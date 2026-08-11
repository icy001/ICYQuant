"""
ICYQuant Evidence Engine — systematic evidence collection and evaluation.

Gathers, evaluates, and weighs evidence for and against research
hypotheses, providing a structured framework for evidence-based
quantitative research.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EvidenceDirection(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INCONCLUSIVE = "inconclusive"


@dataclass
class EvidenceItem:
    """A single piece of evidence."""
    evidence_id: str
    hypothesis_id: str
    direction: EvidenceDirection
    strength: EvidenceStrength
    description: str
    source_doc_id: str = ""
    source_title: str = ""
    relevance_score: float = 0.0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceEngine:
    """Systematic evidence collection and evaluation engine.

    Responsibilities:
        - Gather evidence from retrieved documents
        - Classify evidence direction (supports/contradicts/neutral)
        - Assess evidence strength
        - Aggregate evidence per hypothesis
        - Track provenance for citation
    """

    def __init__(self) -> None:
        self._evidence_items: dict[str, EvidenceItem] = {}
        self._total_collected = 0

    async def collect(
        self,
        hypotheses: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Collect evidence for a set of hypotheses from documents."""
        evidence_list: list[dict[str, Any]] = []

        for hypothesis in hypotheses:
            hypothesis_id = hypothesis.get("hypothesis_id", "")
            statement = hypothesis.get("statement", "").lower()

            for doc in documents:
                doc_content = doc.get("snippet", doc.get("content", "")).lower()
                doc_id = doc.get("doc_id", "")
                doc_title = doc.get("title", "")
                relevance = doc.get("score", 0.0)

                # Determine evidence direction based on content signals
                direction = self._classify_direction(statement, doc_content)

                # Determine strength based on relevance and match quality
                strength = self._assess_strength(relevance, doc_content)

                item = EvidenceItem(
                    evidence_id=f"{hypothesis_id}_{doc_id}",
                    hypothesis_id=hypothesis_id,
                    direction=direction,
                    strength=strength,
                    description=doc.get("snippet", "")[:300],
                    source_doc_id=doc_id,
                    source_title=doc_title,
                    relevance_score=relevance,
                    confidence=relevance * 0.8,
                )

                self._evidence_items[item.evidence_id] = item
                self._total_collected += 1

                evidence_list.append({
                    "evidence_id": item.evidence_id,
                    "hypothesis_id": item.hypothesis_id,
                    "direction": item.direction.value,
                    "strength": item.strength.value,
                    "description": item.description,
                    "source_doc_id": item.source_doc_id,
                    "source_title": item.source_title,
                    "relevance_score": item.relevance_score,
                    "confidence": item.confidence,
                })

        return evidence_list

    def _classify_direction(self, hypothesis: str, content: str) -> EvidenceDirection:
        """Classify whether content supports or contradicts a hypothesis."""
        # In production, this would use an LLM or trained classifier
        # Simple keyword heuristic:
        positive_signals = ["supports", "confirms", "evidence suggests", "consistent with", "demonstrates"]
        negative_signals = ["contradicts", "does not support", "inconsistent", "no evidence", "fails to"]

        pos_count = sum(1 for s in positive_signals if s in content)
        neg_count = sum(1 for s in negative_signals if s in content)

        if pos_count > neg_count:
            return EvidenceDirection.SUPPORTS
        elif neg_count > pos_count:
            return EvidenceDirection.CONTRADICTS
        return EvidenceDirection.NEUTRAL

    def _assess_strength(self, relevance: float, content: str) -> EvidenceStrength:
        """Assess the strength of a piece of evidence."""
        if relevance > 0.8 and len(content) > 200:
            return EvidenceStrength.STRONG
        elif relevance > 0.5:
            return EvidenceStrength.MODERATE
        elif relevance > 0.2:
            return EvidenceStrength.WEAK
        return EvidenceStrength.INCONCLUSIVE

    def get_evidence_for_hypothesis(self, hypothesis_id: str) -> list[EvidenceItem]:
        """Get all evidence for a specific hypothesis."""
        return [
            e for e in self._evidence_items.values()
            if e.hypothesis_id == hypothesis_id
        ]

    def get_summary(self, hypothesis_id: str) -> dict[str, Any]:
        """Get an evidence summary for a hypothesis."""
        items = self.get_evidence_for_hypothesis(hypothesis_id)
        supporting = sum(1 for e in items if e.direction == EvidenceDirection.SUPPORTS)
        contradicting = sum(1 for e in items if e.direction == EvidenceDirection.CONTRADICTS)
        neutral = sum(1 for e in items if e.direction == EvidenceDirection.NEUTRAL)

        return {
            "hypothesis_id": hypothesis_id,
            "total_evidence": len(items),
            "supporting": supporting,
            "contradicting": contradicting,
            "neutral": neutral,
            "strong_evidence": sum(1 for e in items if e.strength == EvidenceStrength.STRONG),
            "verdict": "supported" if supporting > contradicting else (
                "contradicted" if contradicting > supporting else "inconclusive"
            ),
        }

    @property
    def total_collected(self) -> int:
        return self._total_collected
