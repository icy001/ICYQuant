"""Execution timeout and retry policies (Commit 29 Part 1.3 §14, §27-29).

Different control commands carry different timeout policies (``trading:pause``
10s vs ``ledger:repair`` 300s) and different retry policies. By default an
UNKNOWN execution outcome is never automatically retried — high-risk commands
(``trading:kill``, ``ledger:repair``, ``position:rebuild``) must go through
reconciliation first (§16, §27-29).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ExecutionTimeout:
    """Per-command execution timeout policy (§14)."""

    timeout_seconds: int
    retryable: bool

    def is_expired(self, started_at: datetime, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return (now - started_at).total_seconds() >= self.timeout_seconds


@dataclass(frozen=True)
class RetryPolicy:
    """Command retry policy (§28).

    ``allow_unknown_retry`` defaults to ``False``: a command whose execution
    outcome is UNKNOWN is never blindly retried — the operator must reconcile
    with the target first (§16, §27).
    """

    max_attempts: int
    retryable_errors: tuple[str, ...] = ()
    allow_unknown_retry: bool = False

    def is_retryable(self, error_code: str | None) -> bool:
        if error_code is None:
            return self.allow_unknown_retry
        return error_code in self.retryable_errors

    def can_retry(self, attempt_number: int, error_code: str | None = None) -> bool:
        if attempt_number >= self.max_attempts:
            return False
        return self.is_retryable(error_code)
