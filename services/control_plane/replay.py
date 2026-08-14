"""Replay protection — old requests must not re-enter execution (Commit 29 Part 1.4 §28-31).

Idempotency answers *"the same request submitted twice"*; replay protection
answers *"an old request pulled out and re-executed"* (§30). They are
complementary and must never be conflated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

COMPLETED_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


@dataclass(frozen=True)
class ReplayPolicy:
    """How old a submission may be before it is rejected (§29)."""

    max_age_seconds: int
    allow_completed_replay: bool = True


@dataclass(frozen=True)
class ReplayDecision:
    """Whether a submission may proceed (§30)."""

    allowed: bool
    reason: str = ""
    error_code: str | None = None


class ReplayProtector:
    """Rejects old requests before they reach the pipeline (§28-29)."""

    def __init__(self, policy: ReplayPolicy | None = None) -> None:
        self.policy = policy or ReplayPolicy(max_age_seconds=300)

    def check(
        self,
        submitted_at: datetime,
        *,
        now: datetime | None = None,
    ) -> ReplayDecision:
        """Window check: a request older than ``max_age_seconds`` is rejected."""
        reference = now or datetime.now(timezone.utc)
        age = (reference - submitted_at).total_seconds()
        if age > self.policy.max_age_seconds:
            return ReplayDecision(
                allowed=False,
                error_code="REPLAY_REJECTED",
                reason=(
                    f"request is {age:.0f}s old; replay window is "
                    f"{self.policy.max_age_seconds}s"
                ),
            )
        return ReplayDecision(
            allowed=True,
            reason="request is within the replay window",
        )

    def check_command(self, command: Any) -> ReplayDecision:
        """Completed-command replay gate based on a command object (§31)."""
        return self.check_command_state(getattr(command, "state", ""))

    def check_command_state(self, state: str) -> ReplayDecision:
        """Completed-command replay gate based on lifecycle state (§31).

        A completed command is never re-executed; when
        ``allow_completed_replay`` is False even returning its historical
        result is refused.
        """
        if state in COMPLETED_STATES and not self.policy.allow_completed_replay:
            return ReplayDecision(
                allowed=False,
                error_code="REPLAY_REJECTED",
                reason="completed command replay is disabled by policy",
            )
        return ReplayDecision(
            allowed=True,
            reason="command replay allowed by policy",
        )


__all__ = ["ReplayDecision", "ReplayPolicy", "ReplayProtector"]
