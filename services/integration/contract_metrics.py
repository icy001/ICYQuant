"""Contract Metrics — observability for cross-domain control contracts.

Tracks:
  - Contract issuance counts per domain.
  - Pass/reject/block/freeze/expired/error breakdowns.
  - Latency distributions per domain.
  - Constraint conflict counts.
  - Replay detection counts.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .contracts.control_contract import ControlContract
from .contracts.control_response import ControlResponse, ControlResponseStatus
from .contracts.control_decision import ControlDecision
from .contracts.control_reason import ReasonCode


@dataclass
class _DomainMetrics:
    """Per-domain metrics accumulator."""

    total: int = 0
    passed: int = 0
    rejected: int = 0
    blocked: int = 0
    frozen: int = 0
    expired: int = 0
    errors: int = 0

    latencies: List[float] = field(default_factory=list)
    reason_codes: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def p50_latency_ms(self) -> float:
        return self._percentile(50)

    @property
    def p99_latency_ms(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * p / 100.0)
        idx = min(idx, len(sorted_lat) - 1)
        return sorted_lat[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "rejected": self.rejected,
            "blocked": self.blocked,
            "frozen": self.frozen,
            "expired": self.expired,
            "errors": self.errors,
            "pass_rate": round(self.pass_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "top_reason_codes": dict(
                sorted(self.reason_codes.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }


@dataclass
class ContractMetrics:
    """Aggregates metrics across all cross-domain contract executions.

    Usage:
        metrics = ContractMetrics()

        # After each contract execution:
        metrics.record_contract(contract, response)

        # Query:
        print(metrics.summary())
        print(metrics.domain_breakdown())
    """

    _domains: Dict[str, _DomainMetrics] = field(default_factory=lambda: defaultdict(_DomainMetrics))

    # ── Global counters ──

    total_contracts: int = 0
    total_constraint_conflicts: int = 0
    total_replays_detected: int = 0
    total_validations_failed: int = 0

    started_at: float = field(default_factory=time.time)

    # ── Record ──

    def record_contract(
        self,
        contract: ControlContract,
        response: Optional[ControlResponse] = None,
        decision: Optional[ControlDecision] = None,
    ) -> None:
        """Record metrics for a contract execution."""
        self.total_contracts += 1
        domain = contract.domain or "unknown"
        dm = self._domains[domain]
        dm.total += 1

        if response is not None:
            status = response.status
            if status == ControlResponseStatus.PASS:
                dm.passed += 1
            elif status == ControlResponseStatus.REJECT:
                dm.rejected += 1
            elif status == ControlResponseStatus.BLOCK:
                dm.blocked += 1
            elif status == ControlResponseStatus.FREEZE:
                dm.frozen += 1
            elif status == ControlResponseStatus.EXPIRED:
                dm.expired += 1
            elif status == ControlResponseStatus.ERROR:
                dm.errors += 1

            dm.reason_codes[response.reason_code.name] += 1

            if response.latency_ms > 0:
                dm.latencies.append(response.latency_ms)

    def record_response(self, domain: str, response: ControlResponse) -> None:
        """Record metrics from a control response directly."""
        dm = self._domains[domain]
        dm.total += 1
        self.total_contracts += 1

        status = response.status
        if status == ControlResponseStatus.PASS:
            dm.passed += 1
        elif status == ControlResponseStatus.REJECT:
            dm.rejected += 1
        elif status == ControlResponseStatus.BLOCK:
            dm.blocked += 1
        elif status == ControlResponseStatus.FREEZE:
            dm.frozen += 1
        elif status == ControlResponseStatus.EXPIRED:
            dm.expired += 1
        elif status == ControlResponseStatus.ERROR:
            dm.errors += 1

        dm.reason_codes[response.reason_code.name] += 1

        if response.latency_ms > 0:
            dm.latencies.append(response.latency_ms)

    def record_conflict(self) -> None:
        self.total_constraint_conflicts += 1

    def record_replay(self) -> None:
        self.total_replays_detected += 1

    def record_validation_failure(self) -> None:
        self.total_validations_failed += 1

    # ── Queries ──

    def get_domain_metrics(self, domain: str) -> Optional[_DomainMetrics]:
        return self._domains.get(domain)

    def domain_breakdown(self) -> Dict[str, Dict[str, Any]]:
        return {d: m.to_dict() for d, m in sorted(self._domains.items())}

    def overall_pass_rate(self) -> float:
        total_passed = sum(m.passed for m in self._domains.values())
        if self.total_contracts == 0:
            return 0.0
        return total_passed / self.total_contracts

    def overall_avg_latency(self) -> float:
        all_lat = []
        for m in self._domains.values():
            all_lat.extend(m.latencies)
        if not all_lat:
            return 0.0
        return sum(all_lat) / len(all_lat)

    def summary(self) -> Dict[str, Any]:
        uptime = time.time() - self.started_at
        return {
            "uptime_seconds": round(uptime, 1),
            "total_contracts": self.total_contracts,
            "overall_pass_rate": round(self.overall_pass_rate(), 4),
            "overall_avg_latency_ms": round(self.overall_avg_latency(), 2),
            "constraint_conflicts": self.total_constraint_conflicts,
            "replays_detected": self.total_replays_detected,
            "validations_failed": self.total_validations_failed,
            "domains": self.domain_breakdown(),
        }

    def reset(self) -> None:
        self._domains.clear()
        self.total_contracts = 0
        self.total_constraint_conflicts = 0
        self.total_replays_detected = 0
        self.total_validations_failed = 0
        self.started_at = time.time()

    def __repr__(self) -> str:
        return (
            f"ContractMetrics(contracts={self.total_contracts}, "
            f"pass_rate={self.overall_pass_rate():.2%}, "
            f"domains={len(self._domains)})"
        )
