"""Feedback Engine — closed-loop feedback from execution results back into the learning pipeline.

Pipeline:
    Performance Report -> FeedbackEngine.process()
        -> Extract feedback signals
        -> Identify improvement areas
        -> Route feedback to learning pipeline
        -> Update adaptive policy
        -> Output Feedback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    PERFORMANCE = "performance"
    SIGNAL_QUALITY = "signal_quality"
    RISK_ADJUSTMENT = "risk_adjustment"
    EXECUTION_QUALITY = "execution_quality"
    MODEL_UPDATE = "model_update"


class FeedbackSeverity(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class Feedback:
    """A feedback signal from the execution pipeline.

    Attributes:
        feedback_id: Unique identifier.
        feedback_type: Type of feedback.
        severity: Feedback severity.
        source: Source of feedback (e.g. performance_report_id).
        summary: Human-readable summary.
        metrics: Structured feedback metrics.
        suggestions: Improvement suggestions.
        created_at: Creation timestamp.
    """

    feedback_id: str = ""
    feedback_type: FeedbackType = FeedbackType.PERFORMANCE
    severity: FeedbackSeverity = FeedbackSeverity.NEUTRAL
    source: str = ""
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FeedbackEngine:
    """Processes execution feedback and routes it to the learning pipeline.

    Extracts actionable feedback from performance reviews and routes it
    to the learning pipeline and adaptive policy engine for continuous
    improvement.

    Supports:
        - Performance feedback extraction
        - Signal quality assessment
        - Risk adjustment recommendations
        - Execution quality scoring
        - Feedback routing to learning pipeline

    Usage:
        engine = FeedbackEngine()
        await engine.initialize()
        feedback = await engine.process(performance_report)
        await engine.route_to_learning(feedback)
    """

    def __init__(self, max_feedback: int = 200) -> None:
        self._feedback_list: List[Feedback] = []
        self._max_feedback = max_feedback
        self._counter: int = 0
        self._learning_pipeline: Optional[Any] = None
        self._initialized: bool = False
        logger.info("FeedbackEngine created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("FeedbackEngine initialized")

    async def shutdown(self) -> None:
        self._feedback_list.clear()
        self._initialized = False
        logger.info("FeedbackEngine shutdown complete")

    def set_learning_pipeline(self, pipeline: Any) -> None:
        self._learning_pipeline = pipeline

    async def process(self, performance_report: Any) -> List[Feedback]:
        """Process a performance report into feedback signals.

        Args:
            performance_report: PerformanceReport to process.

        Returns:
            List of Feedback signals.
        """
        logger.info("FeedbackEngine.process() started")
        feedback_list: List[Feedback] = []

        deviation = getattr(performance_report, "deviation", 0.0)
        self._counter += 1
        severity = FeedbackSeverity.POSITIVE if deviation >= 0 else FeedbackSeverity.NEGATIVE

        fb = Feedback(
            feedback_id=f"fb_{self._counter}",
            feedback_type=FeedbackType.PERFORMANCE,
            severity=severity,
            source=getattr(performance_report, "report_id", ""),
            summary=f"Performance deviation: {deviation:.4f}",
            metrics={"deviation": deviation},
        )
        feedback_list.append(fb)

        self._feedback_list.extend(feedback_list)
        if len(self._feedback_list) > self._max_feedback:
            self._feedback_list = self._feedback_list[-self._max_feedback:]

        logger.info("FeedbackEngine.process() completed: %d feedback items", len(feedback_list))
        return feedback_list

    async def route_to_learning(self, feedback: Feedback) -> None:
        if self._learning_pipeline:
            await self._learning_pipeline.ingest_feedback(feedback)

    def get_summary(self) -> Dict[str, Any]:
        positive = sum(1 for f in self._feedback_list if f.severity == FeedbackSeverity.POSITIVE)
        negative = sum(1 for f in self._feedback_list if f.severity == FeedbackSeverity.NEGATIVE)
        return {
            "initialized": self._initialized,
            "total_feedback": len(self._feedback_list),
            "positive": positive,
            "negative": negative,
        }
