"""
Risk decision replay service (Commit 41 Part 1.4).

Deterministic re-evaluation of historical risk decisions:

    RiskDecisionRecord
        -> RiskDecisionContext (from context_snapshot)
        -> RiskPolicyEvaluator
        -> New RiskDecision
        -> RiskDecisionComparator
        -> RiskDecisionReplayResult (+ RiskDecisionReplayRecord)

Determinism contract
--------------------

Replay MUST NOT re-query current market / account data.  It rebuilds the
historical context from ``record.context_snapshot`` (the frozen decision-time
inputs) and re-runs the same policies, so the same inputs always produce the
same decision.

Replay is verification, never trading: it only evaluates and compares.  It
never places orders and never mutates positions, cash, or execution state.

Replay status
-------------

- ``MATCHED``    : re-evaluation completed and matched the original decision
- ``MISMATCHED`` : re-evaluation completed but the result changed
- ``FAILED``     : re-evaluation could not complete (persisted as a FAILED
                   record, and a ``RiskDecisionReplayError`` is raised)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from .context.decision_context import RiskDecisionContext
from .context_snapshot import DEFAULT_POLICY_VERSION
from .decision.decision_record import RiskDecisionRecord
from .decision.risk_decision import RiskDecision
from .decision_comparator import RiskDecisionComparator
from .evaluator.policy_evaluator import RiskPolicyEvaluator
from .policy_trace import RiskPolicyTrace
from .ports.replay_repository import RiskDecisionReplayRepository
from .replay_record import RiskDecisionReplayRecord
from .replay_result import (
    ReplayStatus,
    RiskDecisionReplayResult,
)

ReplayIdFactory = Callable[[], str]


class RiskDecisionReplayError(RuntimeError):
    """Raised when a replay cannot complete verification.

    The failed attempt is persisted as a ``FAILED`` replay record before the
    error propagates, so the verification history stays complete.
    """

    def __init__(self, decision_id: str, reason: str) -> None:
        self.decision_id = decision_id
        self.reason = reason
        super().__init__(
            f"risk decision replay failed for {decision_id}: {reason}"
        )


class RiskDecisionReplayVersionMismatchError(RiskDecisionReplayError):
    """Raised when a replay would compare across policy set versions."""

    def __init__(
        self,
        decision_id: str,
        recorded_version: str,
        replay_version: str,
    ) -> None:
        self.recorded_version = recorded_version
        self.replay_version = replay_version
        super().__init__(
            decision_id,
            "VERSION_MISMATCH: record uses "
            f"{recorded_version!r} but replay uses {replay_version!r}",
        )


class RiskDecisionReplayService:
    """Deterministically re-evaluates a historical decision record."""

    def __init__(
        self,
        evaluator: RiskPolicyEvaluator,
        *,
        comparator: RiskDecisionComparator | None = None,
        replay_repository: RiskDecisionReplayRepository | None = None,
        policy_version: str = DEFAULT_POLICY_VERSION,
        replay_id_factory: ReplayIdFactory | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._comparator = comparator or RiskDecisionComparator()
        self._replay_repository = replay_repository
        self._policy_version = policy_version
        self._replay_id_factory = replay_id_factory or (
            lambda: uuid4().hex
        )
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def replay(
        self,
        record: RiskDecisionRecord,
        *,
        policy_version: str | None = None,
    ) -> RiskDecisionReplayResult:
        """Replay ``record`` and compare it against the original decision.

        ``policy_version`` may override the version this service was
        configured with (used to replay an old decision with the *same* set
        of policies).  Passing a version that differs from the one recorded
        on ``record`` raises ``RiskDecisionReplayVersionMismatchError``
        instead of producing a misleading comparison.

        Raises:
            RiskDecisionReplayVersionMismatchError: when the replay version
                differs from the recorded policy version.
            RiskDecisionReplayError: when the replay could not complete.
        """
        replay_version = policy_version or self._policy_version
        if record.policy_version != replay_version:
            self._persist_failed(
                record,
                "VERSION_MISMATCH: recorded "
                f"{record.policy_version!r}, replaying with {replay_version!r}",
            )
            raise RiskDecisionReplayVersionMismatchError(
                record.decision_id,
                record.policy_version,
                replay_version,
            )

        try:
            context = RiskDecisionContext.from_snapshot(
                record.context_snapshot
            )
            replayed = self._evaluator.evaluate(context)
        except Exception as exc:
            self._persist_failed(record, str(exc))
            raise RiskDecisionReplayError(record.decision_id, str(exc)) from exc

        differences = self._comparator.compare(record, replayed)
        matched = not differences

        result = RiskDecisionReplayResult(
            decision_id=record.decision_id,
            original_decision=record.decision,
            replayed_decision=replayed.status.value,
            matched=matched,
            original_policy_trace=record.policy_trace,
            replayed_policy_trace=replayed.policy_trace
            or RiskPolicyTrace(evaluations=()),
            differences=differences,
        )

        if self._replay_repository is not None:
            self._replay_repository.save(
                RiskDecisionReplayRecord(
                    replay_id=self._replay_id_factory(),
                    decision_id=record.decision_id,
                    original_decision=result.original_decision,
                    replayed_decision=result.replayed_decision,
                    status=result.status,
                    matched=result.matched,
                    differences=result.differences,
                    replayed_at=self._now_provider(),
                )
            )

        return result

    def _persist_failed(
        self,
        record: RiskDecisionRecord,
        reason: str,
    ) -> None:
        """Persist a FAILED replay record so the audit trail stays complete."""
        if self._replay_repository is None:
            return
        self._replay_repository.save(
            RiskDecisionReplayRecord(
                replay_id=self._replay_id_factory(),
                decision_id=record.decision_id,
                original_decision=record.decision,
                replayed_decision=ReplayStatus.FAILED,
                status=ReplayStatus.FAILED,
                matched=False,
                differences=(f"replay failed: {reason}",),
                replayed_at=self._now_provider(),
            )
        )


__all__ = [
    "RiskDecisionReplayError",
    "RiskDecisionReplayService",
    "RiskDecisionReplayVersionMismatchError",
]
