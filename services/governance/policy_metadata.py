"""
Policy Metadata — structured metadata for policy version tracking.

Tracks: ownership, regulatory classification, review history, mandatory flags,
categorization, and audit trail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PolicyReviewRecord:
    """Record of a single review action on a policy."""

    reviewer: str
    action: str  # approved, rejected, returned, commented
    comment: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "action": self.action,
            "comment": self.comment,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyReviewRecord":
        return cls(
            reviewer=data.get("reviewer", ""),
            action=data.get("action", ""),
            comment=data.get("comment", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PolicyMetadata:
    """
    Structured metadata attached to every policy version.

    Provides full institutional lineage: who owns it, what regulation
    backs it, whether it's mandatory, and a complete review history.
    """

    # Ownership
    owner: str = "SYSTEM"
    owner_team: str = ""
    maintainer: str = ""

    # Classification
    category: str = ""  # e.g., RISK, COMPLIANCE, CAPITAL, OPERATIONAL
    sub_category: str = ""
    policy_type: str = ""  # e.g., LIMIT, REQUIREMENT, GUIDELINE, RESTRICTION

    # Regulatory
    regulatory: bool = False
    regulation_ref: str = ""  # e.g., "SEC Rule 15c3-1", "Basel III"
    compliance_framework: str = ""  # e.g., "Basel III", "MiFID II"

    # Mandatory
    mandatory: bool = True  # If False, advisory only
    override_allowed: bool = True  # Whether this policy allows manual override
    override_requires_approval: bool = True

    # Review
    review_interval_days: int = 90  # How often this policy should be reviewed
    last_reviewed_at: float = field(default_factory=time.time)
    last_reviewed_by: str = ""
    review_history: List[PolicyReviewRecord] = field(default_factory=list)

    # Documentation
    rationale: str = ""
    references: List[str] = field(default_factory=list)
    related_policies: List[str] = field(default_factory=list)

    # Change tracking
    change_summary: str = ""
    breaking_change: bool = False

    # Custom
    tags: List[str] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)

    def add_review(self, reviewer: str, action: str, comment: str = "") -> None:
        """Record a review action."""
        record = PolicyReviewRecord(
            reviewer=reviewer,
            action=action,
            comment=comment,
        )
        self.review_history.append(record)
        self.last_reviewed_at = record.timestamp
        self.last_reviewed_by = reviewer

    def is_overdue_for_review(self, now: Optional[float] = None) -> bool:
        """Check if this policy is overdue for periodic review."""
        if self.review_interval_days <= 0:
            return False
        now = now or time.time()
        elapsed_days = (now - self.last_reviewed_at) / 86400.0
        return elapsed_days > self.review_interval_days

    def days_since_last_review(self, now: Optional[float] = None) -> float:
        """Days elapsed since last review."""
        now = now or time.time()
        return (now - self.last_reviewed_at) / 86400.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner": self.owner,
            "owner_team": self.owner_team,
            "maintainer": self.maintainer,
            "category": self.category,
            "sub_category": self.sub_category,
            "policy_type": self.policy_type,
            "regulatory": self.regulatory,
            "regulation_ref": self.regulation_ref,
            "compliance_framework": self.compliance_framework,
            "mandatory": self.mandatory,
            "override_allowed": self.override_allowed,
            "override_requires_approval": self.override_requires_approval,
            "review_interval_days": self.review_interval_days,
            "last_reviewed_at": self.last_reviewed_at,
            "last_reviewed_by": self.last_reviewed_by,
            "review_history": [r.to_dict() for r in self.review_history],
            "rationale": self.rationale,
            "references": self.references,
            "related_policies": self.related_policies,
            "change_summary": self.change_summary,
            "breaking_change": self.breaking_change,
            "tags": self.tags,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyMetadata":
        meta = cls(
            owner=data.get("owner", "SYSTEM"),
            owner_team=data.get("owner_team", ""),
            maintainer=data.get("maintainer", ""),
            category=data.get("category", ""),
            sub_category=data.get("sub_category", ""),
            policy_type=data.get("policy_type", ""),
            regulatory=data.get("regulatory", False),
            regulation_ref=data.get("regulation_ref", ""),
            compliance_framework=data.get("compliance_framework", ""),
            mandatory=data.get("mandatory", True),
            override_allowed=data.get("override_allowed", True),
            override_requires_approval=data.get("override_requires_approval", True),
            review_interval_days=data.get("review_interval_days", 90),
            last_reviewed_at=data.get("last_reviewed_at", time.time()),
            last_reviewed_by=data.get("last_reviewed_by", ""),
            rationale=data.get("rationale", ""),
            references=data.get("references", []),
            related_policies=data.get("related_policies", []),
            change_summary=data.get("change_summary", ""),
            breaking_change=data.get("breaking_change", False),
            tags=data.get("tags", []),
            custom=data.get("custom", {}),
        )
        for r in data.get("review_history", []):
            meta.review_history.append(PolicyReviewRecord.from_dict(r))
        return meta
