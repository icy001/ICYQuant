"""
Approval Audit — records approval workflow history.

Integrates with AuditEngine for unified immutable audit recording.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class ApprovalAudit:
    """
    Records and queries approval history.
    Tracks approval requests, their outcomes, and workflow steps.

    Also integrates with AuditEngine for immutable event recording
    when an audit_engine is provided.
    """

    def __init__(self, max_records: int = 50000, audit_engine: Any = None):
        self._records: List[Dict[str, Any]] = []
        self._max_records = max_records
        self._audit_engine = audit_engine  # Optional AuditEngine integration

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(
        self,
        approval_id: str,
        approval_request_id: str,
        decision_request_id: str,
        decision: str,
        level: str,
        reason: str,
        steps_completed: List[str],
        context: Dict[str, Any],
    ) -> None:
        """Record an approval event."""
        entry = {
            "approval_id": approval_id,
            "approval_request_id": approval_request_id,
            "decision_request_id": decision_request_id,
            "decision": decision,
            "level": level,
            "reason": reason,
            "steps_completed": steps_completed,
            "context": context,
            "timestamp": time.time(),
        }
        self._records.append(entry)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_by_decision(self, decision_request_id: str) -> Optional[Dict[str, Any]]:
        """Get approval for a decision request."""
        for r in reversed(self._records):
            if r["decision_request_id"] == decision_request_id:
                return r
        return None

    def get_by_approval_id(self, approval_id: str) -> Optional[Dict[str, Any]]:
        for r in reversed(self._records):
            if r["approval_id"] == approval_id:
                return r
        return None

    def get_rejected(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all rejected approvals."""
        results = []
        for r in reversed(self._records):
            if r["decision"] == "REJECTED":
                results.append(r)
                if len(results) >= limit:
                    break
        return results

    def get_by_level(self, level: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get approvals at a specific level."""
        results = []
        for r in reversed(self._records):
            if r["level"] == level:
                results.append(r)
                if len(results) >= limit:
                    break
        return results

    def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._records[-n:]))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._records)

    def approval_rate(self) -> float:
        total = len(self._records)
        if total == 0:
            return 1.0
        approved = sum(1 for r in self._records if r["decision"] == "APPROVED")
        return approved / total

    def stats(self) -> Dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"total": 0}

        decisions: Dict[str, int] = {}
        levels: Dict[str, int] = {}
        for r in self._records:
            decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1
            levels[r["level"]] = levels.get(r["level"], 0) + 1

        return {
            "total": total,
            "decisions": decisions,
            "levels": levels,
            "approval_rate": self.approval_rate(),
        }

    def clear(self) -> None:
        self._records.clear()

    # ── AuditEngine Integration ──

    def set_audit_engine(self, engine: Any) -> None:
        """Set the AuditEngine for immutable event recording."""
        self._audit_engine = engine

    def record_with_audit(
        self,
        approval_id: str,
        approval_request_id: str,
        decision_request_id: str,
        decision: str,
        level: str,
        reason: str,
        steps_completed: List[str],
        context: Dict[str, Any],
        correlation_id: str = "",
        approver: str = "",
    ) -> None:
        """Record with both local and immutable audit."""
        self.record(approval_id, approval_request_id, decision_request_id,
                    decision, level, reason, steps_completed, context)

        if self._audit_engine:
            from .audit_event_type import AuditEventType
            from .audit_actor import AuditActor
            from .audit_action import AuditAction
            from .audit_outcome import AuditOutcome

            event_type_map = {
                "APPROVED": AuditEventType.APPROVAL_APPROVED,
                "REJECTED": AuditEventType.APPROVAL_REJECTED,
                "EXPIRED": AuditEventType.APPROVAL_EXPIRED,
                "CANCELLED": AuditEventType.APPROVAL_CANCELLED,
                "INVALIDATED": AuditEventType.APPROVAL_INVALIDATED,
            }
            event_type = event_type_map.get(decision, AuditEventType.APPROVAL_CREATED)

            self._audit_engine.record_event(
                event_type=event_type,
                entity_type="APPROVAL",
                entity_id=approval_id,
                actor=AuditActor.human(approver) if approver else AuditActor.system("approval-audit"),
                action=AuditAction.APPROVE if decision == "APPROVED" else AuditAction.DENY,
                outcome=AuditOutcome.APPROVAL_GRANTED if decision == "APPROVED" else AuditOutcome.APPROVAL_DENIED,
                reason=reason,
                correlation_id=correlation_id or f"CORR-{decision_request_id}",
            )
