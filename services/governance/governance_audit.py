"""
Governance Audit — cross-cutting audit for the entire governance subsystem.

Aggregates audit data from decision audit, policy audit, and approval audit
to provide a unified institutional audit view.

Part 1.4: now also integrates with AuditEngine, LineageEngine, and
DecisionRecord for full end-to-end lineage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .decision_audit import DecisionAudit, AuditRecord
from .policy_audit import PolicyAudit
from .approval_audit import ApprovalAudit


@dataclass
class GovernanceAuditReport:
    """A unified governance audit report."""

    report_id: str = ""
    generated_at: float = field(default_factory=time.time)

    # Aggregate stats
    total_decisions: int = 0
    allowed: int = 0
    rejected: int = 0
    blocked: int = 0
    overrides: int = 0
    approvals: int = 0
    policy_violations: int = 0

    # Top reasons
    top_block_reasons: List[str] = field(default_factory=list)
    top_override_reasons: List[str] = field(default_factory=list)

    # Compliance
    decisions_without_audit: int = 0


class GovernanceAudit:
    """
    Aggregates all audit subsystems into a unified governance audit view.

    Part 1.4: now also integrates with AuditEngine and LineageEngine
    for immutable event recording and full lineage resolution.
    """

    def __init__(
        self,
        decision_audit: Optional[DecisionAudit] = None,
        policy_audit: Optional[PolicyAudit] = None,
        approval_audit: Optional[ApprovalAudit] = None,
        audit_engine: Any = None,
        lineage_engine: Any = None,
    ):
        self._decision = decision_audit or DecisionAudit()
        self._policy = policy_audit or PolicyAudit()
        self._approval = approval_audit or ApprovalAudit()
        self._audit_engine = audit_engine  # Optional AuditEngine
        self._lineage_engine = lineage_engine  # Optional LineageEngine

    # ------------------------------------------------------------------
    # Sub-auditors
    # ------------------------------------------------------------------

    @property
    def decision(self) -> DecisionAudit:
        return self._decision

    @property
    def policy(self) -> PolicyAudit:
        return self._policy

    @property
    def approval(self) -> ApprovalAudit:
        return self._approval

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_report(self) -> GovernanceAuditReport:
        """Generate a unified governance audit report."""
        decision_stats = self._decision.stats()
        policy_count = self._policy.count()
        approval_count = self._approval.count()

        report = GovernanceAuditReport(
            report_id=f"GA-{int(time.time())}",
            total_decisions=decision_stats.get("total", 0),
            allowed=decision_stats.get("verdicts", {}).get("ALLOW", 0),
            rejected=decision_stats.get("verdicts", {}).get("REJECT", 0),
            blocked=decision_stats.get("verdicts", {}).get("BLOCKED", 0),
            overrides=decision_stats.get("overrides", 0),
            approvals=approval_count,
            policy_violations=policy_count,
        )

        # Top block reasons
        blocked = self._decision.get_blocked_decisions(limit=20)
        reason_counts: Dict[str, int] = {}
        for b in blocked:
            reason = b.get("reason", "")[:80]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        report.top_block_reasons = [
            r for r, _ in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return report

    def get_full_trace(self, decision_id: str) -> Dict[str, Any]:
        """Get the full audit trace for a single decision."""
        decision = self._decision.get(decision_id)
        if not decision:
            return {"error": f"No audit record for decision {decision_id}"}

        return {
            "decision": decision.to_dict() if hasattr(decision, "to_dict") else str(decision),
            "policy_evaluations": self._policy.get_by_decision(decision_id),
            "approval": self._approval.get_by_decision(decision_id),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a quick governance summary."""
        stats = self._decision.stats()
        return {
            "total_decisions": stats.get("total", 0),
            "verdicts": stats.get("verdicts", {}),
            "overrides": stats.get("overrides", 0),
            "policy_violations": self._policy.count(),
            "approvals": self._approval.count(),
        }

    # ── Part 1.4: Immutable Audit & Lineage Integration ──

    def set_audit_engine(self, engine: Any) -> None:
        """Set the AuditEngine and propagate to sub-auditors."""
        self._audit_engine = engine
        self._decision.set_audit_engine(engine)
        self._policy.set_audit_engine(engine)
        self._approval.set_audit_engine(engine)

    def set_lineage_engine(self, engine: Any) -> None:
        """Set the LineageEngine for full lineage resolution."""
        self._lineage_engine = engine

    def get_full_lineage(self, decision_id: str) -> Dict[str, Any]:
        """Get the full decision lineage from the LineageEngine."""
        if not self._lineage_engine:
            return {"error": "LineageEngine not configured"}

        nodes = self._lineage_engine.graph.get_nodes_by_entity("DECISION", decision_id)
        if not nodes:
            return {"error": f"No lineage nodes for decision {decision_id}"}

        return self._lineage_engine.resolve_full(nodes[0].node_id)

    def verify_audit_integrity(self) -> Dict[str, Any]:
        """Verify audit integrity via the AuditEngine."""
        if not self._audit_engine:
            return {"error": "AuditEngine not configured"}
        return self._audit_engine.verify_integrity()

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report including lineage metrics."""
        report = self.generate_report()
        result = {
            "report": {
                "report_id": report.report_id,
                "generated_at": report.generated_at,
                "total_decisions": report.total_decisions,
                "allowed": report.allowed,
                "rejected": report.rejected,
                "blocked": report.blocked,
                "overrides": report.overrides,
                "approvals": report.approvals,
                "policy_violations": report.policy_violations,
            },
        }

        if self._audit_engine:
            result["audit_metrics"] = self._audit_engine.get_metrics()
            result["integrity"] = self._audit_engine.verify_integrity()

        if self._lineage_engine:
            result["lineage_metrics"] = self._lineage_engine.get_metrics()
            result["orphans"] = self._lineage_engine.detect_orphans()

        return result
