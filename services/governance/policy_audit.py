"""
Policy Audit — records policy evaluation history.

Integrates with AuditEngine for unified immutable audit recording.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class PolicyAudit:
    """
    Records and queries policy evaluation history.
    Tracks which policies were evaluated, their results, and violations.

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
        decision_id: str,
        request_id: str,
        policy_id: str,
        policy_name: str,
        passed: bool,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        """Record a policy evaluation."""
        entry = {
            "decision_id": decision_id,
            "request_id": request_id,
            "policy_id": policy_id,
            "policy_name": policy_name,
            "passed": passed,
            "violations": violations,
            "warnings": warnings,
            "timestamp": time.time(),
        }
        self._records.append(entry)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_by_decision(self, decision_id: str) -> List[Dict[str, Any]]:
        """Get all policy evaluations for a decision."""
        return [r for r in self._records if r["decision_id"] == decision_id]

    def get_by_policy(self, policy_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all evaluations for a specific policy."""
        results = []
        for r in reversed(self._records):
            if r["policy_id"] == policy_id:
                results.append(r)
                if len(results) >= limit:
                    break
        return results

    def get_violations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all evaluations with violations."""
        results = []
        for r in reversed(self._records):
            if not r["passed"]:
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

    def violation_count(self) -> int:
        return sum(1 for r in self._records if not r["passed"])

    def policy_violation_rates(self) -> Dict[str, float]:
        """Violation rate per policy."""
        totals: Dict[str, int] = {}
        violations: Dict[str, int] = {}
        for r in self._records:
            pid = r["policy_id"]
            totals[pid] = totals.get(pid, 0) + 1
            if not r["passed"]:
                violations[pid] = violations.get(pid, 0) + 1

        rates = {}
        for pid in totals:
            rates[pid] = violations.get(pid, 0) / totals[pid] if totals[pid] > 0 else 0.0
        return rates

    def clear(self) -> None:
        self._records.clear()

    # ── AuditEngine Integration ──

    def set_audit_engine(self, engine: Any) -> None:
        """Set the AuditEngine for immutable event recording."""
        self._audit_engine = engine

    def record_with_audit(
        self,
        decision_id: str,
        request_id: str,
        policy_id: str,
        policy_name: str,
        passed: bool,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
        correlation_id: str = "",
        policy_version: str = "",
        policy_hash: str = "",
    ) -> None:
        """Record with both local and immutable audit."""
        self.record(decision_id, request_id, policy_id, policy_name,
                    passed, violations, warnings)

        # Also record as immutable AuditEvent if engine is available
        if self._audit_engine:
            from .audit_event_type import AuditEventType
            from .audit_actor import AuditActor
            from .audit_action import AuditAction
            from .audit_outcome import AuditOutcome

            outcome = AuditOutcome.POLICY_PASS if passed else AuditOutcome.POLICY_FAIL
            self._audit_engine.record_event(
                event_type=AuditEventType.POLICY_ACTIVATED if passed else AuditEventType.POLICY_REVOKED,
                entity_type="POLICY",
                entity_id=policy_id,
                actor=AuditActor.system("policy-audit"),
                action=AuditAction.VALIDATE,
                outcome=outcome,
                reason=f"Policy {policy_name}: {'PASS' if passed else 'FAIL'}",
                correlation_id=correlation_id or f"CORR-{decision_id}",
            )
