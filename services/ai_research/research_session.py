"""
ICYQuant Research Session — stateful research conversation context.

Tracks the full lifecycle of a single research interaction including
question history, context accumulation, intermediate results, and
session metadata.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class ResearchSession:
    """A stateful research conversation session.

    Tracks:
        - User identity and session metadata
        - Question-answer history
        - Accumulated context across turns
        - Citations and evidence collected
        - Final report when completed
    """

    user_id: str
    title: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Conversation history
    turns: list[dict[str, Any]] = field(default_factory=list)

    # Accumulated context
    context: dict[str, Any] = field(default_factory=dict)

    # Collected artifacts
    citations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)

    # Final output
    report: Optional[dict[str, Any]] = None
    artifacts: list[str] = field(default_factory=list)

    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_turn(self, question: str, answer: dict[str, Any]) -> None:
        """Record a question-answer turn in the conversation."""
        turn = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.turns.append(turn)
        self.updated_at = datetime.now(timezone.utc)

    def add_context(self, key: str, value: Any) -> None:
        """Accumulate context for subsequent research turns."""
        self.context[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def add_citation(self, citation: dict[str, Any]) -> None:
        self.citations.append(citation)

    def add_evidence(self, evidence_item: dict[str, Any]) -> None:
        self.evidence.append(evidence_item)

    def add_hypothesis(self, hypothesis: dict[str, Any]) -> None:
        self.hypotheses.append(hypothesis)

    def set_report(self, report: dict[str, Any]) -> None:
        self.report = report
        self.updated_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        self.status = SessionStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        self.status = SessionStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)

    def pause(self) -> None:
        self.status = SessionStatus.PAUSED
        self.updated_at = datetime.now(timezone.utc)

    def resume(self) -> None:
        self.status = SessionStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "title": self.title,
            "status": self.status.value,
            "turn_count": self.turn_count,
            "citation_count": len(self.citations),
            "evidence_count": len(self.evidence),
            "hypothesis_count": len(self.hypotheses),
            "has_report": self.report is not None,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
