"""
Governance Metrics — Prometheus-style metrics for the governance subsystem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GaugeMetric:
    """A simple gauge metric."""

    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    help: str = ""

    def set(self, value: float) -> None:
        self.value = value

    def inc(self, delta: float = 1.0) -> None:
        self.value += delta

    def dec(self, delta: float = 1.0) -> None:
        self.value -= delta

    def to_prometheus(self) -> str:
        label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
        label_part = f"{{{label_str}}}" if label_str else ""
        return f"{self.name}{label_part} {self.value}"


@dataclass
class CounterMetric:
    """A monotonically increasing counter."""

    name: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    help: str = ""

    def inc(self, delta: int = 1) -> None:
        self.value += delta

    def to_prometheus(self) -> str:
        label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
        label_part = f"{{{label_str}}}" if label_str else ""
        return f"{self.name}{label_part} {self.value}"


class GovernanceMetrics:
    """
    Governance subsystem metrics.

    Tracks:
      - Decision counts (total, allowed, rejected, blocked, review, approvals, overrides)
      - Policy evaluation counts and breaches
      - Authority check counts and failures
      - Constraint check counts and failures
      - Decision guard blocks
      - Decision latency
      - Audit record counts
    """

    def __init__(self):
        # Decision counters
        self.decisions_total = CounterMetric(
            name="icyquant_governance_decisions_total",
            help="Total governance decisions evaluated",
        )
        self.allowed_total = CounterMetric(
            name="icyquant_governance_allowed_total",
            help="Decisions allowed",
        )
        self.rejected_total = CounterMetric(
            name="icyquant_governance_rejected_total",
            help="Decisions rejected",
        )
        self.blocked_total = CounterMetric(
            name="icyquant_governance_blocked_total",
            help="Decisions blocked",
        )
        self.review_required_total = CounterMetric(
            name="icyquant_governance_review_required_total",
            help="Decisions requiring review",
        )
        self.approval_required_total = CounterMetric(
            name="icyquant_governance_approval_required_total",
            help="Approvals required",
        )
        self.approved_total = CounterMetric(
            name="icyquant_governance_approved_total",
            help="Approvals granted",
        )
        self.overrides_total = CounterMetric(
            name="icyquant_governance_overrides_total",
            help="Decisions overridden",
        )

        # Policy counters
        self.policy_evaluations_total = CounterMetric(
            name="icyquant_policy_evaluations_total",
            help="Total policy evaluations",
        )
        self.policy_breaches_total = CounterMetric(
            name="icyquant_policy_breaches_total",
            help="Total policy breaches",
        )

        # Authority counters
        self.authority_checks_total = CounterMetric(
            name="icyquant_authority_checks_total",
            help="Total authority checks",
        )
        self.authority_failures_total = CounterMetric(
            name="icyquant_authority_failures_total",
            help="Authority check failures",
        )

        # Constraint counters
        self.constraint_checks_total = CounterMetric(
            name="icyquant_constraint_checks_total",
            help="Total constraint checks",
        )
        self.constraint_failures_total = CounterMetric(
            name="icyquant_constraint_failures_total",
            help="Constraint check failures",
        )

        # Guard
        self.decision_guard_blocks_total = CounterMetric(
            name="icyquant_decision_guard_blocks_total",
            help="Decision guard blocks",
        )

        # Latency
        self.decision_latency = GaugeMetric(
            name="icyquant_governance_decision_latency",
            help="Average governance decision latency",
        )

        # Audit
        self.audit_records_total = CounterMetric(
            name="icyquant_governance_audit_records_total",
            help="Total audit records",
        )

        # ---- Versioned policy metrics ----
        self.policy_versions_total = CounterMetric(
            name="icyquant_policy_versions_total",
            help="Total policy versions created",
        )
        self.policy_versions_active = GaugeMetric(
            name="icyquant_policy_versions_active",
            help="Currently active policy versions",
        )
        self.policy_versions_published = GaugeMetric(
            name="icyquant_policy_versions_published",
            help="Currently published policy versions",
        )
        self.policy_activations_total = CounterMetric(
            name="icyquant_policy_activations_total",
            help="Total policy activations",
        )
        self.policy_rollbacks_total = CounterMetric(
            name="icyquant_policy_rollbacks_total",
            help="Total policy rollbacks",
        )
        self.policy_conflicts_detected = GaugeMetric(
            name="icyquant_policy_conflicts_detected",
            help="Number of unresolved policy conflicts",
        )
        self.policy_overrides_active = GaugeMetric(
            name="icyquant_policy_overrides_active",
            help="Currently active policy overrides",
        )
        self.policy_cache_hits = CounterMetric(
            name="icyquant_policy_cache_hits",
            help="Policy evaluation cache hits",
        )
        self.policy_cache_misses = CounterMetric(
            name="icyquant_policy_cache_misses",
            help="Policy evaluation cache misses",
        )

        # ---- Part 1.4: Audit & Lineage metrics ----
        self.audit_events_total = CounterMetric(
            name="icyquant_audit_events_total",
            help="Total immutable audit events recorded",
        )
        self.audit_integrity_failures_total = CounterMetric(
            name="icyquant_audit_integrity_failures_total",
            help="Total audit integrity failures",
        )
        self.audit_chain_breaks_total = CounterMetric(
            name="icyquant_audit_chain_breaks_total",
            help="Total audit chain breaks",
        )
        self.audit_orphan_events_total = GaugeMetric(
            name="icyquant_audit_orphan_events_total",
            help="Detected orphan events",
        )
        self.audit_lineage_conflicts_total = GaugeMetric(
            name="icyquant_audit_lineage_conflicts_total",
            help="Detected lineage conflicts",
        )
        self.audit_incomplete_lineage_total = GaugeMetric(
            name="icyquant_audit_incomplete_lineage_total",
            help="Incomplete lineage chains",
        )
        self.decision_snapshots_total = CounterMetric(
            name="icyquant_decision_snapshots_total",
            help="Total decision snapshots captured",
        )
        self.decision_replays_total = CounterMetric(
            name="icyquant_decision_replays_total",
            help="Total decision replays",
        )
        self.decision_replay_mismatches_total = CounterMetric(
            name="icyquant_decision_replay_mismatches_total",
            help="Decision replay mismatches",
        )
        self.human_overrides_total = CounterMetric(
            name="icyquant_human_overrides_total",
            help="Total human overrides",
        )
        self.emergency_overrides_total = CounterMetric(
            name="icyquant_emergency_overrides_total",
            help="Total emergency overrides",
        )
        self.lineage_queries_total = CounterMetric(
            name="icyquant_lineage_queries_total",
            help="Total lineage queries",
        )
        self.lineage_reconstruction_latency = GaugeMetric(
            name="icyquant_lineage_reconstruction_latency",
            help="Lineage reconstruction latency (ms)",
        )
        self.audit_write_latency = GaugeMetric(
            name="icyquant_audit_write_latency",
            help="Audit write latency (ms)",
        )

        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Convenience recorder
    # ------------------------------------------------------------------

    def record_decision(self, verdict: str, latency_ms: float) -> None:
        self.decisions_total.inc()
        self.decision_latency.set(latency_ms)

        verdict = verdict.upper()
        if verdict == "ALLOW":
            self.allowed_total.inc()
        elif verdict in ("REJECT", "REJECTED"):
            self.rejected_total.inc()
        elif verdict == "BLOCKED":
            self.blocked_total.inc()
        elif verdict == "REVIEW":
            self.review_required_total.inc()
        elif verdict == "OVERRIDDEN":
            self.overrides_total.inc()

    def record_policy_evaluation(self, passed: bool) -> None:
        self.policy_evaluations_total.inc()
        if not passed:
            self.policy_breaches_total.inc()

    def record_authority_check(self, authorized: bool) -> None:
        self.authority_checks_total.inc()
        if not authorized:
            self.authority_failures_total.inc()

    def record_constraint_check(self, passed: bool) -> None:
        self.constraint_checks_total.inc()
        if not passed:
            self.constraint_failures_total.inc()

    def record_guard_block(self) -> None:
        self.decision_guard_blocks_total.inc()

    def record_audit(self) -> None:
        self.audit_records_total.inc()

    def record_version_created(self) -> None:
        self.policy_versions_total.inc()

    def record_activation(self) -> None:
        self.policy_activations_total.inc()

    def record_rollback(self) -> None:
        self.policy_rollbacks_total.inc()

    def record_cache_hit(self) -> None:
        self.policy_cache_hits.inc()

    def record_cache_miss(self) -> None:
        self.policy_cache_misses.inc()

    def set_active_versions(self, count: int) -> None:
        self.policy_versions_active.set(float(count))

    def set_published_versions(self, count: int) -> None:
        self.policy_versions_published.set(float(count))

    def set_conflicts_detected(self, count: int) -> None:
        self.policy_conflicts_detected.set(float(count))

    def set_overrides_active(self, count: int) -> None:
        self.policy_overrides_active.set(float(count))

    def record_version_event(
        self, event_type: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a version lifecycle event."""
        event_map = {
            "CREATED": self.record_version_created,
            "ACTIVATED": self.record_activation,
            "ROLLBACK": self.record_rollback,
        }
        fn = event_map.get(event_type)
        if fn:
            fn()

    # ── Part 1.4: Audit & Lineage recorders ──

    def record_audit_event(self) -> None:
        self.audit_events_total.inc()

    def record_audit_integrity_failure(self) -> None:
        self.audit_integrity_failures_total.inc()

    def record_audit_chain_break(self) -> None:
        self.audit_chain_breaks_total.inc()

    def record_decision_snapshot(self) -> None:
        self.decision_snapshots_total.inc()

    def record_decision_replay(self, match: bool) -> None:
        self.decision_replays_total.inc()
        if not match:
            self.decision_replay_mismatches_total.inc()

    def record_human_override(self) -> None:
        self.human_overrides_total.inc()

    def record_emergency_override(self) -> None:
        self.emergency_overrides_total.inc()

    def record_lineage_query(self) -> None:
        self.lineage_queries_total.inc()

    def set_lineage_reconstruction_latency(self, ms: float) -> None:
        self.lineage_reconstruction_latency.set(ms)

    def set_audit_write_latency(self, ms: float) -> None:
        self.audit_write_latency.set(ms)

    # ── Part 1.3: Approval / Delegation / Authority metrics ──

    def record_approval_request(self) -> None:
        if hasattr(self, "approval_requests_total"):
            self.approval_requests_total.inc()

    def record_approval_approved(self) -> None:
        if hasattr(self, "approval_approved_total"):
            self.approval_approved_total.inc()

    def record_approval_rejected(self) -> None:
        if hasattr(self, "approval_rejected_total"):
            self.approval_rejected_total.inc()

    def record_approval_expired(self) -> None:
        if hasattr(self, "approval_expired_total"):
            self.approval_expired_total.inc()

    def record_approval_cancelled(self) -> None:
        if hasattr(self, "approval_cancelled_total"):
            self.approval_cancelled_total.inc()

    def record_approval_invalidated(self) -> None:
        if hasattr(self, "approval_invalidated_total"):
            self.approval_invalidated_total.inc()

    def record_authority_grant(self) -> None:
        if hasattr(self, "authority_grants_total"):
            self.authority_grants_total.inc()

    def record_authority_revocation(self) -> None:
        if hasattr(self, "authority_revocations_total"):
            self.authority_revocations_total.inc()

    def record_delegation_created(self) -> None:
        if hasattr(self, "delegations_total"):
            self.delegations_total.inc()

    def record_delegation_failure(self) -> None:
        if hasattr(self, "delegation_failures_total"):
            self.delegation_failures_total.inc()

    def record_delegation_expired(self) -> None:
        if hasattr(self, "delegation_expired_total"):
            self.delegation_expired_total.inc()

    def record_approval_guard_block(self) -> None:
        if hasattr(self, "approval_guard_blocks_total"):
            self.approval_guard_blocks_total.inc()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_prometheus(self) -> str:
        """Export all metrics in Prometheus exposition format."""
        metrics = [
            self.decisions_total,
            self.allowed_total,
            self.rejected_total,
            self.blocked_total,
            self.review_required_total,
            self.approval_required_total,
            self.approved_total,
            self.overrides_total,
            self.policy_evaluations_total,
            self.policy_breaches_total,
            self.authority_checks_total,
            self.authority_failures_total,
            self.constraint_checks_total,
            self.constraint_failures_total,
            self.decision_guard_blocks_total,
            self.decision_latency,
            self.audit_records_total,
            self.policy_versions_total,
            self.policy_versions_active,
            self.policy_versions_published,
            self.policy_activations_total,
            self.policy_rollbacks_total,
            self.policy_conflicts_detected,
            self.policy_overrides_active,
            self.policy_cache_hits,
            self.policy_cache_misses,
            self.audit_events_total,
            self.audit_integrity_failures_total,
            self.audit_chain_breaks_total,
            self.audit_orphan_events_total,
            self.audit_lineage_conflicts_total,
            self.audit_incomplete_lineage_total,
            self.decision_snapshots_total,
            self.decision_replays_total,
            self.decision_replay_mismatches_total,
            self.human_overrides_total,
            self.emergency_overrides_total,
            self.lineage_queries_total,
            self.lineage_reconstruction_latency,
            self.audit_write_latency,
        ]
        lines = []
        for m in metrics:
            if m.help:
                lines.append(f"# HELP {m.name} {m.help}")
                lines.append(f"# TYPE {m.name} {'counter' if isinstance(m, CounterMetric) else 'gauge'}")
            lines.append(m.to_prometheus())
        return "\n".join(lines)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a JSON snapshot of all metrics."""
        return {
            "decisions": {
                "total": self.decisions_total.value,
                "allowed": self.allowed_total.value,
                "rejected": self.rejected_total.value,
                "blocked": self.blocked_total.value,
                "review_required": self.review_required_total.value,
                "approval_required": self.approval_required_total.value,
                "approved": self.approved_total.value,
                "overrides": self.overrides_total.value,
            },
            "policy": {
                "evaluations": self.policy_evaluations_total.value,
                "breaches": self.policy_breaches_total.value,
            },
            "authority": {
                "checks": self.authority_checks_total.value,
                "failures": self.authority_failures_total.value,
            },
            "constraints": {
                "checks": self.constraint_checks_total.value,
                "failures": self.constraint_failures_total.value,
            },
            "guard_blocks": self.decision_guard_blocks_total.value,
            "avg_latency": self.decision_latency.value,
            "audit_records": self.audit_records_total.value,
            # Versioned policy metrics
            "policy_versions": {
                "total": self.policy_versions_total.value,
                "active": self.policy_versions_active.value,
                "published": self.policy_versions_published.value,
            },
            "policy_activations": self.policy_activations_total.value,
            "policy_rollbacks": self.policy_rollbacks_total.value,
            "policy_conflicts": self.policy_conflicts_detected.value,
            "policy_overrides_active": self.policy_overrides_active.value,
            "policy_cache": {
                "hits": self.policy_cache_hits.value,
                "misses": self.policy_cache_misses.value,
            },
            "audit": {
                "events_total": self.audit_events_total.value,
                "integrity_failures": self.audit_integrity_failures_total.value,
                "chain_breaks": self.audit_chain_breaks_total.value,
                "orphans": self.audit_orphan_events_total.value,
                "lineage_conflicts": self.audit_lineage_conflicts_total.value,
                "incomplete_lineage": self.audit_incomplete_lineage_total.value,
                "write_latency_ms": self.audit_write_latency.value,
            },
            "lineage": {
                "snapshots": self.decision_snapshots_total.value,
                "replays": self.decision_replays_total.value,
                "replay_mismatches": self.decision_replay_mismatches_total.value,
                "queries": self.lineage_queries_total.value,
                "reconstruction_latency_ms": self.lineage_reconstruction_latency.value,
            },
            "overrides": {
                "human": self.human_overrides_total.value,
                "emergency": self.emergency_overrides_total.value,
            },
            "uptime_seconds": time.time() - self._start_time,
        }
