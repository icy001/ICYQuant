"""Control evidence — auditable proof for every control decision.

Every PASS/REJECT/BLOCK decision carries structured evidence
so that "why" is always traceable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ControlEvidence:
    """Base evidence envelope for a control decision.

    Specialized sub-types carry domain-specific metrics.
    """

    # ── Evidence identity ──
    evidence_id: str = ""
    domain: str = ""  # "risk", "governance", "authority", "approval"

    # ── Content ──
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    # ── Timing ──
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "domain": self.domain,
            "metrics": self.metrics,
            "tags": self.tags,
            "evaluated_at": self.evaluated_at,
        }

    def __repr__(self) -> str:
        return f"ControlEvidence(domain={self.domain!r}, metrics={list(self.metrics.keys())})"


# ── Domain-specific evidence ──


@dataclass
class RiskEvidence(ControlEvidence):
    """Risk-domain control evidence."""

    def __post_init__(self):
        self.domain = "risk"

    @classmethod
    def from_assessment(
        cls,
        metric: str,
        value: Any,
        limit: Any,
        threshold_percent: float = 100.0,
        **kwargs: Any,
    ) -> "RiskEvidence":
        """Create risk evidence from a quantitative assessment."""
        return cls(
            metrics={
                "metric": metric,
                "value": value,
                "limit": limit,
                "threshold_percent": threshold_percent,
                **kwargs.get("extra_metrics", {}),
            },
            tags={
                "evidence_type": "quantitative",
                **kwargs.get("extra_tags", {}),
            },
            evidence_id=kwargs.get("evidence_id", ""),
            evaluated_at=kwargs.get("evaluated_at", time.time()),
        )


@dataclass
class GovernanceEvidence(ControlEvidence):
    """Governance-domain control evidence."""

    def __post_init__(self):
        self.domain = "governance"

    @classmethod
    def from_policy_eval(
        cls,
        governance_state: str = "NORMAL",
        policy_name: str = "",
        policy_version: str = "",
        policy_hash: str = "",
        **kwargs: Any,
    ) -> "GovernanceEvidence":
        """Create governance evidence from a policy evaluation."""
        return cls(
            metrics={
                "governance_state": governance_state,
                "policy_name": policy_name,
                "policy_version": policy_version,
                "policy_hash": policy_hash,
                **kwargs.get("extra_metrics", {}),
            },
            tags={
                "evidence_type": "policy",
                **kwargs.get("extra_tags", {}),
            },
            evidence_id=kwargs.get("evidence_id", ""),
            evaluated_at=kwargs.get("evaluated_at", time.time()),
        )


@dataclass
class AuthorityEvidence(ControlEvidence):
    """Authority-domain control evidence."""

    def __post_init__(self):
        self.domain = "authority"

    @classmethod
    def from_authorization(
        cls,
        authority_limit: float = 0.0,
        requested_notional: float = 0.0,
        remaining_limit: float = 0.0,
        authority_status: str = "VALID",
        **kwargs: Any,
    ) -> "AuthorityEvidence":
        """Create authority evidence from an authorization check."""
        return cls(
            metrics={
                "authority_limit": authority_limit,
                "requested_notional": requested_notional,
                "remaining_limit": remaining_limit,
                "authority_status": authority_status,
                **kwargs.get("extra_metrics", {}),
            },
            tags={
                "evidence_type": "authorization",
                **kwargs.get("extra_tags", {}),
            },
            evidence_id=kwargs.get("evidence_id", ""),
            evaluated_at=kwargs.get("evaluated_at", time.time()),
        )


@dataclass
class ApprovalEvidence(ControlEvidence):
    """Approval-domain control evidence."""

    def __post_init__(self):
        self.domain = "approval"

    @classmethod
    def from_approval(
        cls,
        approval_id: str = "",
        approved_notional: float = 0.0,
        requested_notional: float = 0.0,
        expires_at: float = 0.0,
        scope: str = "",
        **kwargs: Any,
    ) -> "ApprovalEvidence":
        """Create approval evidence from an approval record."""
        return cls(
            metrics={
                "approval_id": approval_id,
                "approved_notional": approved_notional,
                "requested_notional": requested_notional,
                "expires_at": expires_at,
                "scope": scope,
                **kwargs.get("extra_metrics", {}),
            },
            tags={
                "evidence_type": "approval",
                **kwargs.get("extra_tags", {}),
            },
            evidence_id=kwargs.get("evidence_id", ""),
            evaluated_at=kwargs.get("evaluated_at", time.time()),
        )
