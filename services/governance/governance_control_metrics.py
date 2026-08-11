"""
Governance Control Metrics — metrics for the autonomous control plane.

Part 1.5: provides metrics tracking for the control plane, guardians,
controllers, interventions, and emergency actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SimpleMetric:
    """Simple metric wrapper (no external dependency)."""

    def __init__(self, initial: float = 0.0):
        self._value: float = initial

    @property
    def value(self) -> float:
        return self._value

    def inc(self, delta: float = 1.0) -> None:
        self._value += delta

    def set(self, value: float) -> None:
        self._value = value


@dataclass
class ControlMetrics:
    """Metrics for the autonomous governance control plane.

    Part 1.5 metrics:
      - State transitions, signals, breaches
      - Interventions, freezes, reductions
      - Authority revocations, escalations
      - Emergency events, recovery
      - Watchdog failures, control loop latency
    """

    # State transitions
    governance_state_transitions_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_signals_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_breaches_total: SimpleMetric = field(default_factory=SimpleMetric)

    # Interventions
    governance_interventions_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_intervention_failures_total: SimpleMetric = field(default_factory=SimpleMetric)

    # Specific actions
    governance_freezes_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_exposure_reductions_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_authority_revocations_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_escalations_total: SimpleMetric = field(default_factory=SimpleMetric)

    # Emergency
    governance_emergency_events_total: SimpleMetric = field(default_factory=SimpleMetric)
    governance_recovery_total: SimpleMetric = field(default_factory=SimpleMetric)

    # Watchdog
    governance_watchdog_failures_total: SimpleMetric = field(default_factory=SimpleMetric)

    # Latency (in milliseconds)
    governance_control_loop_latency: SimpleMetric = field(default_factory=SimpleMetric)
    governance_recovery_latency: SimpleMetric = field(default_factory=SimpleMetric)

    def record_state_transition(self) -> None:
        self.governance_state_transitions_total.inc()

    def record_signal(self) -> None:
        self.governance_signals_total.inc()

    def record_breach(self) -> None:
        self.governance_breaches_total.inc()

    def record_intervention(self, success: bool = True) -> None:
        self.governance_interventions_total.inc()
        if not success:
            self.governance_intervention_failures_total.inc()

    def record_freeze(self) -> None:
        self.governance_freezes_total.inc()

    def record_exposure_reduction(self) -> None:
        self.governance_exposure_reductions_total.inc()

    def record_authority_revocation(self) -> None:
        self.governance_authority_revocations_total.inc()

    def record_escalation(self) -> None:
        self.governance_escalations_total.inc()

    def record_emergency_event(self) -> None:
        self.governance_emergency_events_total.inc()

    def record_recovery(self) -> None:
        self.governance_recovery_total.inc()

    def record_watchdog_failure(self) -> None:
        self.governance_watchdog_failures_total.inc()

    def set_control_loop_latency_ms(self, ms: float) -> None:
        self.governance_control_loop_latency.set(ms)

    def set_recovery_latency_ms(self, ms: float) -> None:
        self.governance_recovery_latency.set(ms)

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all metrics."""
        return {
            "state": {
                "transitions": self.governance_state_transitions_total.value,
            },
            "signals": {
                "total": self.governance_signals_total.value,
                "breaches": self.governance_breaches_total.value,
            },
            "interventions": {
                "total": self.governance_interventions_total.value,
                "failures": self.governance_intervention_failures_total.value,
            },
            "actions": {
                "freezes": self.governance_freezes_total.value,
                "exposure_reductions": self.governance_exposure_reductions_total.value,
                "authority_revocations": self.governance_authority_revocations_total.value,
                "escalations": self.governance_escalations_total.value,
            },
            "emergency": {
                "events": self.governance_emergency_events_total.value,
                "recoveries": self.governance_recovery_total.value,
            },
            "watchdog": {
                "failures": self.governance_watchdog_failures_total.value,
            },
            "latency": {
                "control_loop_ms": self.governance_control_loop_latency.value,
                "recovery_ms": self.governance_recovery_latency.value,
            },
        }
