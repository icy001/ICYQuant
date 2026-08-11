"""
Risk event model — Legacy and Foundation layers.

The legacy ``RiskEvent`` provides a simple frozen event. The foundation
layer adds typed events for lifecycle transitions, policy changes,
evaluation results, approval decisions, and recovery actions used by
the production Risk Management Platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Event Type Enums
# ---------------------------------------------------------------------------


class RiskLifecycleEventType(str, Enum):
    """Lifecycle event types."""
    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    PAUSED = "paused"
    RESUMED = "resumed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    ARCHIVED = "archived"


class RiskPolicyEventType(str, Enum):
    """Policy event types."""
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"
    POLICY_ENABLED = "policy_enabled"
    POLICY_DISABLED = "policy_disabled"
    POLICY_THRESHOLD_BREACH = "policy_threshold_breach"
    POLICY_VIOLATION = "policy_violation"


class RiskEvaluationEventType(str, Enum):
    """Evaluation event types."""
    EVALUATION_STARTED = "evaluation_started"
    EVALUATION_COMPLETED = "evaluation_completed"
    EVALUATION_FAILED = "evaluation_failed"
    EVALUATION_APPROVED = "evaluation_approved"
    EVALUATION_REJECTED = "evaluation_rejected"
    EVALUATION_PENDING = "evaluation_pending"
    EVALUATION_ESCALATED = "evaluation_escalated"


class RiskApprovalEventType(str, Enum):
    """Approval event types."""
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_OVERRIDDEN = "approval_overridden"


class RiskRecoveryEventType(str, Enum):
    """Recovery event types."""
    RECOVERY_INITIATED = "recovery_initiated"
    RECOVERY_RETRYING = "recovery_retrying"
    RECOVERY_SUCCEEDED = "recovery_succeeded"
    RECOVERY_FAILED = "recovery_failed"
    RECOVERY_SNAPSHOT_SAVED = "recovery_snapshot_saved"
    RECOVERY_SNAPSHOT_RESTORED = "recovery_snapshot_restored"


# ---------------------------------------------------------------------------
# Legacy Risk Event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskEvent:
    """Legacy risk event (backwards-compatible)."""

    event_id: str
    event_type: str
    level: str
    message: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Foundation Risk Events
# ---------------------------------------------------------------------------


@dataclass
class RiskLifecycleEvent:
    """
    Event emitted during risk component lifecycle transitions.

    Carries the component's old and new lifecycle states for audit
    and monitoring purposes.
    """

    event_id: str
    event_type: RiskLifecycleEventType
    component_id: str
    previous_state: str
    new_state: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskPolicyEvent:
    """
    Event emitted when risk policies are created, updated, or deleted.

    Also triggered on policy threshold breaches and violations.
    """

    event_id: str
    event_type: RiskPolicyEventType
    policy_id: str
    policy_type: str
    severity: str = "WARNING"
    message: str = ""
    affected_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskEvaluationEvent:
    """
    Event emitted during risk evaluation lifecycle.

    Tracks evaluation start, completion, failure, and decision outcomes.
    """

    event_id: str
    event_type: RiskEvaluationEventType
    evaluation_id: str
    account_id: Optional[str] = None
    decision: Optional[str] = None
    policies_evaluated: int = 0
    policies_failed: int = 0
    duration_ms: Optional[float] = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskApprovalEvent:
    """
    Event emitted during risk decision approval workflow.

    Tracks approval requests, grants, denials, expirations, and overrides.
    """

    event_id: str
    event_type: RiskApprovalEventType
    approval_id: str
    evaluation_id: Optional[str] = None
    approver: Optional[str] = None
    reason: str = ""
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskRecoveryEvent:
    """
    Event emitted during risk platform recovery operations.

    Tracks recovery initiation, retries, success, failure, and
    snapshot save/restore actions.
    """

    event_id: str
    event_type: RiskRecoveryEventType
    recovery_id: str
    snapshot_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    duration_ms: Optional[float] = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))