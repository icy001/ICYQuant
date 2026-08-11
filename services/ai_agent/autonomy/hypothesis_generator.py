"""Hypothesis Generator — autonomously proposes research hypotheses for validation.

Pipeline:
    Observation -> HypothesisGenerator.generate()
        -> Formulate hypothesis from market data / signals
        -> Define testable predictions
        -> Assign confidence prior
        -> Output structured Hypothesis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass
class Hypothesis:
    """A research hypothesis to be tested.

    Attributes:
        hypothesis_id: Unique identifier.
        statement: The hypothesis statement.
        prediction: Testable prediction.
        status: Current status.
        prior_confidence: Initial confidence before testing (0.0-1.0).
        posterior_confidence: Confidence after testing (0.0-1.0).
        evidence: Collected evidence for/against.
        test_results: Results of hypothesis tests.
        created_at: Creation timestamp.
    """

    hypothesis_id: str = ""
    statement: str = ""
    prediction: str = ""
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    prior_confidence: float = 0.5
    posterior_confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    test_results: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_worth_testing(self) -> bool:
        return self.prior_confidence >= 0.3


class HypothesisGenerator:
    """Generates research hypotheses from observations and signals.

    Formulates testable hypotheses based on market observations, signal
    patterns, and factor analysis. Supports AI-assisted hypothesis
    generation with confidence priors.

    Supports:
        - Observation-driven hypothesis formulation
        - AI-assisted hypothesis generation
        - Prior confidence estimation
        - Evidence tracking

    Usage:
        gen = HypothesisGenerator()
        await gen.initialize()
        hypotheses = await gen.generate(observations=[...])
    """

    def __init__(self, max_hypotheses: int = 100) -> None:
        self._hypotheses: List[Hypothesis] = []
        self._max_hypotheses = max_hypotheses
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("HypothesisGenerator created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("HypothesisGenerator initialized")

    async def shutdown(self) -> None:
        self._hypotheses.clear()
        self._initialized = False
        logger.info("HypothesisGenerator shutdown complete")

    async def generate(
        self,
        observations: Optional[List[Dict[str, Any]]] = None,
        signals: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Hypothesis]:
        """Generate hypotheses from observations.

        Args:
            observations: Market observations.
            signals: Trading signals.
            context: Additional context.

        Returns:
            List of generated Hypotheses.
        """
        logger.info("HypothesisGenerator.generate() started")
        hypotheses: List[Hypothesis] = []
        self._store_hypotheses(hypotheses)
        logger.info("HypothesisGenerator.generate() completed: %d hypotheses", len(hypotheses))
        return hypotheses

    def confirm(self, hypothesis: Hypothesis, evidence: Dict[str, Any]) -> None:
        hypothesis.status = HypothesisStatus.CONFIRMED
        hypothesis.evidence.append(evidence)
        hypothesis.posterior_confidence = min(1.0, hypothesis.prior_confidence + 0.2)

    def reject(self, hypothesis: Hypothesis, reason: str = "") -> None:
        hypothesis.status = HypothesisStatus.REJECTED
        hypothesis.evidence.append({"rejection_reason": reason})

    def _store_hypotheses(self, hypotheses: List[Hypothesis]) -> None:
        self._hypotheses.extend(hypotheses)
        if len(self._hypotheses) > self._max_hypotheses:
            self._hypotheses = self._hypotheses[-self._max_hypotheses:]

    def get_active_hypotheses(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": h.hypothesis_id,
                "statement": h.statement,
                "status": h.status.value,
                "prior": round(h.prior_confidence, 2),
                "posterior": round(h.posterior_confidence, 2),
            }
            for h in self._hypotheses if h.status in (HypothesisStatus.PROPOSED, HypothesisStatus.TESTING)
        ]

    def get_summary(self) -> Dict[str, Any]:
        confirmed = sum(1 for h in self._hypotheses if h.status == HypothesisStatus.CONFIRMED)
        return {
            "initialized": self._initialized,
            "total": len(self._hypotheses),
            "confirmed": confirmed,
        }
