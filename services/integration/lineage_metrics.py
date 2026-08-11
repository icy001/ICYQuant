"""Lineage Metrics — observability for the control lineage infrastructure.

Tracks lineage creation, completion, broken links, missing events,
and other integrity-related metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LineageMetrics:
    """Aggregated metrics for control lineage operations."""

    lineages_created: int = 0
    lineages_completed: int = 0
    lineages_frozen: int = 0
    lineages_revoked: int = 0

    nodes_created: int = 0
    edges_created: int = 0

    broken_links_detected: int = 0
    missing_events_detected: int = 0
    inconsistency_errors: int = 0

    snapshots_captured: int = 0
    audit_events_recorded: int = 0

    chain_verifications: int = 0
    chain_verification_failures: int = 0

    # ── Mutators ──────────────────────────────────────────────────

    def record_lineage_created(self) -> None:
        self.lineages_created += 1

    def record_lineage_completed(self) -> None:
        self.lineages_completed += 1

    def record_lineage_frozen(self) -> None:
        self.lineages_frozen += 1

    def record_lineage_revoked(self) -> None:
        self.lineages_revoked += 1

    def record_node_created(self, count: int = 1) -> None:
        self.nodes_created += count

    def record_edge_created(self, count: int = 1) -> None:
        self.edges_created += count

    def record_broken_link(self) -> None:
        self.broken_links_detected += 1

    def record_missing_event(self) -> None:
        self.missing_events_detected += 1

    def record_inconsistency(self) -> None:
        self.inconsistency_errors += 1

    def record_snapshot(self) -> None:
        self.snapshots_captured += 1

    def record_audit_event(self) -> None:
        self.audit_events_recorded += 1

    def record_chain_verification(self, passed: bool) -> None:
        self.chain_verifications += 1
        if not passed:
            self.chain_verification_failures += 1

    # ── Summary ───────────────────────────────────────────────────

    @property
    def total_lineages(self) -> int:
        return self.lineages_created

    @property
    def active_lineages(self) -> int:
        return (
            self.lineages_created
            - self.lineages_completed
            - self.lineages_frozen
            - self.lineages_revoked
        )

    def summary(self) -> dict[str, Any]:
        """Return a metrics summary suitable for monitoring dashboards."""
        total = max(self.chain_verifications, 1)
        return {
            "lineages": {
                "created": self.lineages_created,
                "completed": self.lineages_completed,
                "frozen": self.lineages_frozen,
                "revoked": self.lineages_revoked,
                "active": self.active_lineages,
            },
            "graph": {
                "nodes_created": self.nodes_created,
                "edges_created": self.edges_created,
            },
            "integrity": {
                "broken_links": self.broken_links_detected,
                "missing_events": self.missing_events_detected,
                "inconsistencies": self.inconsistency_errors,
            },
            "audit": {
                "events_recorded": self.audit_events_recorded,
                "snapshots": self.snapshots_captured,
                "chain_verifications": self.chain_verifications,
                "chain_failures": self.chain_verification_failures,
                "chain_pass_rate": round(
                    (self.chain_verifications
                     - self.chain_verification_failures)
                    / total * 100, 2
                ),
            },
        }
