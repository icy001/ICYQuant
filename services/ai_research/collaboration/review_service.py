"""
ICYQuant Collaboration — review service for research quality assurance.

Enables structured peer review of research outputs including reports,
hypotheses, and experiments with scoring and feedback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReviewTarget(str, Enum):
    REPORT = "report"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    NOTEBOOK = "notebook"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


@dataclass
class Review:
    """A peer review of a research artifact."""
    review_id: str
    target_type: ReviewTarget
    target_id: str
    reviewer_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    score: float = 0.0
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ReviewService:
    """Structured peer review service for research quality assurance.

    Supports:
        - Review assignment and tracking
        - Structured feedback (strengths, weaknesses, suggestions)
        - Scoring system
        - Review status workflow (pending → in_progress → approved/changes_requested/rejected)
    """

    def __init__(self) -> None:
        self._reviews: dict[str, Review] = {}
        self._total_created = 0

    def create_review(
        self,
        target_type: ReviewTarget,
        target_id: str,
        reviewer_id: str,
    ) -> Review:
        """Create a new review request."""
        import uuid
        review = Review(
            review_id=str(uuid.uuid4()),
            target_type=target_type,
            target_id=target_id,
            reviewer_id=reviewer_id,
        )
        self._reviews[review.review_id] = review
        self._total_created += 1
        logger.info("Created review: %s for %s", review.review_id, target_id)
        return review

    def submit_review(
        self,
        review_id: str,
        score: float,
        summary: str,
        strengths: Optional[list[str]] = None,
        weaknesses: Optional[list[str]] = None,
        suggestions: Optional[list[str]] = None,
    ) -> bool:
        """Submit a completed review."""
        review = self._reviews.get(review_id)
        if review is None:
            return False

        review.score = max(0.0, min(10.0, score))
        review.summary = summary
        review.strengths = strengths or []
        review.weaknesses = weaknesses or []
        review.suggestions = suggestions or []
        review.status = ReviewStatus.APPROVED if score >= 7.0 else ReviewStatus.CHANGES_REQUESTED
        review.completed_at = datetime.now(timezone.utc)
        return True

    def request_changes(self, review_id: str, feedback: str) -> bool:
        """Request changes on a review."""
        review = self._reviews.get(review_id)
        if review is None:
            return False
        review.status = ReviewStatus.CHANGES_REQUESTED
        review.suggestions.append(feedback)
        return True

    def reject(self, review_id: str, reason: str) -> bool:
        """Reject a review."""
        review = self._reviews.get(review_id)
        if review is None:
            return False
        review.status = ReviewStatus.REJECTED
        review.summary = reason
        review.completed_at = datetime.now(timezone.utc)
        return True

    def get_review(self, review_id: str) -> Optional[Review]:
        return self._reviews.get(review_id)

    def list_by_target(self, target_id: str) -> list[Review]:
        """List all reviews for a target."""
        return [r for r in self._reviews.values() if r.target_id == target_id]

    def list_by_reviewer(self, reviewer_id: str) -> list[Review]:
        """List all reviews by a reviewer."""
        return [r for r in self._reviews.values() if r.reviewer_id == reviewer_id]

    def get_average_score(self, target_id: str) -> Optional[float]:
        """Get the average review score for a target."""
        reviews = self.list_by_target(target_id)
        completed = [r for r in reviews if r.status in (ReviewStatus.APPROVED, ReviewStatus.CHANGES_REQUESTED)]
        if not completed:
            return None
        return sum(r.score for r in completed) / len(completed)

    @property
    def total_created(self) -> int:
        return self._total_created
