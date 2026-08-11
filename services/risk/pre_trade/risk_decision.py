"""
Pre-Trade Risk Decision — Standardized risk evaluation output.

All risk evaluations produce a ``RiskDecision`` that OMS uses to
approve, reject, or escalate orders. Every decision is immutable
and fully auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class Decision(str, Enum):
    """Risk decision outcome."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    ESCALATED = "ESCALATED"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    CONDITIONAL_APPROVED = "CONDITIONAL_APPROVED"


class RiskLevel(str, Enum):
    """Overall risk assessment level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskDecision:
    """
    Immutable risk decision produced by the Pre-Trade Risk Engine.

    Contains the final decision, supporting evidence from individual
    checkers, and a structured reason trace for audit trails.

    Usage::

        decision = RiskDecision.approved("REQ-001", risk_score=15)
        decision = RiskDecision.rejected("REQ-001", risk_score=85, reasons=[...])
    """

    # ---- Identifiers ----
    decision_id: str = field(default_factory=lambda: uuid4().hex)
    request_id: str = ""
    engine_id: str = ""

    # ---- Decision ----
    decision: Decision = Decision.APPROVED
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0  # 0 (safe) – 100 (critical)

    # ---- Evidence ----
    triggered_rules: list[str] = field(default_factory=list)
    passed_rules: list[str] = field(default_factory=list)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    checker_results: dict[str, Any] = field(default_factory=dict)

    # ---- Workflow ----
    requires_manual_approval: bool = False
    approver: Optional[str] = None
    approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # ---- Metadata ----
    evaluation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_approved(self) -> bool:
        return self.decision == Decision.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.decision == Decision.REJECTED

    @property
    def needs_escalation(self) -> bool:
        return self.decision in (Decision.ESCALATED, Decision.PENDING_REVIEW, Decision.MANUAL_APPROVAL)

    # ---- Factory Methods ----

    @classmethod
    def approved(
        cls,
        request_id: str,
        risk_score: float = 0.0,
        passed_rules: Optional[list[str]] = None,
        checker_results: Optional[dict[str, Any]] = None,
        evaluation_time_ms: float = 0.0,
        **kwargs: Any,
    ) -> RiskDecision:
        return cls(
            request_id=request_id,
            decision=Decision.APPROVED,
            risk_level=RiskLevel.LOW if risk_score < 30 else RiskLevel.MEDIUM,
            risk_score=risk_score,
            passed_rules=passed_rules or [],
            checker_results=checker_results or {},
            evaluation_time_ms=evaluation_time_ms,
            **kwargs,
        )

    @classmethod
    def rejected(
        cls,
        request_id: str,
        risk_score: float = 80.0,
        triggered_rules: Optional[list[str]] = None,
        reasons: Optional[list[dict[str, Any]]] = None,
        checker_results: Optional[dict[str, Any]] = None,
        evaluation_time_ms: float = 0.0,
        **kwargs: Any,
    ) -> RiskDecision:
        return cls(
            request_id=request_id,
            decision=Decision.REJECTED,
            risk_level=RiskLevel.CRITICAL if risk_score >= 80 else RiskLevel.HIGH,
            risk_score=risk_score,
            triggered_rules=triggered_rules or [],
            reasons=reasons or [],
            checker_results=checker_results or {},
            evaluation_time_ms=evaluation_time_ms,
            **kwargs,
        )

    @classmethod
    def escalated(
        cls,
        request_id: str,
        risk_score: float = 60.0,
        triggered_rules: Optional[list[str]] = None,
        reasons: Optional[list[dict[str, Any]]] = None,
        checker_results: Optional[dict[str, Any]] = None,
        evaluation_time_ms: float = 0.0,
        **kwargs: Any,
    ) -> RiskDecision:
        return cls(
            request_id=request_id,
            decision=Decision.ESCALATED,
            risk_level=RiskLevel.HIGH,
            risk_score=risk_score,
            triggered_rules=triggered_rules or [],
            reasons=reasons or [],
            checker_results=checker_results or {},
            evaluation_time_ms=evaluation_time_ms,
            **kwargs,
        )

    @classmethod
    def pending_review(
        cls,
        request_id: str,
        risk_score: float = 50.0,
        triggered_rules: Optional[list[str]] = None,
        reasons: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> RiskDecision:
        return cls(
            request_id=request_id,
            decision=Decision.PENDING_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            risk_score=risk_score,
            triggered_rules=triggered_rules or [],
            reasons=reasons or [],
            requires_manual_approval=True,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "engine_id": self.engine_id,
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "triggered_rules": self.triggered_rules,
            "passed_rules": self.passed_rules,
            "reasons": self.reasons,
            "requires_manual_approval": self.requires_manual_approval,
            "evaluation_time_ms": self.evaluation_time_ms,
            "created_at": self.created_at.isoformat(),
        }
