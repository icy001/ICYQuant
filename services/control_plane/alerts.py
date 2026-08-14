"""Control Plane alert rules and evaluation (Commit 29 Part 1.5 §26-28, §46).

Alert rules cover operational signals:

    COMMAND_FAILURE_RATE_HIGH        COMMAND_TIMEOUT_RATE_HIGH
    RECOVERY_RATE_HIGH               DUPLICATE_RATE_HIGH
    IDEMPOTENCY_CONFLICT_SPIKE       REPLAY_REJECTION_SPIKE
    CLAIM_CONFLICT_SPIKE             VERSION_CONFLICT_SPIKE

High-risk commands (trading:kill, order:cancel_all, ledger:repair,
position:rebuild) escalate immediately when they land in a dangerous state.
An AUDIT_INTEGRITY_FAILURE is always CRITICAL (§46).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .metrics import ControlMetricsSnapshot


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertRule(str, Enum):
    COMMAND_FAILURE_RATE_HIGH = "COMMAND_FAILURE_RATE_HIGH"
    COMMAND_TIMEOUT_RATE_HIGH = "COMMAND_TIMEOUT_RATE_HIGH"
    RECOVERY_RATE_HIGH = "RECOVERY_RATE_HIGH"
    DUPLICATE_RATE_HIGH = "DUPLICATE_RATE_HIGH"
    IDEMPOTENCY_CONFLICT_SPIKE = "IDEMPOTENCY_CONFLICT_SPIKE"
    REPLAY_REJECTION_SPIKE = "REPLAY_REJECTION_SPIKE"
    CLAIM_CONFLICT_SPIKE = "CLAIM_CONFLICT_SPIKE"
    VERSION_CONFLICT_SPIKE = "VERSION_CONFLICT_SPIKE"
    HIGH_RISK_COMMAND_FAILURE = "HIGH_RISK_COMMAND_FAILURE"
    AUDIT_INTEGRITY_FAILURE = "AUDIT_INTEGRITY_FAILURE"


# High-risk control actions (§27): never blind-retried, always escalate.
HIGH_RISK_ACTIONS = frozenset(
    {
        "trading:kill",
        "order:cancel_all",
        "ledger:repair",
        "position:rebuild",
    }
)

# Dangerous terminal/in-flight states for a high-risk command (§27).
HIGH_RISK_STATES = frozenset(
    {
        "FAILED",
        "UNKNOWN",
        "RECOVERY_REQUIRED",
    }
)


@dataclass(frozen=True)
class Alert:
    """A single alert with operational context (§28)."""

    rule: str
    severity: AlertSeverity
    message: str
    command_id: str | None = None
    correlation_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


DEFAULT_THRESHOLDS: dict[str, float] = {
    "failure_rate": 0.05,
    "timeout_rate": 0.05,
    "recovery_rate": 0.05,
    "duplicate_rate": 0.20,
    "idempotency_conflict": 10,
    "replay_rejection": 10,
    "claim_conflict": 10,
    "version_conflict": 10,
}


class ControlAlertEvaluator:
    """Evaluates metrics / command outcomes / audit integrity into alerts (§26)."""

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def evaluate_metrics(self, snapshot: ControlMetricsSnapshot) -> tuple[Alert, ...]:
        """Rate/spike based alerts from a metrics snapshot (§26)."""
        alerts: list[Alert] = []
        context = {
            "success_rate": snapshot.success_rate,
            "timeout_rate": snapshot.timeout_rate,
            "recovery_rate": snapshot.recovery_rate,
            "duplicate_rate": snapshot.duplicate_rate,
        }

        if snapshot.failed > 0 and snapshot.failed / max(snapshot.submitted, 1) >= self.thresholds["failure_rate"]:
            alerts.append(
                Alert(
                    rule=AlertRule.COMMAND_FAILURE_RATE_HIGH,
                    severity=AlertSeverity.HIGH,
                    message="Control command failure rate is above threshold",
                    context={"failed": snapshot.failed, **context},
                )
            )
        if snapshot.timeout_rate >= self.thresholds["timeout_rate"]:
            alerts.append(
                Alert(
                    rule=AlertRule.COMMAND_TIMEOUT_RATE_HIGH,
                    severity=AlertSeverity.WARNING,
                    message="Control command timeout rate is above threshold",
                    context={"timeouts": snapshot.timeouts, **context},
                )
            )
        if snapshot.recovery_rate >= self.thresholds["recovery_rate"]:
            alerts.append(
                Alert(
                    rule=AlertRule.RECOVERY_RATE_HIGH,
                    severity=AlertSeverity.WARNING,
                    message="Recovery rate is above threshold - target communication may be degraded",
                    context={"recoveries": snapshot.recoveries, **context},
                )
            )
        if snapshot.duplicate_rate >= self.thresholds["duplicate_rate"]:
            alerts.append(
                Alert(
                    rule=AlertRule.DUPLICATE_RATE_HIGH,
                    severity=AlertSeverity.WARNING,
                    message="Duplicate rate is high - possible client timeout or retry storm",
                    context={"duplicates": snapshot.duplicates, **context},
                )
            )
        if snapshot.idempotency_conflicts >= self.thresholds["idempotency_conflict"]:
            alerts.append(
                Alert(
                    rule=AlertRule.IDEMPOTENCY_CONFLICT_SPIKE,
                    severity=AlertSeverity.WARNING,
                    message="Idempotency conflict spike",
                    context={"idempotency_conflicts": snapshot.idempotency_conflicts},
                )
            )
        if snapshot.replay_rejections >= self.thresholds["replay_rejection"]:
            alerts.append(
                Alert(
                    rule=AlertRule.REPLAY_REJECTION_SPIKE,
                    severity=AlertSeverity.WARNING,
                    message="Replay rejection spike",
                    context={"replay_rejections": snapshot.replay_rejections},
                )
            )
        if snapshot.claim_conflicts >= self.thresholds["claim_conflict"]:
            alerts.append(
                Alert(
                    rule=AlertRule.CLAIM_CONFLICT_SPIKE,
                    severity=AlertSeverity.WARNING,
                    message="Execution claim conflict spike",
                    context={"claim_conflicts": snapshot.claim_conflicts},
                )
            )
        if snapshot.version_conflicts >= self.thresholds["version_conflict"]:
            alerts.append(
                Alert(
                    rule=AlertRule.VERSION_CONFLICT_SPIKE,
                    severity=AlertSeverity.WARNING,
                    message="Optimistic-concurrency version conflict spike",
                    context={"version_conflicts": snapshot.version_conflicts},
                )
            )
        return tuple(alerts)

    def evaluate_command(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        principal: str | None = None,
        attempt: int | None = None,
        state: str,
        error: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """High-risk command escalation when it lands in a dangerous state (§27-28)."""
        if action in HIGH_RISK_ACTIONS and state in HIGH_RISK_STATES:
            return (
                Alert(
                    rule=AlertRule.HIGH_RISK_COMMAND_FAILURE,
                    severity=AlertSeverity.HIGH,
                    message=f"High-risk control command {action} reached {state}",
                    command_id=command_id,
                    correlation_id=correlation_id,
                    context={
                        "command_id": command_id,
                        "action": action,
                        "target": target,
                        "principal": principal,
                        "attempt": attempt,
                        "state": state,
                        "error": error,
                        "correlation_id": correlation_id,
                    },
                ),
            )
        return ()

    def evaluate_audit_integrity(self, verified: bool) -> Alert | None:
        """Audit chain tampering is always CRITICAL (§46)."""
        if not verified:
            return Alert(
                rule=AlertRule.AUDIT_INTEGRITY_FAILURE,
                severity=AlertSeverity.CRITICAL,
                message="Audit evidence chain integrity check failed",
                context={"verified": False},
            )
        return None
