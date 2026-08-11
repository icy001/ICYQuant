"""
ICYQuant Evidence Manager — evidence tracking and validation for agent claims.

Manages evidence chains linking agent outputs to their supporting data,
sources, and methodology. Provides evidence scoring, citation tracking,
and reproducibility verification.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EvidenceType(str, Enum):
    BACKTEST = "backtest"
    HISTORICAL = "historical"
    STATISTICAL = "statistical"
    THEORETICAL = "theoretical"
    EXPERT_OPINION = "expert_opinion"
    MARKET_DATA = "market_data"
    LITERATURE = "literature"
    SIMULATION = "simulation"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    ANECDOTAL = "anecdotal"
    UNVERIFIED = "unverified"


@dataclass
class Evidence:
    """A single piece of evidence supporting a claim."""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    claim_id: str = ""
    evidence_type: EvidenceType = EvidenceType.HISTORICAL
    strength: EvidenceStrength = EvidenceStrength.UNVERIFIED
    description: str = ""
    source: str = ""
    data_reference: str = ""       # URI or reference to supporting data
    methodology: str = ""          # How the evidence was derived
    confidence: float = 0.0

    # Reproducibility
    reproducible: bool = False
    reproduction_steps: list[str] = field(default_factory=list)

    # Citations
    citations: list[str] = field(default_factory=list)
    peer_reviewed: bool = False

    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceChain:
    """A chain of evidence supporting a single claim."""
    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    claim: str = ""
    claim_agent_id: str = ""

    evidence_items: list[Evidence] = field(default_factory=list)

    # Aggregated scores
    total_evidence_count: int = 0
    strong_evidence_count: int = 0
    overall_strength: EvidenceStrength = EvidenceStrength.UNVERIFIED
    aggregated_confidence: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceManager:
    """Manages evidence chains for multi-agent research claims.

    Responsibilities:
        - Register evidence items linked to agent claims
        - Build and track evidence chains
        - Score evidence strength and reliability
        - Verify reproducibility of evidence
        - Cross-reference evidence across agents
        - Flag unsupported or weak claims
    """

    def __init__(self) -> None:
        self._evidence: dict[str, Evidence] = {}
        self._chains: dict[str, EvidenceChain] = {}
        self._claim_to_chain: dict[str, str] = {}  # claim_id → chain_id
        self._total_evidence = 0

    # ── Evidence Registration ──

    def add_evidence(self, evidence: Evidence) -> Evidence:
        """Register a new evidence item."""
        evidence.strength = self._assess_strength(evidence)
        self._evidence[evidence.evidence_id] = evidence
        self._total_evidence += 1

        # Add to evidence chain
        if evidence.claim_id:
            chain = self._get_or_create_chain(evidence.claim_id, evidence.created_by)
            chain.evidence_items.append(evidence)
            chain.total_evidence_count = len(chain.evidence_items)
            chain.strong_evidence_count = sum(
                1 for e in chain.evidence_items if e.strength == EvidenceStrength.STRONG
            )
            self._recalculate_chain(chain)

        logger.debug("Evidence %s added: type=%s strength=%s",
                      evidence.evidence_id, evidence.evidence_type.value,
                      evidence.strength.value)
        return evidence

    def add_evidence_batch(self, items: list[Evidence]) -> int:
        """Register multiple evidence items."""
        for item in items:
            self.add_evidence(item)
        return len(items)

    # ── Evidence Chain ──

    def get_chain(self, claim_id: str) -> Optional[EvidenceChain]:
        """Get the evidence chain for a claim."""
        chain_id = self._claim_to_chain.get(claim_id)
        if chain_id:
            return self._chains.get(chain_id)
        return None

    def get_unverified_claims(self) -> list[EvidenceChain]:
        """Get claims with unverified or weak evidence."""
        return [
            chain for chain in self._chains.values()
            if chain.overall_strength in (EvidenceStrength.UNVERIFIED, EvidenceStrength.WEAK, EvidenceStrength.ANECDOTAL)
        ]

    def get_verified_claims(self) -> list[EvidenceChain]:
        """Get claims with strong or moderate evidence."""
        return [
            chain for chain in self._chains.values()
            if chain.overall_strength in (EvidenceStrength.STRONG, EvidenceStrength.MODERATE)
        ]

    # ── Evidence Scoring ──

    def _assess_strength(self, evidence: Evidence) -> EvidenceStrength:
        """Score an evidence item's strength."""
        score = 0

        # Type-based scoring
        type_scores = {
            EvidenceType.BACKTEST: 3,
            EvidenceType.HISTORICAL: 2,
            EvidenceType.STATISTICAL: 3,
            EvidenceType.THEORETICAL: 1,
            EvidenceType.EXPERT_OPINION: 1,
            EvidenceType.MARKET_DATA: 2,
            EvidenceType.LITERATURE: 2,
            EvidenceType.SIMULATION: 2,
        }
        score += type_scores.get(evidence.evidence_type, 1)

        # Reproducibility bonus
        if evidence.reproducible:
            score += 2

        # Peer-reviewed bonus
        if evidence.peer_reviewed:
            score += 1

        # Source quality
        if evidence.source:
            score += 1

        # Methodology documentation
        if evidence.methodology:
            score += 1

        if score >= 5:
            return EvidenceStrength.STRONG
        if score >= 3:
            return EvidenceStrength.MODERATE
        if score >= 2:
            return EvidenceStrength.WEAK
        if score >= 1:
            return EvidenceStrength.ANECDOTAL
        return EvidenceStrength.UNVERIFIED

    def _recalculate_chain(self, chain: EvidenceChain) -> None:
        """Recalculate overall chain strength and confidence."""
        if not chain.evidence_items:
            chain.overall_strength = EvidenceStrength.UNVERIFIED
            chain.aggregated_confidence = 0.0
            return

        # Determine overall strength (best item determines)
        strength_order = {
            EvidenceStrength.STRONG: 4,
            EvidenceStrength.MODERATE: 3,
            EvidenceStrength.WEAK: 2,
            EvidenceStrength.ANECDOTAL: 1,
            EvidenceStrength.UNVERIFIED: 0,
        }
        best = max(chain.evidence_items, key=lambda e: strength_order.get(e.strength, 0))
        chain.overall_strength = best.strength

        # Aggregate confidence
        confidences = [e.confidence for e in chain.evidence_items if e.confidence > 0]
        chain.aggregated_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # ── Internal ──

    def _get_or_create_chain(self, claim_id: str, agent_id: str) -> EvidenceChain:
        """Get or create an evidence chain for a claim."""
        if claim_id in self._claim_to_chain:
            chain_id = self._claim_to_chain[claim_id]
            if chain_id in self._chains:
                return self._chains[chain_id]

        chain = EvidenceChain(claim=claim_id, claim_agent_id=agent_id)
        self._chains[chain.chain_id] = chain
        self._claim_to_chain[claim_id] = chain.chain_id
        return chain

    # ── Stats ──

    @property
    def total_evidence(self) -> int:
        return self._total_evidence

    @property
    def chain_count(self) -> int:
        return len(self._chains)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the evidence manager state."""
        chains = list(self._chains.values())
        return {
            "total_evidence": self._total_evidence,
            "total_chains": len(chains),
            "verified_claims": len(self.get_verified_claims()),
            "unverified_claims": len(self.get_unverified_claims()),
            "avg_confidence": sum(c.aggregated_confidence for c in chains) / max(len(chains), 1),
        }
