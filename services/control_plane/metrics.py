"""Control Plane metrics (Commit 29 Part 1.5 §19-24).

Counters are deliberately split so an AUTHORIZATION_REJECTED command is never
counted as an execution failure (§20):

    submitted / authorized / rejected / executed / succeeded / failed

Derived rates used by alerting and diagnostics (§23-24):

    success_rate   = succeeded / submitted
    timeout_rate   = timeouts  / executed
    recovery_rate  = recoveries / submitted
    duplicate_rate = duplicates / submitted
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class ControlMetricsSnapshot:
    """Point-in-time metric counters and derived rates (§19)."""

    submitted: int = 0
    authorized: int = 0
    rejected: int = 0
    executed: int = 0
    succeeded: int = 0
    failed: int = 0
    timeouts: int = 0
    recoveries: int = 0
    recovery_success: int = 0
    recovery_failure: int = 0
    duplicates: int = 0
    idempotency_conflicts: int = 0
    replay_rejections: int = 0
    claim_conflicts: int = 0
    version_conflicts: int = 0
    execution_attempts: int = 0
    command_durations: tuple[float, ...] = ()
    execution_durations: tuple[float, ...] = ()

    @property
    def success_rate(self) -> float:
        if self.submitted == 0:
            return 0.0
        return self.succeeded / self.submitted

    @property
    def timeout_rate(self) -> float:
        if self.executed == 0:
            return 0.0
        return self.timeouts / self.executed

    @property
    def recovery_rate(self) -> float:
        if self.submitted == 0:
            return 0.0
        return self.recoveries / self.submitted

    @property
    def duplicate_rate(self) -> float:
        if self.submitted == 0:
            return 0.0
        return self.duplicates / self.submitted

    @property
    def idempotency_conflict_rate(self) -> float:
        if self.submitted == 0:
            return 0.0
        return self.idempotency_conflicts / self.submitted

    def percentile(self, values: Sequence[float], p: float) -> float:
        """Nearest-rank percentile (§21)."""
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1))
        return ordered[index]

    @property
    def command_latency_p50(self) -> float:
        return self.percentile(self.command_durations, 0.50)

    @property
    def command_latency_p95(self) -> float:
        return self.percentile(self.command_durations, 0.95)

    @property
    def command_latency_p99(self) -> float:
        return self.percentile(self.command_durations, 0.99)

    @property
    def execution_latency_p95(self) -> float:
        return self.percentile(self.execution_durations, 0.95)


class ControlMetrics:
    """In-memory metrics collector with derived rates (§19-24)."""

    def __init__(self) -> None:
        self._submitted = 0
        self._authorized = 0
        self._rejected = 0
        self._executed = 0
        self._succeeded = 0
        self._failed = 0
        self._timeouts = 0
        self._recoveries = 0
        self._recovery_success = 0
        self._recovery_failure = 0
        self._duplicates = 0
        self._idempotency_conflicts = 0
        self._replay_rejections = 0
        self._claim_conflicts = 0
        self._version_conflicts = 0
        self._execution_attempts = 0
        self._command_durations: list[float] = []
        self._execution_durations: list[float] = []

    # --- counters ---

    def record_submitted(self) -> None:
        self._submitted += 1

    def record_authorized(self) -> None:
        self._authorized += 1

    def record_rejected(self) -> None:
        self._rejected += 1

    def record_executed(self) -> None:
        self._executed += 1
        self._execution_attempts += 1

    def record_succeeded(self, duration_seconds: float | None = None) -> None:
        self._succeeded += 1
        if duration_seconds is not None:
            self._command_durations.append(duration_seconds)

    def record_failed(self) -> None:
        self._failed += 1

    def record_timeout(self) -> None:
        self._timeouts += 1

    def record_recovery(self) -> None:
        self._recoveries += 1

    def record_recovery_success(self) -> None:
        self._recovery_success += 1

    def record_recovery_failure(self) -> None:
        self._recovery_failure += 1

    def record_duplicate(self) -> None:
        self._duplicates += 1

    def record_idempotency_conflict(self) -> None:
        self._idempotency_conflicts += 1

    def record_replay_rejection(self) -> None:
        self._replay_rejections += 1

    def record_claim_conflict(self) -> None:
        self._claim_conflicts += 1

    def record_version_conflict(self) -> None:
        self._version_conflicts += 1

    def record_execution_duration(self, seconds: float) -> None:
        self._execution_durations.append(seconds)

    # --- snapshot & rates ---

    def snapshot(self) -> ControlMetricsSnapshot:
        return ControlMetricsSnapshot(
            submitted=self._submitted,
            authorized=self._authorized,
            rejected=self._rejected,
            executed=self._executed,
            succeeded=self._succeeded,
            failed=self._failed,
            timeouts=self._timeouts,
            recoveries=self._recoveries,
            recovery_success=self._recovery_success,
            recovery_failure=self._recovery_failure,
            duplicates=self._duplicates,
            idempotency_conflicts=self._idempotency_conflicts,
            replay_rejections=self._replay_rejections,
            claim_conflicts=self._claim_conflicts,
            version_conflicts=self._version_conflicts,
            execution_attempts=self._execution_attempts,
            command_durations=tuple(self._command_durations),
            execution_durations=tuple(self._execution_durations),
        )

    def success_rate(self) -> float:
        return self.snapshot().success_rate

    def timeout_rate(self) -> float:
        return self.snapshot().timeout_rate

    def recovery_rate(self) -> float:
        return self.snapshot().recovery_rate

    def duplicate_rate(self) -> float:
        return self.snapshot().duplicate_rate

    def command_latency_p95(self) -> float:
        return self.snapshot().command_latency_p95
