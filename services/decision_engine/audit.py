from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .decision import Decision


@dataclass
class AuditRecord:
    """A single audit entry recording a decision and its rationale."""

    decision: Decision
    reason: str = ""
    signal_details: Dict[str, float] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    market_regime: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DecisionAudit:
    """Records and queries the audit trail of all decisions.

    Answers: Why was this decision made?
    """

    def __init__(self):
        self.records: List[AuditRecord] = []

    def record(self, decision: Decision) -> AuditRecord:
        """Record a decision in the audit trail."""
        record = AuditRecord(
            decision=decision,
            reason=decision.reason,
            signal_details=dict(decision.signals),
            risk_metrics={"risk_score": decision.risk_score},
        )
        self.records.append(record)
        return record

    def record_detailed(
        self,
        decision: Decision,
        signal_details: Dict[str, float],
        risk_metrics: Dict[str, float],
        market_regime: str = "unknown",
    ) -> AuditRecord:
        """Record a decision with full context."""
        record = AuditRecord(
            decision=decision,
            reason=decision.reason,
            signal_details=signal_details,
            risk_metrics=risk_metrics,
            market_regime=market_regime,
        )
        self.records.append(record)
        return record

    def get_by_symbol(self, symbol: str) -> List[AuditRecord]:
        """Get all audit records for a given symbol."""
        return [
            r for r in self.records if r.decision.symbol == symbol
        ]

    def get_by_status(self, status: str) -> List[AuditRecord]:
        """Get all audit records with a given decision status."""
        return [
            r for r in self.records if r.decision.status == status
        ]

    def get_by_date_range(
        self, start: datetime, end: datetime
    ) -> List[AuditRecord]:
        """Get records within a date range."""
        return [
            r
            for r in self.records
            if start <= r.timestamp <= end
        ]

    def get_recent(self, n: int = 10) -> List[AuditRecord]:
        """Get the most recent n audit records (by insertion order)."""
        if not self.records:
            return []
        return list(reversed(self.records[-n:]))

    def summary(self) -> Dict[str, Any]:
        """Summary statistics of the audit trail."""
        if not self.records:
            return {"total_records": 0}

        actions = {}
        statuses = {}
        for r in self.records:
            actions[r.decision.action] = (
                actions.get(r.decision.action, 0) + 1
            )
            statuses[r.decision.status] = (
                statuses.get(r.decision.status, 0) + 1
            )

        avg_score = sum(
            r.decision.score for r in self.records
        ) / len(self.records)

        return {
            "total_records": len(self.records),
            "actions": actions,
            "statuses": statuses,
            "avg_score": round(avg_score, 4),
            "date_range": {
                "first": min(r.timestamp for r in self.records),
                "last": max(r.timestamp for r in self.records),
            },
        }
