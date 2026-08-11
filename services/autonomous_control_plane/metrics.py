"""
Control Plane Metrics — Prometheus-compatible metrics for the Control Plane.

Tracks all governance metrics: decisions, policy evaluations, autonomy,
budget, model lifecycle, approvals, permissions, audit, incidents, and health.
"""

from __future__ import annotations

import threading
from typing import Any


class Metrics:
    """
    Metrics registry for the Autonomous Control Plane.

    Tracks all governance metrics defined in the ICYQuant spec:
    decisions, policy evaluations, autonomy transitions, budget consumption,
    model lifecycle events, approval rates, and incident counts.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Counter operations
    # ------------------------------------------------------------------

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    # ------------------------------------------------------------------
    # Gauge operations
    # ------------------------------------------------------------------

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    # ------------------------------------------------------------------
    # Predefined metrics
    # ------------------------------------------------------------------

    def record_decision(self, outcome: str) -> None:
        self.inc("icyquant_control_plane_decisions_total")
        if outcome == "denied":
            self.inc("icyquant_control_plane_denials_total")
        elif outcome == "deferred":
            self.inc("icyquant_control_plane_deferred_total")

    def record_policy_evaluation(self, violation: bool = False, conflict: bool = False) -> None:
        self.inc("icyquant_policy_evaluations_total")
        if violation:
            self.inc("icyquant_policy_violations_total")
        if conflict:
            self.inc("icyquant_policy_conflicts_total")

    def record_autonomy_transition(self) -> None:
        self.inc("icyquant_autonomy_transitions_total")

    def record_autonomy_guard_block(self) -> None:
        self.inc("icyquant_autonomy_guard_blocks_total")

    def record_budget_consumed(self, budget_type: str, amount: float) -> None:
        self.inc(f"icyquant_{budget_type}_budget_used")

    def record_model_event(self, event: str) -> None:
        self.inc(f"icyquant_model_{event}_total")

    def record_approval(self, approved: bool, override: bool = False) -> None:
        self.inc("icyquant_approval_requests_total")
        if not approved:
            self.inc("icyquant_approval_rejections_total")
        if override:
            self.inc("icyquant_human_overrides_total")

    def record_incident(self, severity: str) -> None:
        self.inc("icyquant_incidents_total")

    def record_circuit_breaker(self) -> None:
        self.inc("icyquant_circuit_breaker_events_total")

    def record_kill_switch(self) -> None:
        self.inc("icyquant_kill_switch_events_total")

    def set_autonomy_level(self, level: int) -> None:
        self.set_gauge("icyquant_autonomy_level", float(level))

    def set_system_health(self, score: float) -> None:
        self.set_gauge("icyquant_system_health_score", score)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    def stats(self) -> dict:
        return self.snapshot()
