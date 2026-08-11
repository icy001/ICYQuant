"""
Decision Audit — full institutional decision record.

Every governance decision is auditably recorded, including:
  - Input context
  - Policy evaluation result
  - Authority evaluation result
  - Constraint evaluation results
  - Approval result
  - Final verdict and reason

This is NOT an application log — it answers "WHY did the system allow this?"

Part 1.4 adds integration with AuditEngine and DecisionRecord
for immutable, hash-chained audit with full lineage.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuditRecord:
    """A complete record of a single governance decision."""

    decision_id: str
    request_id: str
    actor: str = ""
    decision_type: str = ""

    # Verdict
    verdict: str = ""
    reason: str = ""

    # Override
    override: bool = False
    override_reason: str = ""

    # Stage results
    policy_result: Optional[Dict[str, Any]] = None
    authority_result: Optional[Dict[str, Any]] = None
    constraint_results: Optional[List[Dict[str, Any]]] = None
    approval_result: Optional[Dict[str, Any]] = None

    # Context snapshot
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "actor": self.actor,
            "decision_type": self.decision_type,
            "verdict": self.verdict,
            "reason": self.reason,
            "override": self.override,
            "override_reason": self.override_reason,
            "policy_result": self.policy_result,
            "authority_result": self.authority_result,
            "constraint_results": self.constraint_results,
            "approval_result": self.approval_result,
            "context_snapshot": self.context_snapshot,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DecisionAudit:
    """
    Stores and queries governance audit records.
    Provides the institutional decision record for compliance and debugging.

    Part 1.4: now also integrates with AuditEngine and DecisionRecord
    for immutable, hash-chained recording.
    """

    def __init__(self, max_records: int = 100000, audit_engine: Any = None):
        self._records: List[AuditRecord] = []
        self._max_records = max_records
        self._audit_engine = audit_engine  # Optional AuditEngine integration
        self._decision_records: Dict[str, Any] = {}  # DecisionRecord by decision_id

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, record: AuditRecord) -> None:
        """Store an audit record."""
        self._records.append(record)
        # Prune if exceeding max
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, decision_id: str) -> Optional[AuditRecord]:
        """Get a specific audit record by decision_id."""
        for r in reversed(self._records):
            if r.decision_id == decision_id:
                return r
        return None

    def query(
        self,
        actor: Optional[str] = None,
        decision_type: Optional[str] = None,
        verdict: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query audit records with filters."""
        results = []
        for r in reversed(self._records):
            if actor and r.actor != actor:
                continue
            if decision_type and r.decision_type != decision_type:
                continue
            if verdict and r.verdict != verdict:
                continue
            if since and r.timestamp < since:
                continue
            results.append(r.to_dict())
            if len(results) >= limit + offset:
                break
        return results[offset:offset + limit]

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent audit records."""
        records = self._records[-n:]
        return [r.to_dict() for r in reversed(records)]

    def get_by_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get audit record by original request_id."""
        for r in reversed(self._records):
            if r.request_id == request_id:
                return r.to_dict()
        return None

    def get_blocked_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get decisions that were blocked or rejected."""
        results = []
        for r in reversed(self._records):
            if r.verdict in ("BLOCKED", "REJECTED"):
                results.append(r.to_dict())
                if len(results) >= limit:
                    break
        return results

    def get_overrides(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get decisions that were overridden."""
        results = []
        for r in reversed(self._records):
            if r.override:
                results.append(r.to_dict())
                if len(results) >= limit:
                    break
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._records)

    def stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics."""
        total = len(self._records)
        if total == 0:
            return {"total": 0}

        verdicts: Dict[str, int] = {}
        overrides = 0
        actors: Dict[str, int] = {}

        for r in self._records:
            verdicts[r.verdict] = verdicts.get(r.verdict, 0) + 1
            if r.override:
                overrides += 1
            actors[r.actor] = actors.get(r.actor, 0) + 1

        return {
            "total": total,
            "verdicts": verdicts,
            "overrides": overrides,
            "top_actors": sorted(actors.items(), key=lambda x: x[1], reverse=True)[:5],
            "first_timestamp": self._records[0].timestamp if self._records else None,
            "last_timestamp": self._records[-1].timestamp if self._records else None,
        }

    def clear(self) -> None:
        self._records.clear()
        self._decision_records.clear()

    # ── Part 1.4: DecisionRecord Integration ──

    def set_audit_engine(self, engine: Any) -> None:
        """Set the AuditEngine for immutable event recording."""
        self._audit_engine = engine

    def record_decision_record(self, record: Any) -> None:
        """Store a full DecisionRecord (Part 1.4)."""
        self._decision_records[record.decision_id] = record

    def get_decision_record(self, decision_id: str) -> Optional[Any]:
        """Get a full DecisionRecord by decision_id."""
        return self._decision_records.get(decision_id)

    def record_with_audit(
        self,
        record: AuditRecord,
        correlation_id: str = "",
    ) -> None:
        """Record an AuditRecord with immutable AuditEngine integration."""
        self.record(record)

        if self._audit_engine:
            from .audit_event_type import AuditEventType
            from .audit_actor import AuditActor
            from .audit_action import AuditAction
            from .audit_outcome import AuditOutcome

            verdict_map = {
                "ALLOW": AuditEventType.DECISION_APPROVED,
                "BLOCKED": AuditEventType.DECISION_REJECTED,
                "REJECTED": AuditEventType.DECISION_REJECTED,
                "REVIEW": AuditEventType.DECISION_CREATED,
            }
            event_type = verdict_map.get(record.verdict, AuditEventType.DECISION_CREATED)

            self._audit_engine.record_event(
                event_type=event_type,
                entity_type="DECISION",
                entity_id=record.decision_id,
                actor=AuditActor.human(record.actor) if record.actor else AuditActor.system("decision-audit"),
                action=AuditAction.APPROVE if record.verdict == "ALLOW" else AuditAction.DENY,
                outcome=AuditOutcome.SUCCESS if record.verdict == "ALLOW" else AuditOutcome.FAILURE,
                reason=record.reason,
                correlation_id=correlation_id or f"CORR-{record.decision_id}",
            )
