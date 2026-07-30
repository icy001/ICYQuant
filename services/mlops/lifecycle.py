"""
AI Lifecycle Manager.

Tracks the full lifecycle of every AI model in the system:
Training → Validation → Registry → Staging → Canary → Production → Monitoring → Retirement

Provides complete audit trail: who, when, why, version.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LifecycleStage(str, enum.Enum):
    """Stages in the AI model lifecycle."""
    CREATED = "created"
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REGISTERED = "registered"
    STAGING = "staging"
    CANARY = "canary"
    PRODUCTION = "production"
    MONITORING = "monitoring"
    DEGRADED = "degraded"
    RETIRED = "retired"
    ARCHIVED = "archived"


@dataclass
class LifecycleEvent:
    """A single event in a model's lifecycle."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    model_version: str = ""
    from_stage: Optional[LifecycleStage] = None
    to_stage: LifecycleStage = LifecycleStage.CREATED

    # Actor
    triggered_by: str = "system"  # user or system component
    trigger_reason: str = ""

    # Timing
    timestamp: float = field(default_factory=time.time)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "from_stage": self.from_stage.value if self.from_stage else None,
            "to_stage": self.to_stage.value,
            "triggered_by": self.triggered_by,
            "trigger_reason": self.trigger_reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class LifecycleRecord:
    """Complete lifecycle record for a model."""

    model_name: str = ""
    model_version: str = ""

    current_stage: LifecycleStage = LifecycleStage.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Lifecycle timeline
    events: List[LifecycleEvent] = field(default_factory=list)

    # Key timestamps
    trained_at: Optional[float] = None
    validated_at: Optional[float] = None
    registered_at: Optional[float] = None
    deployed_at: Optional[float] = None
    retired_at: Optional[float] = None

    # Statistics
    days_in_production: float = 0.0
    total_retrains: int = 0
    total_rollbacks: int = 0

    # Metrics snapshots
    training_metrics: Dict[str, float] = field(default_factory=dict)
    validation_metrics: Dict[str, float] = field(default_factory=dict)
    production_metrics: Dict[str, float] = field(default_factory=dict)

    # Tags
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "current_stage": self.current_stage.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": [e.to_dict() for e in self.events],
            "trained_at": self.trained_at,
            "validated_at": self.validated_at,
            "registered_at": self.registered_at,
            "deployed_at": self.deployed_at,
            "retired_at": self.retired_at,
            "days_in_production": self.days_in_production,
            "total_retrains": self.total_retrains,
            "total_rollbacks": self.total_rollbacks,
            "tags": self.tags,
        }


@dataclass
class LifecycleConfig:
    """Configuration for lifecycle management."""

    # Auto-transitions
    auto_advance_on_train: bool = True
    auto_advance_on_validate: bool = True
    auto_advance_on_register: bool = True

    # Monitoring
    track_metric_history: bool = True
    max_metric_history: int = 100

    # Retention
    retain_retired_models: bool = True
    archive_after_days: int = 365  # Auto-archive after 1 year inactive

    # Audit
    audit_all_transitions: bool = True
    require_reason: bool = True


# ---------------------------------------------------------------------------
# Lifecycle Manager
# ---------------------------------------------------------------------------

