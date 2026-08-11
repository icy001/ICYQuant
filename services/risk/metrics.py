"""
Risk Metrics — Prometheus-compatible metrics for the Risk Platform.

Tracks risk requests, evaluations, runtime latency, policy updates,
snapshot events, and recovery operations.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskPlatformMetrics:
    """
    Prometheus-style metrics for the Risk Management Platform.

    Metrics:
        icyquant_risk_requests_total
        icyquant_risk_evaluations_total
        icyquant_risk_runtime_latency
        icyquant_risk_policy_updates
        icyquant_risk_snapshot_total
        icyquant_risk_recovery_total
    """

    REQUESTS_TOTAL = "icyquant_risk_requests_total"
    EVALUATIONS_TOTAL = "icyquant_risk_evaluations_total"
    RUNTIME_LATENCY = "icyquant_risk_runtime_latency"
    POLICY_UPDATES = "icyquant_risk_policy_updates"
    SNAPSHOT_TOTAL = "icyquant_risk_snapshot_total"
    RECOVERY_TOTAL = "icyquant_risk_recovery_total"
    APPROVALS_TOTAL = "icyquant_risk_approvals_total"
    REJECTIONS_TOTAL = "icyquant_risk_rejections_total"

    def __init__(self) -> None:
        self._counters: dict[str, float] = {
            self.REQUESTS_TOTAL: 0,
            self.EVALUATIONS_TOTAL: 0,
            self.POLICY_UPDATES: 0,
            self.SNAPSHOT_TOTAL: 0,
            self.RECOVERY_TOTAL: 0,
            self.APPROVALS_TOTAL: 0,
            self.REJECTIONS_TOTAL: 0,
        }
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    # ---- Counters ----

    def increment(self, name: str, amount: float = 1.0) -> None:
        if name in self._counters:
            self._counters[name] += amount

    def record_request(self) -> None:
        self.increment(self.REQUESTS_TOTAL)

    def record_evaluation(self) -> None:
        self.increment(self.EVALUATIONS_TOTAL)

    def record_approval(self) -> None:
        self.increment(self.APPROVALS_TOTAL)

    def record_rejection(self) -> None:
        self.increment(self.REJECTIONS_TOTAL)

    def record_policy_update(self) -> None:
        self.increment(self.POLICY_UPDATES)

    def record_snapshot(self) -> None:
        self.increment(self.SNAPSHOT_TOTAL)

    def record_recovery(self) -> None:
        self.increment(self.RECOVERY_TOTAL)

    # ---- Gauges ----

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # ---- Histograms ----

    def observe_latency(self, name: str, value_ms: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value_ms)
        if len(self._histograms[name]) > 10000:
            self._histograms[name] = self._histograms[name][-10000:]

    def record_runtime_latency(self, latency_ms: float) -> None:
        self.observe_latency(self.RUNTIME_LATENCY, latency_ms)

    def get_histogram_stats(self, name: str) -> Optional[dict[str, float]]:
        values = self._histograms.get(name, [])
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.5)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[-1],
        }

    # ---- Snapshot ----

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {name: self.get_histogram_stats(name) for name in self._histograms},
        }

    def reset(self) -> None:
        for key in self._counters:
            self._counters[key] = 0
        self._gauges.clear()
        self._histograms.clear()
        logger.info("Risk platform metrics reset.")
