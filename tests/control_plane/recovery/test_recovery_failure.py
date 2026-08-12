"""Unit tests: recovery failure handling (retry / escalate / deadline)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.events.recovery_failed import RecoveryFailed
from services.control_plane.recovery.recovery_context import (
    RecoveryContext,
    RecoveryScope,
)
from services.control_plane.recovery.recovery_orchestrator import (
    RecoveryOrchestrator,
    RetryPolicy,
)
from services.control_plane.recovery.recovery_state import (
    FailureClass,
    RecoveryState,
)
from services.control_plane.recovery.recovery_step import (
    StepOutcome,
    StepType,
)
from services.control_plane.recovery.recovery_strategy import PositionRecoveryStrategy
from services.control_plane.recovery_steps import StepExecutor
from services.control_plane.repositories.recovery_checkpoint_repository import (
    RecoveryCheckpointRepository,
)
from services.control_plane.repositories.recovery_repository import RecoveryRepository


class _FlakyExecutor(StepExecutor):
    """Fails once with a transient error, then succeeds."""

    step_type = StepType.REPLAY_EVENTS

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, step, context):
        self.calls += 1
        if self.calls == 1:
            return StepOutcome(
                success=False,
                error="connection to event store timed out",
                error_code="CONNECTION_TIMEOUT",
            )
        return StepOutcome(
            success=True,
            output={"event_cursor": 100, "replayed_events": 100, "complete": True},
        )


class _AlwaysFailExecutor(StepExecutor):
    """Always fails with a transient error."""

    step_type = StepType.REPLAY_EVENTS

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, step, context):
        self.calls += 1
        return StepOutcome(
            success=False,
            error="temporary database timeout",
            error_code="DB_TIMEOUT",
        )


class _IntegrityFailExecutor(StepExecutor):
    """Fails with an integrity error (event gap)."""

    step_type = StepType.REPLAY_EVENTS

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, step, context):
        self.calls += 1
        return StepOutcome(
            success=False,
            error="EVENT_GAP: missing event 102",
            error_code="EVENT_GAP",
        )


def _context(**overrides) -> RecoveryContext:
    defaults = {
        "recovery_id": "REC-1",
        "incident_id": "INC-1",
        "trigger": "position-integrity",
        "scope": RecoveryScope.STRATEGY,
        "system_state": SystemState.DEGRADED,
        "trading_state": TradingState.TRADING_READY,
        "risk_state": ComponentState.HEALTHY,
        "position_state": ComponentState.UNHEALTHY,
        "ledger_state": ComponentState.HEALTHY,
        "correlation_id": "CORR-1",
    }
    defaults.update(overrides)
    return RecoveryContext(**defaults)


def _orchestrator(**overrides):
    kwargs = {
        "strategy": PositionRecoveryStrategy(),
        "repository": RecoveryRepository(),
        "checkpoint_repository": RecoveryCheckpointRepository(),
    }
    kwargs.update(overrides)
    return RecoveryOrchestrator(**kwargs)


class TestRetryPolicy:
    def test_exponential_backoff(self):
        policy = RetryPolicy(
            max_attempts=3, backoff_seconds=1.0, backoff_multiplier=2.0
        )
        assert policy.backoff_for(1) == 1.0
        assert policy.backoff_for(2) == 2.0
        assert policy.backoff_for(3) == 4.0

    def test_transient_failures_retry_within_budget(self):
        policy = RetryPolicy(max_attempts=3)
        assert policy.can_retry(1, FailureClass.TRANSIENT)
        assert policy.can_retry(2, FailureClass.TRANSIENT)
        assert not policy.can_retry(3, FailureClass.TRANSIENT)

    def test_integrity_failures_never_retry(self):
        policy = RetryPolicy(max_attempts=10)
        assert not policy.can_retry(1, FailureClass.INTEGRITY)
        assert not policy.can_retry(1, FailureClass.FATAL)


class TestTransientRetry:
    def test_transient_failure_retries_and_completes(self):
        flaky = _FlakyExecutor()
        orchestrator = _orchestrator(step_executors={StepType.REPLAY_EVENTS: flaky})
        result = orchestrator.start(_context())

        assert result.success
        assert flaky.calls == 2
        assert orchestrator.checkpoints.checkpoint_count() == 8

        failed_events = [
            e for e in orchestrator.events if isinstance(e, RecoveryFailed)
        ]
        assert len(failed_events) == 1
        assert failed_events[0].retryable is True
        assert failed_events[0].failure_class == "TRANSIENT"

        replay_starts = [
            e
            for e in orchestrator.events
            if e.event_type == "RECOVERY_STEP_STARTED"
            and e.step_id == "REPLAY_EVENTS"
        ]
        assert len(replay_starts) == 2


class TestEscalation:
    def test_exhausted_retries_escalate(self):
        always_fail = _AlwaysFailExecutor()
        orchestrator = _orchestrator(
            step_executors={StepType.REPLAY_EVENTS: always_fail},
            retry_policy=RetryPolicy(max_attempts=2),
        )
        result = orchestrator.start(_context())

        assert result.state is RecoveryState.ESCALATED
        assert result.escalated
        assert always_fail.calls == 2
        assert result.errors

        failed_events = [
            e for e in orchestrator.events if isinstance(e, RecoveryFailed)
        ]
        assert len(failed_events) == 2
        assert failed_events[-1].escalated is True
        # trading stays halted — recovery never auto-reopens
        assert result.actions  # isolation still requested

    def test_integrity_failure_escalates_immediately(self):
        integrity = _IntegrityFailExecutor()
        orchestrator = _orchestrator(
            step_executors={StepType.REPLAY_EVENTS: integrity},
            retry_policy=RetryPolicy(max_attempts=5),
        )
        result = orchestrator.start(_context())

        assert result.state is RecoveryState.ESCALATED
        assert integrity.calls == 1
        failed_events = [
            e for e in orchestrator.events if isinstance(e, RecoveryFailed)
        ]
        assert failed_events[0].failure_class == "INTEGRITY"
        assert failed_events[0].retryable is False

    def test_deadline_exceeded_escalates(self):
        past_deadline = datetime.now(timezone.utc) - timedelta(seconds=30)
        orchestrator = _orchestrator()
        result = orchestrator.start(_context(deadline=past_deadline))

        assert result.state is RecoveryState.ESCALATED
        failed_events = [
            e for e in orchestrator.events if isinstance(e, RecoveryFailed)
        ]
        assert any("DEADLINE" in e.error for e in failed_events)
        # no recovery step ever ran after the deadline
        assert orchestrator.checkpoints.checkpoint_count() == 0
