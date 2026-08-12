"""
RecoveryOrchestrator — the coordinating heart of autonomous recovery.

Responsibilities:

    create recovery -> execute plan -> manage steps -> persist checkpoints
        -> handle failure (retry / escalate) -> verify -> request re-open

The orchestrator never mutates business state.  It asks steps to produce
:class:`RecoveryAction` requests, persists progress as checkpoints, and only
ever resumes / escalates based on deterministic policy.

Crash safety: every successful step is checkpointed, so a crashed orchestrator
can load the session and resume from the last durable checkpoint instead of
restarting from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..events.recovery_completed import RecoveryCompleted
from ..events.recovery_failed import RecoveryFailed
from ..events.recovery_started import RecoveryStarted
from ..events.recovery_step_completed import RecoveryStepCompleted
from ..events.recovery_step_started import RecoveryStepStarted
from ..events.recovery_verified import RecoveryVerified
from ..policy.policy_context import PolicyContext
from ..policy.policy_decision import PolicyDecision
from .recovery_checkpoint import RecoveryCheckpoint
from .recovery_context import RecoveryContext
from .recovery_plan import RecoveryPlan
from .recovery_result import RecoveryResult, RampUpLevel
from .recovery_state import (
    FailureClass,
    RecoveryState,
    RecoveryStateMachine,
    classify_failure,
)
from .recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# event bus
# ---------------------------------------------------------------------------


class InMemoryEventBus:
    """Minimal publish/subscribe bus (single-process, test-friendly)."""

    def __init__(self) -> None:
        self._subscribers: List[Callable[[Any], None]] = []

    def subscribe(self, fn: Callable[[Any], None]) -> Callable[[Any], None]:
        self._subscribers.append(fn)
        return fn

    def publish(self, event: Any) -> None:
        for fn in list(self._subscribers):
            fn(event)

    def clear(self) -> None:
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# ---------------------------------------------------------------------------
# retry policy
# ---------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    """Backoff policy for retryable recovery failures."""

    max_attempts: int = 3
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    timeout_seconds: float = 300.0

    def backoff_for(self, attempt: int) -> float:
        """Exponential backoff: 1s, 2s, 4s ..."""
        return self.backoff_seconds * (self.backoff_multiplier ** max(0, attempt - 1))

    def can_retry(self, attempt: int, failure_class: FailureClass) -> bool:
        """Integrity / fatal failures never auto-retry (require investigation)."""
        if failure_class in (FailureClass.INTEGRITY, FailureClass.FATAL):
            return False
        return attempt < self.max_attempts


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------


class RecoveryNotFoundError(Exception):
    """Raised when a recovery session does not exist."""


@dataclass
class RecoverySession:
    """One durable recovery session (context + plan + state)."""

    recovery_id: str
    context: RecoveryContext
    plan: RecoveryPlan
    state: RecoveryState = RecoveryState.DETECTED
    result: Optional[RecoveryResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "context": self.context.to_dict(),
            "plan": self.plan.to_dict(),
            "state": self.state.value,
            "result": self.result.to_dict() if self.result else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoverySession":
        return cls(
            recovery_id=data["recovery_id"],
            context=RecoveryContext.from_dict(data["context"]),
            plan=RecoveryPlan.from_dict(data["plan"]),
            state=RecoveryState(data.get("state", "DETECTED")),
            result=RecoveryResult.from_dict(data["result"]) if data.get("result") else None,
        )


#: Recovery state implied by each running step.
_STATE_FOR_STEP: Dict[StepType, RecoveryState] = {
    StepType.ISOLATE_TRADING: RecoveryState.ISOLATING,
    StepType.FREEZE_STATE: RecoveryState.RECOVERING,
    StepType.REPLAY_EVENTS: RecoveryState.RECOVERING,
    StepType.REBUILD_LEDGER: RecoveryState.RECOVERING,
    StepType.REBUILD_POSITION: RecoveryState.RECOVERING,
    StepType.RECONCILE_STATE: RecoveryState.RECONCILING,
    StepType.VERIFY_INTEGRITY: RecoveryState.VERIFYING,
    StepType.RESUME_TRADING: RecoveryState.RAMPING_UP,
}


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------


class RecoveryOrchestrator:
    """Coordinates a recovery session through its full lifecycle."""

    def __init__(
        self,
        strategy: Any,
        repository: Any,
        checkpoint_repository: Any,
        event_bus: Optional[InMemoryEventBus] = None,
        policy_engine: Any = None,
        retry_policy: Optional[RetryPolicy] = None,
        step_executors: Optional[Dict[StepType, Any]] = None,
    ) -> None:
        self.strategy = strategy
        self.repository = repository
        self.checkpoints = checkpoint_repository
        self.event_bus = event_bus or InMemoryEventBus()
        self.policy_engine = policy_engine
        self.retry_policy = retry_policy or RetryPolicy()
        self._executors: Dict[StepType, Any] = dict(step_executors or {})
        #: every event emitted by this orchestrator instance (audit trail)
        self.events: List[Any] = []

    # -- public entry points ----------------------------------------------

    def start(self, context: RecoveryContext) -> RecoveryResult:
        """Begin recovery for a context (idempotent per incident)."""
        existing = self.repository.find_active_by_incident(context.incident_id)
        if existing is not None:
            # #39 idempotency — never start a second concurrent recovery
            return self.resume(existing.recovery_id)

        if not context.recovery_id:
            context.recovery_id = f"REC-{self.repository.recovery_count() + 1:04d}"
        plan = self.strategy.build_plan(context)
        session = RecoverySession(
            recovery_id=context.recovery_id,
            context=context,
            plan=plan,
            state=RecoveryState.DETECTED,
        )
        self.repository.save(session)

        self._emit(
            RecoveryStarted(
                recovery_id=session.recovery_id,
                incident_id=context.incident_id,
                scope=context.scope.value,
                trigger=context.trigger,
                correlation_id=context.correlation_id,
                policy_version=context.policy_version,
            )
        )
        return self.run(session.recovery_id)

    def run(
        self, recovery_id: str, max_steps: Optional[int] = None
    ) -> RecoveryResult:
        """Advance the session until completion, failure or step budget."""
        session = self._load(recovery_id)
        executed = 0
        while True:
            if self._check_deadline(session):
                break
            step = session.plan.current_step()
            if step is None:
                break
            if max_steps is not None and executed >= max_steps:
                break

            outcome = self._execute_step(session, step)
            executed += 1
            if not outcome.success and not self._handle_failure(session, step, outcome):
                break

        return self._finalize(session)

    def resume(self, recovery_id: str) -> RecoveryResult:
        """Load an active recovery, apply its latest checkpoint, keep going."""
        session = self._load(recovery_id)
        checkpoint = self.checkpoints.latest(recovery_id)
        if checkpoint is not None:
            session.plan.resume_from(checkpoint)
        if session.state in (RecoveryState.FAILED, RecoveryState.DETECTED):
            self._set_state(session, RecoveryState.ISOLATING)
        return self.run(recovery_id)

    # -- internals --------------------------------------------------------

    def _load(self, recovery_id: str) -> RecoverySession:
        session = self.repository.get(recovery_id)
        if session is None:
            raise RecoveryNotFoundError(f"recovery {recovery_id!r} not found")
        return session

    def _set_state(self, session: RecoverySession, state: RecoveryState) -> None:
        if session.state is state:
            return
        RecoveryStateMachine.assert_transition(session.state, state)
        session.state = state

    def _execute_step(
        self, session: RecoverySession, step: RecoveryStep, now: Optional[datetime] = None
    ) -> StepOutcome:
        now = now or _utcnow()
        step.mark_running(now)
        self._set_state(session, _STATE_FOR_STEP[step.step_type])
        self._emit(
            RecoveryStepStarted(
                recovery_id=session.recovery_id,
                step_id=step.step_id,
                step_type=step.step_type.value,
                attempt=step.attempt + 1,
                correlation_id=session.context.correlation_id,
            )
        )

        executor = self._executors.get(step.step_type)
        if executor is None:
            from ..recovery_steps import get_step_executor

            executor = get_step_executor(step.step_type)
        outcome = executor.execute(step, session.context)

        if outcome.success:
            step.mark_completed(outcome.output, now)
            session.context.step_outputs[step.step_id] = dict(outcome.output)
            self._emit(
                RecoveryStepCompleted(
                    recovery_id=session.recovery_id,
                    step_id=step.step_id,
                    step_type=step.step_type.value,
                    attempt=step.attempt + 1,
                    output=outcome.output,
                    correlation_id=session.context.correlation_id,
                )
            )
            if not self._post_step(session, step, outcome):
                # verify / policy gates failed after the step ran
                error = step.error or "STEP_POST_FAILED"
                error_code = step.error_code or "STEP_FAILED"
                return StepOutcome(success=False, error=error, error_code=error_code)
            # durable checkpoint after every truly successful step
            self.checkpoints.save(
                RecoveryCheckpoint.from_step(session.recovery_id, step, outcome.output)
            )
        else:
            step.mark_failed(outcome.error or outcome.error_code, now, outcome.error_code)
        return outcome

    def _post_step(
        self, session: RecoverySession, step: RecoveryStep, outcome: StepOutcome
    ) -> bool:
        """Post-success gates.  Returns False when the step must be treated as
        failed (integrity verification rejected, policy refused re-open)."""
        if step.step_type is StepType.ISOLATE_TRADING:
            # #7 isolation complete -> baseline is frozen
            self._set_state(session, RecoveryState.ISOLATED)
            return True
        if step.step_type is StepType.VERIFY_INTEGRITY:
            verified = bool(outcome.output.get("verified"))
            self._emit(
                RecoveryVerified(
                    recovery_id=session.recovery_id,
                    verified=verified,
                    checks=dict(outcome.output.get("checks", {})),
                    correlation_id=session.context.correlation_id,
                )
            )
            if not verified:
                step.mark_failed(
                    "INTEGRITY_VERIFICATION_FAILED",
                    step.completed_at,
                    "INTEGRITY_VERIFICATION_FAILED",
                )
                return False
            return True
        if step.step_type is StepType.RESUME_TRADING:
            if not self._confirm_resume(session):
                # #35 policy must agree before trading can reopen
                step.mark_failed(
                    "POLICY_REJECTED_RESUME", step.completed_at, "POLICY_REJECTED_RESUME"
                )
                return False
        return True

    def _handle_failure(
        self, session: RecoverySession, step: RecoveryStep, outcome: StepOutcome
    ) -> bool:
        """Decide retry vs escalate.  Returns True when the step will retry."""
        failure_class = classify_failure(outcome.error, outcome.error_code)
        step.attempt += 1
        session.context.attempt = max(session.context.attempt, step.attempt)
        can_retry = self.retry_policy.can_retry(step.attempt, failure_class)

        self._emit(
            RecoveryFailed(
                recovery_id=session.recovery_id,
                step_id=step.step_id,
                error=outcome.error_message,
                failure_class=failure_class.value,
                retryable=can_retry,
                escalated=not can_retry,
                correlation_id=session.context.correlation_id,
            )
        )

        if can_retry:
            # #17 / #28 transient failures may retry (attempted next loop)
            step.reset()
            self._set_state(session, _STATE_FOR_STEP[step.step_type])
            return True
        self._escalate(session)
        return False

    def _escalate(self, session: RecoverySession) -> None:
        """#24/#27 — unrecoverable: keep trading halted, escalate to humans."""
        try:
            self._set_state(session, RecoveryState.ESCALATED)
        except Exception:
            session.state = RecoveryState.ESCALATED

    def _check_deadline(self, session: RecoverySession) -> bool:
        """#26 — a recovery must never run forever."""
        if session.context.deadline is None:
            return False
        if _utcnow() <= session.context.deadline:
            return False
        self._emit(
            RecoveryFailed(
                recovery_id=session.recovery_id,
                step_id=session.plan.current_step().step_id
                if session.plan.current_step()
                else "",
                error="RECOVERY_DEADLINE_EXCEEDED",
                failure_class=FailureClass.FATAL.value,
                retryable=False,
                escalated=True,
                correlation_id=session.context.correlation_id,
            )
        )
        session.state = RecoveryState.ESCALATED
        return True

    def _confirm_resume(self, session: RecoverySession) -> bool:
        """#35/#43 — only the policy engine decides that trading may reopen."""
        if self.policy_engine is None:
            return True
        policy_context = PolicyContext(
            system_state=session.context.system_state,
            trading_state=session.context.trading_state,
            risk_health=session.context.risk_state,
            position_health=session.context.position_state,
            ledger_health=session.context.ledger_state,
            correlation_id=session.context.correlation_id,
        )
        decision = self.policy_engine.decision_for(
            policy_context, correlation_id=session.context.correlation_id
        )
        return decision is PolicyDecision.ALLOW

    def _finalize(self, session: RecoverySession) -> RecoveryResult:
        if session.plan.is_complete():
            try:
                self._set_state(session, RecoveryState.COMPLETED)
            except Exception:
                session.state = RecoveryState.COMPLETED
            self._emit(
                RecoveryCompleted(
                    recovery_id=session.recovery_id,
                    ramp_up_level=_extract_ramp_up_level(session),
                    correlation_id=session.context.correlation_id,
                )
            )
            message = "recovery completed and verified"
        elif session.state is RecoveryState.ESCALATED:
            message = "recovery escalated for human intervention"
        else:
            message = "recovery in progress"

        failed = session.plan.failed_step()
        errors = (
            [f"{failed.step_id}: {failed.error}"] if failed and failed.error else []
        )
        if session.state is RecoveryState.ESCALATED and not errors:
            errors = ["recovery escalated"]

        result = RecoveryResult(
            recovery_id=session.recovery_id,
            state=session.state,
            verified=_is_verified(session),
            ramp_up_level=_extract_ramp_up_level(session),
            message=message,
            errors=errors,
            actions=_collect_actions(session),
            attempt=session.context.attempt,
            started_at=session.context.started_at,
            completed_at=_utcnow() if session.state.is_terminal else None,
            correlation_id=session.context.correlation_id,
        )
        session.result = result
        self.repository.save(session)
        return result

    def _emit(self, event: Any) -> None:
        self.events.append(event)
        self.event_bus.publish(event)


