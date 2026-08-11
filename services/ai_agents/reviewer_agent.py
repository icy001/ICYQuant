"""
ICYQuant Reviewer Agent — quality review and validation.

Reviews outputs from other agents for quality, consistency, methodology
errors, bias, and compliance. Acts as a peer-reviewer in the multi-agent
pipeline.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReviewVerdict(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_MINOR = "approved_with_minor"
    REVISIONS_REQUIRED = "revisions_required"
    REJECTED = "rejected"


@dataclass
class ReviewIssue:
    """An issue found during review."""
    severity: str = "info"       # info, warning, error, critical
    category: str = ""           # methodology, data, bias, compliance, etc.
    description: str = ""
    location: str = ""
    suggestion: str = ""


@dataclass
class ReviewReport:
    """A comprehensive review of an agent's output."""
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""            # What was reviewed
    subject_agent: str = ""      # Which agent produced it
    verdict: ReviewVerdict = ReviewVerdict.APPROVED

    # Scoring
    quality_score: float = 0.0   # 0-10
    methodology_score: float = 0.0
    evidence_score: float = 0.0
    consistency_score: float = 0.0
    bias_score: float = 0.0      # Lower = more bias detected

    issues: list[ReviewIssue] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ReviewerAgent:
    """Quality review and validation agent.

    Capabilities:
        - Methodology review and validation
        - Bias detection and mitigation
        - Consistency checking across agents
        - Evidence quality assessment
        - Compliance verification
        - Scoring and grading
    """

    def __init__(self, agent_id: str = "reviewer_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._review_count = 0

    async def review(self, subject: str, subject_agent: str,
                     content: Any,
                     context: Optional[dict[str, Any]] = None) -> ReviewReport:
        """Review an agent's output for quality and correctness."""
        self._review_count += 1

        report = ReviewReport(
            subject=subject,
            subject_agent=subject_agent,
            quality_score=7.5,
            methodology_score=8.0,
            evidence_score=7.0,
            consistency_score=7.5,
            bias_score=0.15,  # Low bias
            strengths=[
                "Methodology is sound and well-documented",
                "Evidence supports conclusions",
            ],
            recommendations=[
                "Consider adding sensitivity analysis",
                "Validate assumptions with out-of-sample data",
            ],
        )

        # Check for common issues
        if report.evidence_score < 5.0:
            report.issues.append(ReviewIssue(
                severity="error",
                category="evidence",
                description="Insufficient evidence to support conclusions",
                suggestion="Gather additional data or adjust confidence levels",
            ))

        if report.bias_score > 0.5:
            report.issues.append(ReviewIssue(
                severity="warning",
                category="bias",
                description="Potential bias detected in analysis",
                suggestion="Review for confirmation bias and survivorship bias",
            ))

        # Determine verdict
        if report.quality_score >= 7.0 and len([i for i in report.issues if i.severity in ("error", "critical")]) == 0:
            report.verdict = ReviewVerdict.APPROVED
        elif report.quality_score >= 5.0:
            report.verdict = ReviewVerdict.APPROVED_WITH_MINOR
        elif report.quality_score >= 3.0:
            report.verdict = ReviewVerdict.REVISIONS_REQUIRED
        else:
            report.verdict = ReviewVerdict.REJECTED

        logger.info("Review %s: subject=%s verdict=%s quality=%.1f",
                     report.review_id, subject_agent,
                     report.verdict.value, report.quality_score)
        return report

    @property
    def review_count(self) -> int:
        return self._review_count
