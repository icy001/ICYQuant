"""Operational telemetry: retry-storm detection and the operational snapshot
(Commit 29 Part 1.5 §25, §40).

    RetryStormDetector  - flags retry loops from the duplicate ratio (§25)
    ControlPlaneTelemetry - assembles the CONTROL PLANE SNAPSHOT (§40)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .alerts import Alert, AlertRule, AlertSeverity, ControlAlertEvaluator
from .control_health import ControlPlaneHealth
from .diagnostics import DiagnosticsSnapshot, ControlPlaneDiagnostics
from .metrics import ControlMetrics, ControlMetricsSnapshot


class RetryStormDetector:
    """Detects client retry storms from the recent duplicate ratio (§25).

    ``window_size`` is the number of recent requests kept; ``threshold`` is
    the duplicate ratio that turns the window into a storm. A storm produces
    an alert instead of silently accepting unlimited retries.
    """

    def __init__(self, window_size: int = 100, threshold: float = 0.5) -> None:
        self._window: deque[bool] = deque(maxlen=window_size)
        self._threshold = threshold

    def record(self, is_duplicate: bool) -> bool:
        """Record one request; returns ``True`` when this makes it a storm."""
        self._window.append(is_duplicate)
        return self.is_storm()

    def duplicate_rate(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def is_storm(self) -> bool:
        """True when the duplicate ratio in the window crosses the threshold."""
        return self.duplicate_rate() >= self._threshold and len(self._window) > 0

    @property
    def window_size(self) -> int:
        return self._window.maxlen or 0


@dataclass(frozen=True)
class OperationalSnapshot:
    """The CONTROL PLANE SNAPSHOT (§40)."""

    active_commands: int = 0
    executing_commands: int = 0
    unknown_commands: int = 0
    recovery_commands: int = 0
    failed_commands: int = 0
    success_rate: float = 0.0
    timeout_rate: float = 0.0
    duplicate_rate: float = 0.0
    idempotency_conflict_rate: float = 0.0
    active_claims: int = 0
    expired_claims: int = 0
    claim_conflicts: int = 0
    retry_storm: bool = False
    command_latency_p95: float = 0.0


class ControlPlaneTelemetry:
    """Aggregates diagnostics, metrics, health and alerts (§40, §25)."""

    def __init__(
        self,
        *,
        diagnostics: ControlPlaneDiagnostics,
        metrics: ControlMetrics,
        health: ControlPlaneHealth,
        alerts: ControlAlertEvaluator,
        retry_storm: RetryStormDetector | None = None,
    ) -> None:
        self.diagnostics = diagnostics
        self.metrics = metrics
        self.health = health
        self.alerts = alerts
        self.retry_storm = retry_storm or RetryStormDetector()

    def record_request(self, is_duplicate: bool) -> bool:
        """Feed one incoming request into the storm detector (§25)."""
        return self.retry_storm.record(is_duplicate)

    def snapshot(self) -> OperationalSnapshot:
        diag = self.diagnostics.snapshot()
        metrics = self.metrics.snapshot()
        return OperationalSnapshot(
            active_commands=diag.active_commands,
            executing_commands=diag.executing_commands,
            unknown_commands=diag.unknown_commands,
            recovery_commands=diag.recovery_commands,
            failed_commands=diag.failed_commands,
            success_rate=metrics.success_rate,
            timeout_rate=metrics.timeout_rate,
            duplicate_rate=metrics.duplicate_rate,
            idempotency_conflict_rate=metrics.idempotency_conflict_rate,
            active_claims=diag.active_claims,
            expired_claims=diag.expired_claims,
            claim_conflicts=metrics.claim_conflicts,
            retry_storm=self.retry_storm.is_storm(),
            command_latency_p95=metrics.command_latency_p95,
        )

    def evaluate_alerts(self) -> tuple[Alert, ...]:
        """Evaluate metric rules plus the audit-integrity rule (§26, §46)."""
        alerts: list[Alert] = list(self.alerts.evaluate_metrics(self.metrics.snapshot()))
        if self.retry_storm.is_storm():
            alerts.append(
                Alert(
                    rule=AlertRule.DUPLICATE_RATE_HIGH,
                    severity=AlertSeverity.CRITICAL,
                    message="Retry storm detected: duplicate ratio is above threshold",
                    context={
                        "duplicate_rate": self.retry_storm.duplicate_rate(),
                        "window_size": self.retry_storm.window_size,
                    },
                )
            )
        return tuple(alerts)
