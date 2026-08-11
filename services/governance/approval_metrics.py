"""
Approval Metrics — Prometheus-style metrics for approval/authority/delegation.

Tracks:
  - Approval request counts by status
  - Authority grant/revocation counts
  - Delegation counts and failures
  - Guard block counts
  - Latency metrics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ApprovalMetrics:
    """
    Metrics collector for the approval, authority, and delegation subsystems.

    Provides counters and gauges for all Part 1.3 components.
    """

    # Approval counters
    approval_requests_total: int = 0
    approval_pending_total: int = 0
    approval_approved_total: int = 0
    approval_rejected_total: int = 0
    approval_expired_total: int = 0
    approval_cancelled_total: int = 0
    approval_invalidated_total: int = 0
    approval_revalidation_total: int = 0

    # Authority counters
    authority_grants_total: int = 0
    authority_revocations_total: int = 0
    authority_failures_total: int = 0

    # Delegation counters
    delegations_total: int = 0
    delegation_failures_total: int = 0
    delegation_expired_total: int = 0

    # Guard counters
    approval_guard_blocks_total: int = 0

    # Latency
    approval_workflow_latency_ms: List[float] = field(default_factory=list)
    approval_time_to_decision_ms: List[float] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Increment methods
    # ------------------------------------------------------------------

    def inc_approval_request(self) -> None:
        self.approval_requests_total += 1

    def inc_approval_pending(self) -> None:
        self.approval_pending_total += 1

    def inc_approval_approved(self) -> None:
        self.approval_approved_total += 1

    def inc_approval_rejected(self) -> None:
        self.approval_rejected_total += 1

    def inc_approval_expired(self) -> None:
        self.approval_expired_total += 1

    def inc_approval_cancelled(self) -> None:
        self.approval_cancelled_total += 1

    def inc_approval_invalidated(self) -> None:
        self.approval_invalidated_total += 1

    def inc_approval_revalidation(self) -> None:
        self.approval_revalidation_total += 1

    def inc_authority_grant(self) -> None:
        self.authority_grants_total += 1

    def inc_authority_revocation(self) -> None:
        self.authority_revocations_total += 1

    def inc_authority_failure(self) -> None:
        self.authority_failures_total += 1

    def inc_delegation(self) -> None:
        self.delegations_total += 1

    def inc_delegation_failure(self) -> None:
        self.delegation_failures_total += 1

    def inc_delegation_expired(self) -> None:
        self.delegation_expired_total += 1

    def inc_approval_guard_block(self) -> None:
        self.approval_guard_blocks_total += 1

    # ------------------------------------------------------------------
    # Latency
    # ------------------------------------------------------------------

    def record_workflow_latency(self, ms: float) -> None:
        """Record approval workflow latency in milliseconds."""
        self.approval_workflow_latency_ms.append(ms)

    def record_time_to_decision(self, ms: float) -> None:
        """Record time from submission to decision in milliseconds."""
        self.approval_time_to_decision_ms.append(ms)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "approval": {
                "requests_total": self.approval_requests_total,
                "pending": self.approval_pending_total,
                "approved": self.approval_approved_total,
                "rejected": self.approval_rejected_total,
                "expired": self.approval_expired_total,
                "cancelled": self.approval_cancelled_total,
                "invalidated": self.approval_invalidated_total,
                "revalidations": self.approval_revalidation_total,
            },
            "authority": {
                "grants": self.authority_grants_total,
                "revocations": self.authority_revocations_total,
                "failures": self.authority_failures_total,
            },
            "delegation": {
                "total": self.delegations_total,
                "failures": self.delegation_failures_total,
                "expired": self.delegation_expired_total,
            },
            "guards": {
                "approval_guard_blocks": self.approval_guard_blocks_total,
            },
            "latency": {
                "workflow_avg_ms": self._avg(self.approval_workflow_latency_ms),
                "decision_avg_ms": self._avg(self.approval_time_to_decision_ms),
                "workflow_count": len(self.approval_workflow_latency_ms),
                "decision_count": len(self.approval_time_to_decision_ms),
            },
        }

    @staticmethod
    def _avg(values: List[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)


# Global metrics instance
_approval_metrics_instance: ApprovalMetrics = ApprovalMetrics()


def get_approval_metrics() -> ApprovalMetrics:
    """Get the global approval metrics instance."""
    global _approval_metrics_instance
    return _approval_metrics_instance
