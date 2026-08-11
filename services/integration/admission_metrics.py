"""AdmissionMetrics — tracks admission boundary performance and health.

Collects metrics per domain (risk, governance, authority, approval) and
per admission stage (validate, authorize, normalize, dedupe, reserve).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AdmissionMetrics:
    """Tracks admission rates, latencies, and rejection reasons.

    Provides operational visibility into the admission boundary:
    - Pass rates per check
    - Rejection reason distribution
    - Stage latencies
    - Duplicate detection rates
    """

    # Counters
    total_received: int = 0
    total_admitted: int = 0
    total_rejected: int = 0
    total_blocked: int = 0
    total_duplicates: int = 0
    total_expired: int = 0
    total_reservation_failed: int = 0

    # Per-check pass/fail
    check_results: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Rejection reason distribution
    rejection_reasons: Dict[str, int] = field(default_factory=dict)

    # Latency tracking (cumulative seconds)
    stage_latencies: Dict[str, float] = field(default_factory=dict)
    stage_counts: Dict[str, int] = field(default_factory=dict)

    # Timestamps
    started_at: float = field(default_factory=lambda: time.time())

    def record_received(self) -> None:
        self.total_received += 1

    def record_admitted(self) -> None:
        self.total_admitted += 1

    def record_rejected(self, reason_code: str = "") -> None:
        self.total_rejected += 1
        if reason_code:
            self.rejection_reasons[reason_code] = (
                self.rejection_reasons.get(reason_code, 0) + 1
            )

    def record_blocked(self, reason_code: str = "") -> None:
        self.total_blocked += 1
        if reason_code:
            self.rejection_reasons[reason_code] = (
                self.rejection_reasons.get(reason_code, 0) + 1
            )

    def record_duplicate(self) -> None:
        self.total_duplicates += 1

    def record_expired(self, reason_code: str = "") -> None:
        self.total_expired += 1
        if reason_code:
            self.rejection_reasons[reason_code] = (
                self.rejection_reasons.get(reason_code, 0) + 1
            )

    def record_reservation_failed(self, reason_code: str = "") -> None:
        self.total_reservation_failed += 1
        if reason_code:
            self.rejection_reasons[reason_code] = (
                self.rejection_reasons.get(reason_code, 0) + 1
            )

    def record_check(self, check_name: str, passed: bool) -> None:
        """Record a single check result."""
        if check_name not in self.check_results:
            self.check_results[check_name] = {"passed": 0, "failed": 0}
        if passed:
            self.check_results[check_name]["passed"] += 1
        else:
            self.check_results[check_name]["failed"] += 1

    def record_stage_latency(self, stage: str, latency_seconds: float) -> None:
        """Record latency for a specific admission stage."""
        self.stage_latencies[stage] = (
            self.stage_latencies.get(stage, 0.0) + latency_seconds
        )
        self.stage_counts[stage] = self.stage_counts.get(stage, 0) + 1

    def get_pass_rate(self, check_name: str) -> Optional[float]:
        """Get pass rate for a specific check."""
        results = self.check_results.get(check_name)
        if not results:
            return None
        total = results["passed"] + results["failed"]
        if total == 0:
            return None
        return results["passed"] / total

    def get_overall_pass_rate(self) -> float:
        """Overall admission pass rate (admitted / total_received)."""
        if self.total_received == 0:
            return 0.0
        return self.total_admitted / self.total_received

    def get_avg_stage_latency(self, stage: str) -> Optional[float]:
        """Get average latency for a stage."""
        total = self.stage_latencies.get(stage)
        count = self.stage_counts.get(stage, 0)
        if not total or count == 0:
            return None
        return total / count

    def get_top_rejection_reasons(self, n: int = 10) -> List[tuple]:
        """Get the top N rejection reasons."""
        sorted_reasons = sorted(
            self.rejection_reasons.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_reasons[:n]

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self.total_received = 0
        self.total_admitted = 0
        self.total_rejected = 0
        self.total_blocked = 0
        self.total_duplicates = 0
        self.total_expired = 0
        self.total_reservation_failed = 0
        self.check_results.clear()
        self.rejection_reasons.clear()
        self.stage_latencies.clear()
        self.stage_counts.clear()
        self.started_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counters": {
                "received": self.total_received,
                "admitted": self.total_admitted,
                "rejected": self.total_rejected,
                "blocked": self.total_blocked,
                "duplicates": self.total_duplicates,
                "expired": self.total_expired,
                "reservation_failed": self.total_reservation_failed,
            },
            "overall_pass_rate": self.get_overall_pass_rate(),
            "check_results": dict(self.check_results),
            "top_rejection_reasons": self.get_top_rejection_reasons(5),
            "stage_latencies": {
                s: self.get_avg_stage_latency(s)
                for s in self.stage_latencies
            },
            "uptime_seconds": time.time() - self.started_at,
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionMetrics(received={self.total_received}, "
            f"admitted={self.total_admitted}, "
            f"pass_rate={self.get_overall_pass_rate():.1%})"
        )
