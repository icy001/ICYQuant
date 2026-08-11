"""
Governance Audit Metrics — specialized metrics for the audit & lineage subsystem.

Tracks:
  - Audit event throughput and failures
  - Chain integrity and hash mismatches
  - Lineage completeness and orphans
  - Decision replay results
  - Human/emergency override counts
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class Counter:
    def __init__(self, name: str, help: str = ""):
        self.name = name
        self.help = help
        self._value: int = 0

    def inc(self, n: int = 1) -> None:
        self._value += n

    @property
    def value(self) -> int:
        return self._value

    def to_prometheus(self) -> str:
        return f"# HELP {self.name} {self.help}\n# TYPE {self.name} counter\n{self.name} {self._value}"


class Gauge:
    def __init__(self, name: str, help: str = ""):
        self.name = name
        self.help = help
        self._value: float = 0.0

    def set(self, val: float) -> None:
        self._value = val

    @property
    def value(self) -> float:
        return self._value

    def to_prometheus(self) -> str:
        return f"# HELP {self.name} {self.help}\n# TYPE {self.name} gauge\n{self.name} {self._value}"


class AuditMetrics:
    """Specialized metrics for the audit & lineage subsystem."""

    def __init__(self):
        # Audit events
        self.audit_events_total = Counter(
            "icyquant_audit_events_total",
            "Total audit events recorded",
        )
        self.audit_events_failed_total = Counter(
            "icyquant_audit_events_failed_total",
            "Total audit events that failed to record",
        )

        # Integrity
        self.audit_integrity_failures_total = Counter(
            "icyquant_audit_integrity_failures_total",
            "Total audit integrity failures detected",
        )
        self.audit_chain_breaks_total = Counter(
            "icyquant_audit_chain_breaks_total",
            "Total hash chain breaks detected",
        )
        self.audit_hash_mismatches_total = Counter(
            "icyquant_audit_hash_mismatches_total",
            "Total hash mismatches detected",
        )

        # Orphans & conflicts
        self.audit_orphan_events_total = Gauge(
            "icyquant_audit_orphan_events_total",
            "Number of orphan lineage nodes detected",
        )
        self.audit_lineage_conflicts_total = Gauge(
            "icyquant_audit_lineage_conflicts_total",
            "Number of lineage conflicts detected",
        )
        self.audit_incomplete_lineage_total = Gauge(
            "icyquant_audit_incomplete_lineage_total",
            "Number of incomplete lineage chains",
        )

        # Snapshots & replays
        self.decision_snapshots_total = Counter(
            "icyquant_decision_snapshots_total",
            "Total decision snapshots captured",
        )
        self.decision_replays_total = Counter(
            "icyquant_decision_replays_total",
            "Total decision replays performed",
        )
        self.decision_replay_mismatches_total = Counter(
            "icyquant_decision_replay_mismatches_total",
            "Total decision replay mismatches",
        )

        # Overrides
        self.human_overrides_total = Counter(
            "icyquant_human_overrides_total",
            "Total human override decisions",
        )
        self.emergency_overrides_total = Counter(
            "icyquant_emergency_overrides_total",
            "Total emergency override decisions",
        )

        # Lineage queries
        self.lineage_queries_total = Counter(
            "icyquant_lineage_queries_total",
            "Total lineage queries performed",
        )

        # Latencies
        self.lineage_reconstruction_latency = Gauge(
            "icyquant_lineage_reconstruction_latency",
            "Latest lineage reconstruction latency (ms)",
        )
        self.audit_write_latency = Gauge(
            "icyquant_audit_write_latency",
            "Latest audit write latency (ms)",
        )

        self._start_time = time.time()

    # ── Recording ──

    def record_audit_event(self, success: bool = True) -> None:
        self.audit_events_total.inc()
        if not success:
            self.audit_events_failed_total.inc()

    def record_integrity_failure(self) -> None:
        self.audit_integrity_failures_total.inc()

    def record_chain_break(self) -> None:
        self.audit_chain_breaks_total.inc()

    def record_hash_mismatch(self) -> None:
        self.audit_hash_mismatches_total.inc()

    def record_snapshot(self) -> None:
        self.decision_snapshots_total.inc()

    def record_replay(self, match: bool) -> None:
        self.decision_replays_total.inc()
        if not match:
            self.decision_replay_mismatches_total.inc()

    def record_human_override(self) -> None:
        self.human_overrides_total.inc()

    def record_emergency_override(self) -> None:
        self.emergency_overrides_total.inc()

    def record_lineage_query(self) -> None:
        self.lineage_queries_total.inc()

    # ── Gauges ──

    def set_orphans(self, count: int) -> None:
        self.audit_orphan_events_total.set(float(count))

    def set_lineage_conflicts(self, count: int) -> None:
        self.audit_lineage_conflicts_total.set(float(count))

    def set_incomplete_lineage(self, count: int) -> None:
        self.audit_incomplete_lineage_total.set(float(count))

    def set_write_latency(self, ms: float) -> None:
        self.audit_write_latency.set(ms)

    def set_reconstruction_latency(self, ms: float) -> None:
        self.lineage_reconstruction_latency.set(ms)

    # ── Snapshot & Export ──

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "audit_events_total": self.audit_events_total.value,
            "audit_events_failed": self.audit_events_failed_total.value,
            "integrity_failures": self.audit_integrity_failures_total.value,
            "chain_breaks": self.audit_chain_breaks_total.value,
            "hash_mismatches": self.audit_hash_mismatches_total.value,
            "orphans": self.audit_orphan_events_total.value,
            "lineage_conflicts": self.audit_lineage_conflicts_total.value,
            "incomplete_lineage": self.audit_incomplete_lineage_total.value,
            "snapshots": self.decision_snapshots_total.value,
            "replays": self.decision_replays_total.value,
            "replay_mismatches": self.decision_replay_mismatches_total.value,
            "human_overrides": self.human_overrides_total.value,
            "emergency_overrides": self.emergency_overrides_total.value,
            "lineage_queries": self.lineage_queries_total.value,
            "uptime_seconds": time.time() - self._start_time,
        }

    def to_prometheus(self) -> str:
        metrics = [
            self.audit_events_total,
            self.audit_events_failed_total,
            self.audit_integrity_failures_total,
            self.audit_chain_breaks_total,
            self.audit_hash_mismatches_total,
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
        return "\n".join(m.to_prometheus() for m in metrics)