def _extract_ramp_up_level(session: RecoverySession) -> RampUpLevel:
    for step in session.plan.steps:
        if step.step_type is StepType.RESUME_TRADING and step.output.get("ramp_up_level"):
            try:
                return RampUpLevel(step.output["ramp_up_level"])
            except ValueError:
                return RampUpLevel.LEVEL_1
    return RampUpLevel.LEVEL_0


def _is_verified(session: RecoverySession) -> bool:
    for step in session.plan.steps:
        if step.step_type is StepType.VERIFY_INTEGRITY and step.is_done:
            return bool(step.output.get("verified"))
    return False


def _collect_actions(session: RecoverySession) -> List[RecoveryAction]:
    actions: List[RecoveryAction] = []
    for step in session.plan.steps:
        for action in _actions_from_step(step):
            actions.append(action)
    return actions


def _actions_from_step(step: RecoveryStep) -> List[RecoveryAction]:
    if step.step_type is StepType.ISOLATE_TRADING and step.is_done:
        return [RecoveryAction(action="ISOLATE_TRADING", target=step.input.get("scope", ""), detail="trading isolated")]
    if step.step_type is StepType.FREEZE_STATE and step.is_done:
        return [RecoveryAction(action="FREEZE_STATE", target=step.input.get("target", ""), detail="state frozen")]
    if step.step_type is StepType.RESUME_TRADING and step.is_done:
        return [RecoveryAction(action="RESUME_TRADING", target="TRADING", detail=step.output.get("ramp_up_level", "LEVEL_1"))]
    return []


__all__ = [
    "RecoveryOrchestrator",
    "RecoverySession",
    "RecoveryNotFoundError",
    "RetryPolicy",
    "InMemoryEventBus",
]
