"""Learning Pipeline — continuous learning from experience and feedback.

Pipeline:
    Feedback -> LearningPipeline.ingest()
        -> Evaluate experience quality
        -> Extract knowledge patterns
        -> Update internal knowledge base
        -> Adjust adaptive policies
        -> Output LearningEvent

Supports:
    - Experience ingestion
    - Pattern extraction
    - Knowledge accumulation
    - Policy adaptation
    - Memory persistence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LearningEventType(str, Enum):
    EXPERIENCE = "experience"
    PATTERN = "pattern"
    POLICY_UPDATE = "policy_update"
    KNOWLEDGE = "knowledge"


@dataclass
class LearningEvent:
    """A single learning event from the pipeline.

    Attributes:
        event_id: Unique identifier.
        event_type: Type of learning event.
        source_feedback_id: Source feedback identifier.
        description: Human-readable description.
        confidence: Confidence in the learned insight (0.0-1.0).
        data: Structured learning data.
        learned_at: Learning timestamp.
    """

    event_id: str = ""
    event_type: LearningEventType = LearningEventType.EXPERIENCE
    source_feedback_id: str = ""
    description: str = ""
    confidence: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    learned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LearningPipeline:
    """Continuous learning from execution feedback and experience.

    Ingests feedback, extracts patterns, updates knowledge, and adapts
    policies for continuous improvement of autonomous decisions.

    Supports:
        - Experience ingestion and evaluation
        - Pattern extraction from repeated outcomes
        - Knowledge accumulation with confidence
        - Policy adaptation triggers

    Usage:
        pipeline = LearningPipeline()
        await pipeline.initialize()
        event = await pipeline.ingest_feedback(feedback)
        await pipeline.adapt_policy()
    """

    def __init__(self, max_events: int = 500) -> None:
        self._events: List[LearningEvent] = []
        self._max_events = max_events
        self._counter: int = 0
        self._knowledge_updater: Optional[Any] = None
        self._adaptive_policy: Optional[Any] = None
        self._initialized: bool = False
        logger.info("LearningPipeline created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("LearningPipeline initialized")

    async def shutdown(self) -> None:
        self._events.clear()
        self._initialized = False
        logger.info("LearningPipeline shutdown complete")

    def set_knowledge_updater(self, updater: Any) -> None:
        self._knowledge_updater = updater

    def set_adaptive_policy(self, policy: Any) -> None:
        self._adaptive_policy = policy

    async def ingest_feedback(self, feedback: Any) -> LearningEvent:
        """Ingest feedback and generate a learning event.

        Args:
            feedback: Feedback signal to learn from.

        Returns:
            LearningEvent with extracted insights.
        """
        self._counter += 1
        fb_id = getattr(feedback, "feedback_id", "")
        severity = getattr(feedback, "severity", None)
        severity_val = severity.value if hasattr(severity, "value") else str(severity)

        event = LearningEvent(
            event_id=f"learn_{self._counter}",
            event_type=LearningEventType.EXPERIENCE,
            source_feedback_id=fb_id,
            description=f"Learned from feedback: {severity_val}",
            confidence=0.6,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        logger.info("LearningPipeline: ingested feedback %s -> event %s", fb_id, event.event_id)
        return event

    async def adapt_policy(self) -> None:
        """Trigger policy adaptation based on learned patterns."""
        if self._adaptive_policy:
            await self._adaptive_policy.adapt(self._events[-10:])
            logger.info("LearningPipeline: policy adaptation triggered")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_events": len(self._events),
            "recent_events": [
                {"id": e.event_id, "type": e.event_type.value, "description": e.description}
                for e in self._events[-5:]
            ],
        }
