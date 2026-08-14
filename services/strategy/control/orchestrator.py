"""Strategy lifecycle orchestrator.

The control plane *approves* execution; the lifecycle orchestrator makes
sure the strategy control state and the runtime state converge::

    StrategyCommand
        |
        v
    Validate
        |
        v
    Transition (CAS into intermediate state, e.g. PAUSING)
        |
        v
    Runtime Action (runtime.pause / start / ...)
        |
        v
    Observe Runtime
        |
        v
    Commit State (PAUSED / FAILED / ...)

A ``START`` may be accepted by the control plane but still fail at the
runtime; the orchestrator must not pretend the strategy is ``RUNNING``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from services.strategy.control.commands import (
    KILL,
    PAUSE,
    RESUME,
    START,
    STOP,
    StrategyCommand,
)
from services.strategy.control.policies import target_state
from services.strategy.control.state_store import StrategyStateStore
from services.strategy.control.synchronization import (
    StrategyRuntimeSynchronizer,
)
from services.strategy.control.transition import StrategyTransition
from services.strategy.control.validator import StrategyControlValidator
from services.strategy.runtime.adapter import (
    RuntimeActionError,
    StrategyRuntimeAdapter,
)
from services.strategy.runtime.state import (
    HEALTHY_STATES,
    RuntimeState,
)

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

EVENTS: dict[str, str] = {
    "start_intermediate": "STRATEGY_STARTING",
    "start_completed": "STRATEGY_STARTED",
    "start_failed": "STRATEGY_START_FAILED",
    "pause_intermediate": "STRATEGY_PAUSING",
    "pause_completed": "STRATEGY_PAUSED",
    "pause_failed": "STRATEGY_PAUSE_FAILED",
    "resume_intermediate": "STRATEGY_RESUMING",
    "resume_completed": "STRATEGY_RESUMED",
    "resume_failed": "STRATEGY_RESUME_FAILED",
    "stop_intermediate": "STRATEGY_STOPPING",
    "stop_completed": "STRATEGY_STOPPED",
    "stop_failed": "STRATEGY_STOP_FAILED",
    "kill_completed": "STRATEGY_KILLED",
    "kill_failed": "STRATEGY_KILL_FAILED",
    "runtime_degraded": "STRATEGY_RUNTIME_DEGRADED",
    "runtime_unknown": "STRATEGY_RUNTIME_UNKNOWN",
    "recovery_required": "STRATEGY_RECOVERY_REQUIRED",
    "reconciled": "STRATEGY_RECONCILED",
}

_INTERMEDIATE_EVENT_BY_ACTION: dict[str, str | None] = {
    START: EVENTS["start_intermediate"],
    PAUSE: EVENTS["pause_intermediate"],
    RESUME: EVENTS["resume_intermediate"],
    STOP: EVENTS["stop_intermediate"],
    # KILL jumps straight to the terminal event; there is no intermediate.
    KILL: None,
}

_FINAL_EVENT_BY_ACTION: dict[tuple[str, bool], str] = {
    (START, True): EVENTS["start_completed"],
    (START, False): EVENTS["start_failed"],
    (PAUSE, True): EVENTS["pause_completed"],
    (PAUSE, False): EVENTS["pause_failed"],
    (RESUME, True): EVENTS["resume_completed"],
    (RESUME, False): EVENTS["resume_failed"],
    (STOP, True): EVENTS["stop_completed"],
    (STOP, False): EVENTS["stop_failed"],
    (KILL, True): EVENTS["kill_completed"],
    (KILL, False): EVENTS["kill_failed"],
}


class EventBus(Protocol):
    """Publishes lifecycle events to the wider platform."""

    def publish(self, event: str, payload: dict[str, Any]) -> None:  # pragma: no cover
        ...


@dataclass(frozen=True)
class OrchestrationResult:
    """Outcome of executing a control command through the orchestrator.

    ``state`` is the *final* control state (``PAUSED`` after a successful
    pause) as opposed to the intermediate state returned by the boundary.
    """

    strategy_id: str
    command_id: str
    action: str
    state: str
    runtime_state: str
    success: bool
    reason: str | None = None
    transition: StrategyTransition | None = None


@dataclass
class StrategyLifecycleMetrics:
    """Lifecycle counters and timings (see spec Commit 30 Part 1.2)."""

    commands_total: int = 0
    commands_failed_total: int = 0

    starts_total: int = 0
    pauses_total: int = 0
    resumes_total: int = 0
    stops_total: int = 0
    kills_total: int = 0

    runtime_unknown_total: int = 0
    runtime_degraded_total: int = 0

    recovery_total: int = 0
    reconciliation_total: int = 0

    runtime_availability: float = 1.0
    runtime_unknown_duration: float = 0.0

    startup_duration_seconds: float | None = None
    pause_duration_seconds: float | None = None
    shutdown_duration_seconds: float | None = None


class StrategyLifecycleOrchestrator:
    """Drives one strategy control command to completion at the runtime."""

    def __init__(
        self,
        runtime: StrategyRuntimeAdapter,
        state_store: StrategyStateStore,
        event_bus: EventBus,
        validator: StrategyControlValidator,
        synchronizer: StrategyRuntimeSynchronizer | None = None,
        metrics: StrategyLifecycleMetrics | None = None,
    ) -> None:
        self.runtime = runtime
        self.state_store = state_store
        self.event_bus = event_bus
        self.validator = validator
        self.synchronizer = synchronizer or StrategyRuntimeSynchronizer()
        self.metrics = metrics or StrategyLifecycleMetrics()

    # -- command execution --------------------------------------------------

    def execute(self, command: StrategyCommand) -> OrchestrationResult:
        self.metrics.commands_total += 1
        strategy_id = command.strategy_id
        action = command.action
        previous = self.state_store.get(strategy_id)

        # 1. Validate against the state machine.
        try:
            self.validator.validate(previous, action)
        except ValueError as exc:
            self.metrics.commands_failed_total += 1
            return OrchestrationResult(
                strategy_id=strategy_id,
                command_id=command.command_id,
                action=action,
                state=previous,
                runtime_state=self._observe_runtime(strategy_id),
                success=False,
                reason=str(exc),
            )

        # 2. CAS into the intermediate state (e.g. RUNNING -> PAUSING).
        intermediate = target_state(action)
        if not self.state_store.transition(
            strategy_id, previous, intermediate
        ):
            self.metrics.commands_failed_total += 1
            actual = self.state_store.get(strategy_id)
            return OrchestrationResult(
                strategy_id=strategy_id,
                command_id=command.command_id,
                action=action,
                state=actual,
                runtime_state=self._observe_runtime(strategy_id),
                success=False,
                reason=(
                    f"concurrent transition rejected: "
                    f"expected {previous}, actual {actual}"
                ),
            )

        transition = StrategyTransition(
            strategy_id=strategy_id,
            command_id=command.command_id,
            from_state=previous,
            to_state=intermediate,
            action=action,
        )
        self._emit(
            self._intermediate_event(action),
            self._payload(command, previous, intermediate, None),
        )
        started_at = time.monotonic()

        # 3. Execute the runtime action.
        try:
            runtime_state = self._apply_runtime(action, strategy_id)
        except RuntimeActionError as exc:
            final = "FAILED"
            self.state_store.transition(strategy_id, intermediate, final)
            self._finish_metrics(action, success=False)
            self._emit(
                self._final_event(action, success=False),
                self._payload(command, previous, final, "FAILED"),
            )
            return OrchestrationResult(
                strategy_id=strategy_id,
                command_id=command.command_id,
                action=action,
                state=final,
                runtime_state="FAILED",
                success=False,
                reason=str(exc),
                transition=transition,
            )

        # 4. Observe runtime and commit the final state.
        self._record_runtime_metrics(runtime_state)
        final = self._final_state(action, runtime_state)
        self.state_store.transition(strategy_id, intermediate, final)
        self._finish_metrics(
            action,
            success=final != "FAILED",
            duration=time.monotonic() - started_at,
        )
        self._emit(
            self._final_event(action, final != "FAILED"),
            self._payload(command, previous, final, runtime_state),
        )
        return OrchestrationResult(
            strategy_id=strategy_id,
            command_id=command.command_id,
            action=action,
            state=final,
            runtime_state=runtime_state,
            success=final != "FAILED",
            transition=transition,
        )

    # -- reconciliation -----------------------------------------------------

    def reconcile(self, strategy_id: str):
        """Reconcile control state with the observed runtime state."""
        control = self.state_store.get(strategy_id)
        runtime_state = self.runtime.get_state(strategy_id)

        result = self.synchronizer.reconcile(
            control, runtime_state, strategy_id
        )
        self.metrics.reconciliation_total += 1

        payload: dict[str, Any] = {
            "strategy_id": strategy_id,
            "control_state": control,
            "runtime_state": runtime_state,
            "runtime_id": getattr(self.runtime, "runtime_id", None),
        }
        if runtime_state == RuntimeState.UNKNOWN.value:
            self.metrics.runtime_unknown_total += 1
            self._emit(EVENTS["runtime_unknown"], payload)
        elif runtime_state == RuntimeState.DEGRADED.value:
            self.metrics.runtime_degraded_total += 1
            self._emit(EVENTS["runtime_degraded"], payload)

        if result.status in (
            "RECOVERY_REQUIRED",
            "CRITICAL",
        ):
            self.metrics.recovery_total += 1
            self._emit(EVENTS["recovery_required"], payload)
        else:
            self._emit(EVENTS["reconciled"], payload)

        return result

    # -- helpers ------------------------------------------------------------

    def _apply_runtime(self, action: str, strategy_id: str) -> str:
        if action == START:
            self.runtime.start(strategy_id)
        elif action == PAUSE:
            self.runtime.pause(strategy_id)
        elif action == RESUME:
            if not self.runtime.can_resume(strategy_id):
                raise RuntimeActionError("resume preconditions not met")
            self.runtime.resume(strategy_id)
        elif action == STOP:
            self.runtime.stop(strategy_id)
        elif action == KILL:
            self.runtime.kill(strategy_id)
        return self.runtime.get_state(strategy_id)

    def _final_state(self, action: str, runtime_state: str) -> str:
        if action == START:
            return (
                "RUNNING"
                if runtime_state in HEALTHY_STATES
                else "FAILED"
            )
        if action == PAUSE:
            # Pausing only disables signal generation; the runtime process
            # legitimately stays RUNNING/HEALTHY while paused.
            return (
                "PAUSED"
                if runtime_state
                not in {
                    RuntimeState.UNKNOWN.value,
                    RuntimeState.FAILED.value,
                }
                else "FAILED"
            )
        if action == RESUME:
            return (
                "RUNNING"
                if runtime_state in HEALTHY_STATES
                else "FAILED"
            )
        if action == STOP:
            return (
                "STOPPED"
                if runtime_state
                in {
                    RuntimeState.STOPPED.value,
                    RuntimeState.STOPPING.value,
                    RuntimeState.FAILED.value,
                }
                else "FAILED"
            )
        if action == KILL:
            # KILL is terminal regardless of what the runtime reports now;
            # a still-alive runtime will surface as CRITICAL in the
            # synchronizer and trigger an emergency runtime kill.
            return "KILLED"
        raise ValueError(f"unknown control action: {action}")

    def _observe_runtime(self, strategy_id: str) -> str:
        try:
            return self.runtime.get_state(strategy_id)
        except Exception:
            return RuntimeState.UNKNOWN.value

    def _record_runtime_metrics(self, runtime_state: str) -> None:
        if runtime_state == RuntimeState.UNKNOWN.value:
            self.metrics.runtime_unknown_total += 1
        elif runtime_state == RuntimeState.DEGRADED.value:
            self.metrics.runtime_degraded_total += 1

    def _finish_metrics(
        self,
        action: str,
        success: bool,
        duration: float | None = None,
    ) -> None:
        if not success:
            self.metrics.commands_failed_total += 1
            return
        counter_by_action = {
            START: "starts_total",
            PAUSE: "pauses_total",
            RESUME: "resumes_total",
            STOP: "stops_total",
            KILL: "kills_total",
        }
        counter = counter_by_action[action]
        setattr(self.metrics, counter, getattr(self.metrics, counter) + 1)
        if duration is None:
            return
        if action == START:
            self.metrics.startup_duration_seconds = duration
        elif action == PAUSE:
            self.metrics.pause_duration_seconds = duration
        elif action == STOP:
            self.metrics.shutdown_duration_seconds = duration

    def _payload(
        self,
        command: StrategyCommand,
        previous: str,
        new: str,
        runtime_state: str | None,
    ) -> dict[str, Any]:
        return {
            "strategy_id": command.strategy_id,
            "command_id": command.command_id,
            "action": command.action,
            "principal_id": command.principal_id,
            "previous_state": previous,
            "new_state": new,
            "runtime_state": runtime_state,
            "runtime_id": getattr(self.runtime, "runtime_id", None),
            "correlation_id": command.correlation_id,
        }

    def _intermediate_event(self, action: str) -> str | None:
        return _INTERMEDIATE_EVENT_BY_ACTION.get(action)

    def _final_event(self, action: str, success: bool) -> str:
        return _FINAL_EVENT_BY_ACTION[(action, success)]

    def _emit(self, event: str | None, payload: dict[str, Any]) -> None:
        if event is None:
            return
        self.event_bus.publish(event, payload)
