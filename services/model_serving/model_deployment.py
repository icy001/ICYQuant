"""
ICYQuant Model Deployment — Deployment lifecycle representation.

Tracks a single model deployment throughout its lifecycle:
REGISTERED → VALIDATED → CANDIDATE → STAGING → CANARY → PRODUCTION → ARCHIVED

Includes deployment history, rollout state, and audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeploymentState(str, Enum):
    """Deployment lifecycle states."""
    REGISTERED = "registered"       # Model exists in registry
    VALIDATED = "validated"         # Passed validation checks
    CANDIDATE = "candidate"         # Candidate for promotion
    STAGING = "staging"             # Pre-production staging
    CANARY = "canary"               # Canary deployment active
    PRODUCTION = "production"       # Full production
    DEPRECATED = "deprecated"       # Marked for removal
    ARCHIVED = "archived"           # Retired from serving
    FAILED = "failed"              # Deployment failed
    ROLLBACK = "rollback"          # Rollback in progress


class DeploymentEvent(str, Enum):
    """Events that transition deployment state."""
    REGISTER = "register"
    VALIDATE = "validate"
    PROMOTE_CANDIDATE = "promote_to_candidate"
    PROMOTE_STAGING = "promote_to_staging"
    START_CANARY = "start_canary"
    PROMOTE_PRODUCTION = "promote_to_production"
    DEPRECATE = "deprecate"
    ARCHIVE = "archive"
    FAIL = "fail"
    ROLLBACK = "rollback"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

DEPLOYMENT_TRANSITIONS: Dict[DeploymentState, Dict[DeploymentEvent, DeploymentState]] = {
    DeploymentState.REGISTERED: {
        DeploymentEvent.VALIDATE: DeploymentState.VALIDATED,
        DeploymentEvent.FAIL: DeploymentState.FAILED,
    },
    DeploymentState.VALIDATED: {
        DeploymentEvent.PROMOTE_CANDIDATE: DeploymentState.CANDIDATE,
        DeploymentEvent.FAIL: DeploymentState.FAILED,
    },
    DeploymentState.CANDIDATE: {
        DeploymentEvent.PROMOTE_STAGING: DeploymentState.STAGING,
        DeploymentEvent.FAIL: DeploymentState.FAILED,
    },
    DeploymentState.STAGING: {
        DeploymentEvent.START_CANARY: DeploymentState.CANARY,
        DeploymentEvent.PROMOTE_PRODUCTION: DeploymentState.PRODUCTION,
        DeploymentEvent.ROLLBACK: DeploymentState.ROLLBACK,
        DeploymentEvent.FAIL: DeploymentState.FAILED,
    },
    DeploymentState.CANARY: {
        DeploymentEvent.PROMOTE_PRODUCTION: DeploymentState.PRODUCTION,
        DeploymentEvent.ROLLBACK: DeploymentState.ROLLBACK,
        DeploymentEvent.FAIL: DeploymentState.FAILED,
    },
    DeploymentState.PRODUCTION: {
        DeploymentEvent.DEPRECATE: DeploymentState.DEPRECATED,
        DeploymentEvent.ROLLBACK: DeploymentState.ROLLBACK,
    },
    DeploymentState.DEPRECATED: {
        DeploymentEvent.ARCHIVE: DeploymentState.ARCHIVED,
    },
    DeploymentState.ROLLBACK: {
        DeploymentEvent.REGISTER: DeploymentState.REGISTERED,
    },
    DeploymentState.FAILED: {
        DeploymentEvent.ROLLBACK: DeploymentState.ROLLBACK,
        DeploymentEvent.REGISTER: DeploymentState.REGISTERED,
    },
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DeploymentEventRecord:
    """Record of a deployment event."""
    event: DeploymentEvent
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event.value,
            "timestamp": self.timestamp,
            "detail": self.detail,
            "metadata": self.metadata,
        }


@dataclass
class DeploymentConfig:
    """Configuration for a specific deployment."""
    traffic_percent: float = 100.0
    canary_traffic_percent: float = 5.0
    auto_rollback: bool = True
    rollback_threshold_errors: int = 50
    rollback_threshold_latency_ms: float = 5000.0
    health_check_interval_seconds: int = 30
    min_canary_duration_seconds: int = 3600  # 1 hour
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelDeployment:
    """Represents a single model deployment.

    Tracks:
      - Full lifecycle from registration to archival
      - Deployment event history (audit trail)
      - Traffic allocation
      - Rollback target
      - Health status
    """
    deployment_id: str
    model_id: str
    version: str
    state: DeploymentState = DeploymentState.REGISTERED
    previous_version: Optional[str] = None
    previous_deployment_id: Optional[str] = None
    config: DeploymentConfig = field(default_factory=DeploymentConfig)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: List[DeploymentEventRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def can_transition(self, event: DeploymentEvent) -> bool:
        """Check if a state transition is valid."""
        transitions = DEPLOYMENT_TRANSITIONS.get(self.state, {})
        return event in transitions

    def transition(self, event: DeploymentEvent, detail: str = "") -> bool:
        """Attempt a state transition.

        Returns:
            True if transition succeeded.
        """
        transitions = DEPLOYMENT_TRANSITIONS.get(self.state, {})
        if event not in transitions:
            raise ValueError(
                f"Invalid transition: {self.state.value} → {event.value}"
            )

        previous_state = self.state
        self.state = transitions[event]
        self.updated_at = datetime.now(timezone.utc).isoformat()

        self.events.append(DeploymentEventRecord(
            event=event,
            detail=detail,
            metadata={"previous_state": previous_state.value}
        ))

        return True

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def validate(self) -> bool:
        """Mark deployment as validated."""
        return self.transition(DeploymentEvent.VALIDATE, "Deployment validated")

    def promote_to_candidate(self) -> bool:
        """Promote to candidate stage."""
        return self.transition(DeploymentEvent.PROMOTE_CANDIDATE, "Promoted to candidate")

    def promote_to_staging(self) -> bool:
        """Promote to staging."""
        return self.transition(DeploymentEvent.PROMOTE_STAGING, "Promoted to staging")

    def start_canary(self, traffic_percent: Optional[float] = None) -> bool:
        """Start canary deployment."""
        if traffic_percent is not None:
            self.config.canary_traffic_percent = traffic_percent
        return self.transition(DeploymentEvent.START_CANARY, "Canary started")

    def promote_to_production(self) -> bool:
        """Promote to full production."""
        self.config.traffic_percent = 100.0
        return self.transition(DeploymentEvent.PROMOTE_PRODUCTION, "Promoted to production")

    def rollback(self, detail: str = "Manual rollback") -> bool:
        """Rollback deployment."""
        return self.transition(DeploymentEvent.ROLLBACK, detail)

    def archive(self) -> bool:
        """Archive deployment."""
        return self.transition(DeploymentEvent.ARCHIVE, "Archived")

    def mark_failed(self, reason: str = "") -> bool:
        """Mark deployment as failed."""
        return self.transition(DeploymentEvent.FAIL, reason or "Deployment failed")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Whether deployment is actively serving traffic."""
        return self.state in (
            DeploymentState.PRODUCTION,
            DeploymentState.CANARY,
            DeploymentState.STAGING,
        )

    @property
    def is_stable(self) -> bool:
        """Whether deployment is in a stable state."""
        return self.state in (
            DeploymentState.PRODUCTION,
            DeploymentState.ARCHIVED,
        )

    def get_latest_event(self) -> Optional[DeploymentEventRecord]:
        """Get most recent deployment event."""
        return self.events[-1] if self.events else None

    def get_state_duration_seconds(self) -> float:
        """How long the deployment has been in its current state."""
        latest = self.get_latest_event()
        if latest is None:
            return 0.0
        latest_ts = datetime.fromisoformat(latest.timestamp)
        return (datetime.now(timezone.utc) - latest_ts).total_seconds()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "model_id": self.model_id,
            "version": self.version,
            "state": self.state.value,
            "previous_version": self.previous_version,
            "previous_deployment_id": self.previous_deployment_id,
            "traffic_percent": self.config.traffic_percent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events_count": len(self.events),
            "events": [e.to_dict() for e in self.events[-10:]],  # Last 10 events
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelDeployment":
        config = DeploymentConfig(
            traffic_percent=data.get("traffic_percent", 100.0),
        )
        deployment = cls(
            deployment_id=data["deployment_id"],
            model_id=data["model_id"],
            version=data["version"],
            state=DeploymentState(data.get("state", "registered")),
            previous_version=data.get("previous_version"),
            previous_deployment_id=data.get("previous_deployment_id"),
            config=config,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", {}),
        )
        if "events" in data:
            deployment.events = [
                DeploymentEventRecord(
                    event=DeploymentEvent(e["event"]),
                    timestamp=e.get("timestamp", ""),
                    detail=e.get("detail", ""),
                    metadata=e.get("metadata", {}),
                )
                for e in data["events"]
            ]
        return deployment

    def __repr__(self) -> str:
        return (
            f"ModelDeployment({self.model_id}@{self.version}, "
            f"state={self.state.value})"
        )