class LifecycleManager:
    """Manages the full lifecycle of AI models.

    Tracks every model through its entire lifecycle, recording all
    transitions, metrics, and events for audit and governance.

    Valid transitions (forward):
        CREATED → TRAINING → TRAINED → VALIDATING → VALIDATED
        → REGISTERED → STAGING → CANARY → PRODUCTION → MONITORING

    Valid transitions (backward):
        Any → DEGRADED → RETIRED → ARCHIVED
        PRODUCTION → RETIRED

    Usage::

        lm = LifecycleManager(config)
        lm.create("Alpha_v39", "1.0.0")
        lm.transition("Alpha_v39", LifecycleStage.TRAINING, triggered_by="scheduler")
        lm.transition("Alpha_v39", LifecycleStage.VALIDATED, reason="Passed all gates")
        lm.get_audit_trail("Alpha_v39")
    """

    # Valid forward transitions
    FORWARD_TRANSITIONS: Dict[LifecycleStage, List[LifecycleStage]] = {
        LifecycleStage.CREATED: [LifecycleStage.TRAINING],
        LifecycleStage.TRAINING: [LifecycleStage.TRAINED],
        LifecycleStage.TRAINED: [LifecycleStage.VALIDATING],
        LifecycleStage.VALIDATING: [LifecycleStage.VALIDATED],
        LifecycleStage.VALIDATED: [LifecycleStage.REGISTERED, LifecycleStage.RETIRED],
        LifecycleStage.REGISTERED: [LifecycleStage.STAGING],
        LifecycleStage.STAGING: [LifecycleStage.CANARY, LifecycleStage.RETIRED],
        LifecycleStage.CANARY: [LifecycleStage.PRODUCTION, LifecycleStage.RETIRED],
        LifecycleStage.PRODUCTION: [LifecycleStage.MONITORING, LifecycleStage.DEGRADED, LifecycleStage.RETIRED],
        LifecycleStage.MONITORING: [LifecycleStage.DEGRADED, LifecycleStage.RETIRED],
        LifecycleStage.DEGRADED: [LifecycleStage.PRODUCTION, LifecycleStage.RETIRED],
        LifecycleStage.RETIRED: [LifecycleStage.ARCHIVED],
        LifecycleStage.ARCHIVED: [],
    }

    def __init__(self, config: LifecycleConfig):
        self.config = config
        self._records: Dict[str, LifecycleRecord] = {}
        self._metric_history: Dict[str, List[Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Lifecycle Operations
    # ------------------------------------------------------------------

    def create(
        self,
        model_name: str,
        model_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LifecycleRecord:
        """Create a new lifecycle record for a model.

        Args:
            model_name: Model identifier.
            model_version: Version string.
            metadata: Optional creation metadata.

        Returns:
            The new LifecycleRecord.
        """
        key = self._make_key(model_name, model_version)
        if key in self._records:
            logger.warning(f"Lifecycle record already exists for {key}")
            return self._records[key]

        record = LifecycleRecord(
            model_name=model_name,
            model_version=model_version,
            current_stage=LifecycleStage.CREATED,
            tags=metadata.get("tags", {}) if metadata else {},
        )

        self._add_event(
            record,
            to_stage=LifecycleStage.CREATED,
            triggered_by=metadata.get("author", "system") if metadata else "system",
            reason="Model created",
            metadata=metadata or {},
        )

        self._records[key] = record
        logger.info(f"Lifecycle record created: {model_name} v{model_version}")
        return record

    def transition(
        self,
        model_name: str,
        to_stage: LifecycleStage,
        model_version: Optional[str] = None,
        triggered_by: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition a model to a new lifecycle stage.

        Args:
            model_name: Model identifier.
            to_stage: Target lifecycle stage.
            model_version: Version (defaults to latest).
            triggered_by: Who/what triggered the transition.
            reason: Human-readable reason.
            metadata: Optional additional data.

        Returns:
            True if transition was valid and executed.

        Raises:
            ValueError: If the transition is not allowed.
        """
        record = self._get_record(model_name, model_version)
        if not record:
            raise ValueError(f"No lifecycle record for {model_name}")

        if not self._is_valid_transition(record.current_stage, to_stage):
            raise ValueError(
                f"Invalid transition: {record.current_stage.value} → {to_stage.value} "
                f"for {model_name}"
            )

        from_stage = record.current_stage
        record.current_stage = to_stage
        record.updated_at = time.time()

        # Update key timestamps
        self._update_timestamps(record, to_stage)

        # Track stage durations
        if to_stage == LifecycleStage.PRODUCTION:
            record.deployed_at = time.time()
        elif to_stage == LifecycleStage.RETIRED and record.deployed_at:
            record.days_in_production = (
                time.time() - record.deployed_at
            ) / 86400.0

        # Record event
        self._add_event(
            record,
            from_stage=from_stage,
            to_stage=to_stage,
            triggered_by=triggered_by,
            reason=reason,
            metadata=metadata or {},
        )

        logger.info(
            f"Lifecycle transition: {model_name} "
            f"{from_stage.value} → {to_stage.value} "
            f"(by {triggered_by})"
        )

        return True

    def get_stage(
        self, model_name: str, model_version: Optional[str] = None
    ) -> Optional[LifecycleStage]:
        """Get the current lifecycle stage of a model."""
        record = self._get_record(model_name, model_version)
        return record.current_stage if record else None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def record_metrics(
        self,
        model_name: str,
        metrics: Dict[str, float],
        stage: LifecycleStage,
        model_version: Optional[str] = None,
    ) -> None:
        """Record metrics for a model at a specific stage.

        Args:
            model_name: Model identifier.
            metrics: Metric name → value.
            stage: Lifecycle stage for these metrics.
            model_version: Optional version.
        """
        record = self._get_record(model_name, model_version)
        if not record:
            return

        if stage in (LifecycleStage.TRAINING, LifecycleStage.TRAINED):
            record.training_metrics.update(metrics)
        elif stage in (LifecycleStage.VALIDATING, LifecycleStage.VALIDATED):
            record.validation_metrics.update(metrics)
        elif stage in (LifecycleStage.PRODUCTION, LifecycleStage.MONITORING):
            record.production_metrics.update(metrics)

        # Track history
        if self.config.track_metric_history:
            key = self._make_key(model_name, model_version)
            if key not in self._metric_history:
                self._metric_history[key] = []
            self._metric_history[key].append({
                "timestamp": time.time(),
                "stage": stage.value,
                "metrics": metrics,
            })
            # Prune old history
            if len(self._metric_history[key]) > self.config.max_metric_history:
                self._metric_history[key] = self._metric_history[key][
                    -self.config.max_metric_history:
                ]

    def get_metric_history(
        self, model_name: str, model_version: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get metric history for a model."""
        key = self._make_key(model_name, model_version)
        return self._metric_history.get(key, [])

    # ------------------------------------------------------------------
    # Audit & Queries
    # ------------------------------------------------------------------

    def get_audit_trail(
        self, model_name: str, model_version: Optional[str] = None
    ) -> List[LifecycleEvent]:
        """Get the full audit trail (lifecycle events) for a model.

        Returns events in chronological order.
        """
        record = self._get_record(model_name, model_version)
        if not record:
            return []
        return sorted(record.events, key=lambda e: e.timestamp)

    def get_record(
        self, model_name: str, model_version: Optional[str] = None
    ) -> Optional[LifecycleRecord]:
        """Get the full lifecycle record for a model."""
        return self._get_record(model_name, model_version)

    def list_models_by_stage(self, stage: LifecycleStage) -> List[LifecycleRecord]:
        """List all models currently at a specific stage."""
        return [r for r in self._records.values() if r.current_stage == stage]

    def list_all_models(self) -> List[LifecycleRecord]:
        """List all tracked models."""
        return list(self._records.values())

    def get_production_models(self) -> List[LifecycleRecord]:
        """Get all models currently in production."""
        return self.list_models_by_stage(LifecycleStage.PRODUCTION)

    def get_models_needing_attention(self) -> List[LifecycleRecord]:
        """Get models that may need attention (degraded, very old, etc.)."""
        attention = []
        for record in self._records.values():
            if record.current_stage == LifecycleStage.DEGRADED:
                attention.append(record)
            elif (
                record.current_stage == LifecycleStage.PRODUCTION
                and record.deployed_at
                and (time.time() - record.deployed_at) / 86400.0 > 180
            ):
                # In production > 180 days without retrain
                if record.total_retrains == 0:
                    attention.append(record)
        return attention

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate lifecycle statistics."""
        records = list(self._records.values())
        stages = {}
        for r in records:
            s = r.current_stage.value
            stages[s] = stages.get(s, 0) + 1

        total_deployments = sum(
            1 for r in records
            if any(e.to_stage == LifecycleStage.PRODUCTION for e in r.events)
        )
        total_rollbacks = sum(r.total_rollbacks for r in records)
        total_retrains = sum(r.total_retrains for r in records)

        return {
            "total_models": len(records),
            "models_by_stage": stages,
            "total_deployments": total_deployments,
            "total_rollbacks": total_rollbacks,
            "total_retrains": total_retrains,
            "active_production": stages.get(LifecycleStage.PRODUCTION.value, 0),
            "degraded": stages.get(LifecycleStage.DEGRADED.value, 0),
            "retired": stages.get(LifecycleStage.RETIRED.value, 0),
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _get_record(
        self, model_name: str, model_version: Optional[str] = None
    ) -> Optional[LifecycleRecord]:
        """Get a lifecycle record, supporting version lookup."""
        key = self._make_key(model_name, model_version)
        if key in self._records:
            return self._records[key]

        # If no specific version, find latest
        if model_version is None:
            candidates = [
                (k, r) for k, r in self._records.items()
                if k.startswith(f"{model_name}:")
            ]
            if candidates:
                return max(candidates, key=lambda x: x[1].created_at)[1]

        return None

    def _make_key(self, model_name: str, model_version: Optional[str] = None) -> str:
        """Create a unique key for a model record."""
        if model_version:
            return f"{model_name}:{model_version}"
        return model_name

    def _is_valid_transition(
        self, from_stage: LifecycleStage, to_stage: LifecycleStage
    ) -> bool:
        """Check if a transition is valid."""
        allowed = self.FORWARD_TRANSITIONS.get(from_stage, [])
        return to_stage in allowed

    def _update_timestamps(
        self, record: LifecycleRecord, to_stage: LifecycleStage
    ) -> None:
        """Update key timestamps based on stage."""
        now = time.time()
        if to_stage == LifecycleStage.TRAINED:
            record.trained_at = now
        elif to_stage == LifecycleStage.VALIDATED:
            record.validated_at = now
        elif to_stage == LifecycleStage.REGISTERED:
            record.registered_at = now
        elif to_stage == LifecycleStage.PRODUCTION:
            record.deployed_at = now
        elif to_stage == LifecycleStage.RETIRED:
            record.retired_at = now

    def _add_event(
        self,
        record: LifecycleRecord,
        to_stage: LifecycleStage,
        triggered_by: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        from_stage: Optional[LifecycleStage] = None,
    ) -> None:
        """Add a lifecycle event to a record."""
        event = LifecycleEvent(
            model_name=record.model_name,
            model_version=record.model_version,
            from_stage=from_stage,
            to_stage=to_stage,
            triggered_by=triggered_by,
            trigger_reason=reason,
            metadata=metadata or {},
        )
        record.events.append(event)

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._records.clear()
        self._metric_history.clear()
