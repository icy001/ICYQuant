"""
Integration Metrics — monitors integration control flow health and performance.

Commit 21 Part 1.1: tracks flow throughput, gate pass/fail rates, latency,
and error rates across the institutional trading control pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_state import ControlFlowState
from .control_result import GateStatus


@dataclass
class FlowMetrics:
    """Per-flow latency tracking."""

    flow_id: str = ""
    started_at: float = 0.0
    risk_latency_ms: float = 0.0
    governance_latency_ms: float = 0.0
    authority_latency_ms: float = 0.0
    approval_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    final_state: str = ""


@dataclass
class GateMetrics:
    """Per-gate pass/fail metrics."""

    passed: int = 0
    rejected: int = 0
    blocked: int = 0
    frozen: int = 0
    expired: int = 0
    errors: int = 0

    def total(self) -> int:
        return self.passed + self.rejected + self.blocked + self.frozen + self.expired + self.errors

    def pass_rate(self) -> float:
        total = self.total()
        return self.passed / total if total > 0 else 0.0

    def record(self, status: GateStatus) -> None:
        if status == GateStatus.PASS:
            self.passed += 1
        elif status == GateStatus.REJECT:
            self.rejected += 1
        elif status == GateStatus.BLOCK:
            self.blocked += 1
        elif status == GateStatus.FREEZE:
            self.frozen += 1
        elif status == GateStatus.EXPIRED:
            self.expired += 1
        elif status == GateStatus.ERROR:
            self.errors += 1


@dataclass
class IntegrationMetrics:
    """Central metrics for the integration control flow."""

    # ── Flow Counters ──────────────────────────────────────────
    total_flows: int = 0
    active_flows: int = 0
    completed_flows: int = 0
    failed_flows: int = 0

    # ── Outcome Counters ───────────────────────────────────────
    executed_count: int = 0
    rejected_count: int = 0
    blocked_count: int = 0
    frozen_count: int = 0
    cancelled_count: int = 0
    expired_count: int = 0

    # ── Gate Metrics ───────────────────────────────────────────
    risk_metrics: GateMetrics = field(default_factory=GateMetrics)
    governance_metrics: GateMetrics = field(default_factory=GateMetrics)
    authority_metrics: GateMetrics = field(default_factory=GateMetrics)
    approval_metrics: GateMetrics = field(default_factory=GateMetrics)

    # ── Latency ────────────────────────────────────────────────
    _flow_latencies: List[FlowMetrics] = field(default_factory=list)
    _max_latency_samples: int = 1000

    # ── Errors ─────────────────────────────────────────────────
    error_count: int = 0
    last_error: str = ""
    last_error_time: float = 0.0

    # ── Timing ─────────────────────────────────────────────────
    started_at: float = field(default_factory=time.time)

    # ── Recording ──────────────────────────────────────────────

    def record_flow_started(self) -> None:
        self.total_flows += 1
        self.active_flows += 1

    def record_flow_completed(self, final_state: ControlFlowState) -> None:
        self.active_flows = max(0, self.active_flows - 1)
        if final_state == ControlFlowState.EXECUTED:
            self.executed_count += 1
            self.completed_flows += 1
        elif final_state == ControlFlowState.REJECTED:
            self.rejected_count += 1
            self.failed_flows += 1
        elif final_state == ControlFlowState.BLOCKED:
            self.blocked_count += 1
            self.failed_flows += 1
        elif final_state == ControlFlowState.FROZEN:
            self.frozen_count += 1
            self.failed_flows += 1
        elif final_state == ControlFlowState.CANCELLED:
            self.cancelled_count += 1
            self.completed_flows += 1
        elif final_state == ControlFlowState.EXPIRED:
            self.expired_count += 1
            self.failed_flows += 1
        elif final_state == ControlFlowState.FAILED:
            self.failed_flows += 1

    def record_gate_result(self, gate_name: str, status: GateStatus) -> None:
        metrics_map = {
            "risk": self.risk_metrics,
            "governance": self.governance_metrics,
            "authority": self.authority_metrics,
            "approval": self.approval_metrics,
        }
        if gate_name in metrics_map:
            metrics_map[gate_name].record(status)

    def record_flow_latency(self, flow_metrics: FlowMetrics) -> None:
        self._flow_latencies.append(flow_metrics)
        if len(self._flow_latencies) > self._max_latency_samples:
            self._flow_latencies = self._flow_latencies[-self._max_latency_samples:]

    def record_error(self, error: str) -> None:
        self.error_count += 1
        self.last_error = error
        self.last_error_time = time.time()

    # ── Aggregation ────────────────────────────────────────────

    def avg_total_latency_ms(self) -> float:
        if not self._flow_latencies:
            return 0.0
        return sum(f.total_latency_ms for f in self._flow_latencies) / len(self._flow_latencies)

    def overall_pass_rate(self) -> float:
        total = self.total_flows
        return self.executed_count / total if total > 0 else 0.0

    def gate_pass_rates(self) -> Dict[str, float]:
        return {
            "risk": self.risk_metrics.pass_rate(),
            "governance": self.governance_metrics.pass_rate(),
            "authority": self.authority_metrics.pass_rate(),
            "approval": self.approval_metrics.pass_rate(),
        }

    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    # ── Summary ────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "total_flows": self.total_flows,
            "active_flows": self.active_flows,
            "completed_flows": self.completed_flows,
            "failed_flows": self.failed_flows,
            "outcomes": {
                "executed": self.executed_count,
                "rejected": self.rejected_count,
                "blocked": self.blocked_count,
                "frozen": self.frozen_count,
                "cancelled": self.cancelled_count,
                "expired": self.expired_count,
            },
            "gate_pass_rates": self.gate_pass_rates(),
            "avg_latency_ms": self.avg_total_latency_ms(),
            "error_count": self.error_count,
            "uptime_seconds": self.uptime_seconds(),
        }

    def reset(self) -> None:
        self.total_flows = 0
        self.active_flows = 0
        self.completed_flows = 0
        self.failed_flows = 0
        self.executed_count = 0
        self.rejected_count = 0
        self.blocked_count = 0
        self.frozen_count = 0
        self.cancelled_count = 0
        self.expired_count = 0
        self.risk_metrics = GateMetrics()
        self.governance_metrics = GateMetrics()
        self.authority_metrics = GateMetrics()
        self.approval_metrics = GateMetrics()
        self._flow_latencies.clear()
        self.error_count = 0
        self.last_error = ""
        self.last_error_time = 0.0
        self.started_at = time.time()
