from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .recovery_scope import RecoveryScope, RecoveryScopeType
from .recovery_status import RecoveryStatus, RecoveryType


class RecoveryJournalEntryState(str, Enum):
    STARTED = "STARTED"
    PRECHECK_PASSED = "PRECHECK_PASSED"
    PRECHECK_FAILED = "PRECHECK_FAILED"
    EVENTS_LOADED = "EVENTS_LOADED"
    POSITION_REPLAYED = "POSITION_REPLAYED"
    LEDGER_REPLAYED = "LEDGER_REPLAYED"
    PROJECTION_REBUILT = "PROJECTION_REBUILT"
    CONSISTENCY_VERIFIED = "CONSISTENCY_VERIFIED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    RETRYING = "RETRYING"


@dataclass
class RecoveryJournalEntry:
    """A single entry in the recovery audit journal."""

    state: RecoveryJournalEntryState
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "detail": self.detail,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryJournalEntry":
        return cls(
            state=RecoveryJournalEntryState(data["state"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            detail=data.get("detail", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RecoveryJournal:
    """Full audit trail for a recovery job."""

    entries: List[RecoveryJournalEntry] = field(default_factory=list)

    def append(self, state: RecoveryJournalEntryState, detail: str = "", **meta: Any) -> None:
        self.entries.append(
            RecoveryJournalEntry(state=state, detail=detail, metadata=dict(meta))
        )

    @property
    def last_state(self) -> Optional[RecoveryJournalEntryState]:
        return self.entries[-1].state if self.entries else None

    def to_dict(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_dict(cls, data: List[Dict[str, Any]]) -> "RecoveryJournal":
        return cls(entries=[RecoveryJournalEntry.from_dict(e) for e in data])


@dataclass
class RecoveryPlan:
    """Generated before recovery execution — describes what needs to happen."""

    source_execution_id: str
    position_action: str  # REPLAY_REQUIRED | NO_ACTION | REBUILD_REQUIRED
    ledger_action: str  # REPLAY_REQUIRED | NO_ACTION | REBUILD_REQUIRED
    projection_action: str = "NO_ACTION"  # NO_ACTION | REBUILD_REQUIRED
    reason: str = ""
    execution_ids: List[str] = field(default_factory=list)
    precheck_results: Dict[str, bool] = field(default_factory=dict)

    @property
    def requires_position_replay(self) -> bool:
        return self.position_action == "REPLAY_REQUIRED"

    @property
    def requires_ledger_replay(self) -> bool:
        return self.ledger_action == "REPLAY_REQUIRED"

    @property
    def requires_projection_rebuild(self) -> bool:
        return self.projection_action == "REBUILD_REQUIRED"

    @property
    def precheck_passed(self) -> bool:
        return all(self.precheck_results.values()) if self.precheck_results else True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_execution_id": self.source_execution_id,
            "position_action": self.position_action,
            "ledger_action": self.ledger_action,
            "projection_action": self.projection_action,
            "reason": self.reason,
            "execution_ids": self.execution_ids,
            "precheck_results": self.precheck_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryPlan":
        return cls(
            source_execution_id=data["source_execution_id"],
            position_action=data["position_action"],
            ledger_action=data["ledger_action"],
            projection_action=data.get("projection_action", "NO_ACTION"),
            reason=data.get("reason", ""),
            execution_ids=data.get("execution_ids", []),
            precheck_results=data.get("precheck_results", {}),
        )


@dataclass
class RecoveryJob:
    """Core entity representing a single recovery operation.

    Recovery never mutates state directly — it replays immutable execution facts
    and lets domain handlers produce the correct state.
    """

    job_id: str
    recovery_type: RecoveryType
    scope: RecoveryScope
    source_check_id: str

    status: RecoveryStatus = RecoveryStatus.CREATED

    attempt: int = 1
    max_attempts: int = 3

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None

    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    # ---- plan & audit ----
    plan: Optional[RecoveryPlan] = None
    journal: RecoveryJournal = field(default_factory=RecoveryJournal)

    # ---- replay tracking ----
    events_replayed: int = 0
    events_loaded: int = 0
    replay_duration_ms: int = 0

    # ---- concurrency ----
    expected_position_version: Optional[int] = None
    expected_ledger_version: Optional[int] = None

    @property
    def recovery_key(self) -> str:
        return self.scope.recovery_key

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    @property
    def can_retry(self) -> bool:
        return self.status.can_retry and self.attempt < self.max_attempts

    @property
    def account_id(self) -> Optional[str]:
        return self.scope.account_id

    @property
    def instrument_id(self) -> Optional[str]:
        return self.scope.instrument_id

    @property
    def execution_id(self) -> Optional[str]:
        return self.scope.execution_id

    @property
    def order_id(self) -> Optional[str]:
        return self.scope.order_id

    # ---- state transitions ----

    def mark_prechecking(self) -> None:
        self._assert_active()
        self.status = RecoveryStatus.PRECHECKING
        self.started_at = datetime.now(timezone.utc)
        self.journal.append(RecoveryJournalEntryState.STARTED, "Precheck phase started")

    def mark_blocked(self, reason: str) -> None:
        self.status = RecoveryStatus.BLOCKED
        self.failure_code = "BLOCKED"
        self.failure_reason = reason
        self.completed_at = datetime.now(timezone.utc)
        self.journal.append(RecoveryJournalEntryState.BLOCKED, reason)

    def mark_replaying(self) -> None:
        self._assert_active()
        self.status = RecoveryStatus.REPLAYING
        self.journal.append(RecoveryJournalEntryState.EVENTS_LOADED, "Replay phase started")

    def mark_verifying(self) -> None:
        self._assert_active()
        self.status = RecoveryStatus.VERIFYING
        self.journal.append(RecoveryJournalEntryState.POSITION_REPLAYED, "Verification phase started")

    def mark_completed(self) -> None:
        self.status = RecoveryStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.journal.append(RecoveryJournalEntryState.COMPLETED, "Recovery completed successfully")

    def mark_failed(self, code: str, reason: str) -> None:
        self.status = RecoveryStatus.FAILED
        self.failure_code = code
        self.failure_reason = reason
        self.completed_at = datetime.now(timezone.utc)
        self.journal.append(RecoveryJournalEntryState.FAILED, f"{code}: {reason}")

    def mark_escalated(self, reason: str) -> None:
        self.status = RecoveryStatus.ESCALATED
        self.failure_code = "ESCALATED"
        self.failure_reason = reason
        self.completed_at = datetime.now(timezone.utc)
        self.journal.append(RecoveryJournalEntryState.ESCALATED, reason)

    def mark_deduplicated(self) -> None:
        self.status = RecoveryStatus.DEDUPLICATED
        self.completed_at = datetime.now(timezone.utc)

    def retry(self) -> None:
        if not self.can_retry:
            self.mark_escalated(
                f"Max retries ({self.max_attempts}) exceeded: {self.failure_reason}"
            )
            return
        self.attempt += 1
        self.status = RecoveryStatus.PRECHECKING
        self.failure_code = None
        self.failure_reason = None
        self.started_at = datetime.now(timezone.utc)
        self.journal.append(
            RecoveryJournalEntryState.RETRYING, f"Retry attempt {self.attempt}/{self.max_attempts}"
        )

    # ---- internal ----

    def _assert_active(self) -> None:
        if self.is_terminal:
            raise ValueError(
                f"Cannot transition from terminal state {self.status.value}"
            )

    # ---- serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "recovery_type": self.recovery_type.value,
            "scope": self.scope.to_dict(),
            "source_check_id": self.source_check_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "plan": self.plan.to_dict() if self.plan else None,
            "journal": self.journal.to_dict(),
            "events_replayed": self.events_replayed,
            "events_loaded": self.events_loaded,
            "replay_duration_ms": self.replay_duration_ms,
            "expected_position_version": self.expected_position_version,
            "expected_ledger_version": self.expected_ledger_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryJob":
        job = cls(
            job_id=data["job_id"],
            recovery_type=RecoveryType(data["recovery_type"]),
            scope=RecoveryScope.from_dict(data["scope"]),
            source_check_id=data["source_check_id"],
            status=RecoveryStatus(data["status"]),
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 3),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            lineage_id=data.get("lineage_id", ""),
            events_replayed=data.get("events_replayed", 0),
            events_loaded=data.get("events_loaded", 0),
            replay_duration_ms=data.get("replay_duration_ms", 0),
            expected_position_version=data.get("expected_position_version"),
            expected_ledger_version=data.get("expected_ledger_version"),
        )
        if data.get("started_at"):
            job.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            job.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("failure_code"):
            job.failure_code = data["failure_code"]
        if data.get("failure_reason"):
            job.failure_reason = data["failure_reason"]
        if data.get("plan"):
            job.plan = RecoveryPlan.from_dict(data["plan"])
        if data.get("journal"):
            job.journal = RecoveryJournal.from_dict(data["journal"])
        return job
