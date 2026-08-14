"""Tests for the strategy lifecycle orchestrator."""

from __future__ import annotations

from services.strategy.control.commands import StrategyCommand
from services.strategy.control.orchestrator import (
    EVENTS,
    OrchestrationResult,
    StrategyLifecycleOrchestrator,
)
from services.strategy.control.state_store import InMemoryStrategyStateStore
from services.strategy.control.validator import StrategyControlValidator
from services.strategy.runtime.adapter import RuntimeActionError


class FakeRuntime:
    """A scriptable runtime used to exercise the orchestrator."""

    runtime_id = "RUNTIME-001"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.states: dict[str, str] = {}
        self.fail_start = False
        self.resume_allowed = True

    def start(self, strategy_id: str) -> None:
        self.calls.append("start")
        if self.fail_start:
            raise RuntimeActionError("start failed at runtime")
        self.states[strategy_id] = "READY"

    def pause(self, strategy_id: str) -> None:
        self.calls.append("pause")
        # Pausing only disables signal generation; the process state is
        # intentionally left untouched.

    def resume(self, strategy_id: str) -> None:
        self.calls.append("resume")
        self.states[strategy_id] = "RUNNING"

    def can_resume(self, strategy_id: str) -> bool:
        self.calls.append("can_resume")
        return self.resume_allowed

    def stop(self, strategy_id: str) -> None:
        self.calls.append("stop")
        self.states[strategy_id] = "STOPPED"

    def kill(self, strategy_id: str) -> None:
        self.calls.append("kill")
        self.states[strategy_id] = "STOPPED"

    def get_state(self, strategy_id: str) -> str:
        return self.states.get(strategy_id, "STOPPED")

    def assert_started(self) -> None:
        assert "start" in self.calls

    def assert_paused(self) -> None:
        assert "pause" in self.calls


class FakeEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))

    @property
    def names(self) -> list[str]:
        return [event for event, _ in self.events]


class BlockingStateStore(InMemoryStrategyStateStore):
    """A state store whose CAS always fails to simulate lost updates."""

    def transition(
        self, strategy_id: str, expected_state: str, new_state: str
    ) -> bool:
        return False


def make_command(action: str = "pause", **overrides: object) -> StrategyCommand:
    defaults: dict[str, object] = {
        "command_id": "CMD-001",
        "strategy_id": "STRAT-001",
        "action": action,
        "principal_id": "operator-001",
        "parameters": {},
        "correlation_id": "CORR-001",
        "idempotency_key": "IDEMP-001",
    }
    defaults.update(overrides)
    return StrategyCommand(**defaults)


def make_orchestrator(
    store: InMemoryStrategyStateStore | None = None,
    runtime: FakeRuntime | None = None,
    bus: FakeEventBus | None = None,
) -> tuple[StrategyLifecycleOrchestrator, FakeRuntime, FakeEventBus]:
    runtime = runtime or FakeRuntime()
    bus = bus or FakeEventBus()
    orchestrator = StrategyLifecycleOrchestrator(
        runtime=runtime,
        state_store=store or InMemoryStrategyStateStore(),
        event_bus=bus,
        validator=StrategyControlValidator(),
    )
    return orchestrator, runtime, bus


class TestStart:
    def test_start_strategy(self) -> None:
        orchestrator, runtime, _ = make_orchestrator()

        result = orchestrator.execute(make_command(action="start"))

        assert isinstance(result, OrchestrationResult)
        assert result.state == "RUNNING"
        assert result.success is True
        runtime.assert_started()
        assert runtime.states["STRAT-001"] == "READY"

    def test_start_requires_stopped(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, runtime, _ = make_orchestrator(store=store)

        result = orchestrator.execute(make_command(action="start"))

        assert result.success is False
        assert result.state == "RUNNING"
        assert "start" not in runtime.calls


class TestStartFailure:
    def test_start_failure(self) -> None:
        runtime = FakeRuntime()
        runtime.fail_start = True
        orchestrator, _, _ = make_orchestrator(runtime=runtime)

        result = orchestrator.execute(make_command(action="start"))

        assert result.state == "FAILED"
        assert result.success is False
        assert "start" in runtime.calls

    def test_start_failure_never_reports_running(self) -> None:
        runtime = FakeRuntime()
        runtime.fail_start = True
        orchestrator, _, _ = make_orchestrator(runtime=runtime)

        result = orchestrator.execute(make_command(action="start"))

        assert result.state != "RUNNING"
        assert result.state == "FAILED"


class TestPause:
    def test_pause_strategy(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, runtime, _ = make_orchestrator(store=store)

        result = orchestrator.execute(make_command(action="pause"))

        assert result.state == "PAUSED"
        assert result.success is True
        runtime.assert_paused()

    def test_pause_is_rejected_from_stopped(self) -> None:
        orchestrator, runtime, _ = make_orchestrator()

        result = orchestrator.execute(make_command(action="pause"))

        assert result.success is False
        assert result.state == "STOPPED"
        assert "pause" not in runtime.calls

    def test_pause_failure_when_runtime_unknown(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        runtime = FakeRuntime()
        runtime.states["STRAT-001"] = "UNKNOWN"
        orchestrator, _, _ = make_orchestrator(store=store, runtime=runtime)

        result = orchestrator.execute(make_command(action="pause"))

        assert result.state == "FAILED"
        assert result.success is False


class TestResume:
    def test_resume_strategy(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "PAUSED")
        orchestrator, runtime, _ = make_orchestrator(store=store)

        result = orchestrator.execute(make_command(action="resume"))

        assert result.state == "RUNNING"
        assert result.success is True
        assert "resume" in runtime.calls

    def test_resume_precondition_failure(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "PAUSED")
        runtime = FakeRuntime()
        runtime.resume_allowed = False
        orchestrator, _, _ = make_orchestrator(store=store, runtime=runtime)

        result = orchestrator.execute(make_command(action="resume"))

        assert result.state == "FAILED"
        assert result.success is False


class TestStop:
    def test_stop_strategy(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, runtime, _ = make_orchestrator(store=store)

        result = orchestrator.execute(make_command(action="stop"))

        assert result.state == "STOPPED"
        assert result.success is True
        assert "stop" in runtime.calls


class TestKill:
    def test_kill_is_terminal_regardless_of_runtime(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, runtime, _ = make_orchestrator(store=store)

        result = orchestrator.execute(make_command(action="kill"))

        assert result.state == "KILLED"
        assert result.success is True
        assert "kill" in runtime.calls

    def test_kill_from_any_active_state(self) -> None:
        for state in ("STOPPED", "RUNNING", "PAUSING", "PAUSED", "STOPPING"):
            store = InMemoryStrategyStateStore()
            store.set("STRAT-001", state)
            orchestrator, runtime, _ = make_orchestrator(store=store)

            result = orchestrator.execute(make_command(action="kill"))

            assert result.state == "KILLED"
            assert result.success is True
            assert "kill" in runtime.calls


class TestConcurrentTransition:
    def test_concurrent_transition_is_safe(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")

        first = store.transition("STRAT-001", "RUNNING", "PAUSING")
        second = store.transition("STRAT-001", "RUNNING", "STOPPING")

        assert first is True
        assert second is False

    def test_orchestrator_rejects_lost_update(self) -> None:
        store = BlockingStateStore()
        store.set("STRAT-001", "RUNNING")
        runtime = FakeRuntime()
        orchestrator, _, _ = make_orchestrator(
            store=store,
            runtime=runtime,
        )

        result = orchestrator.execute(make_command(action="pause"))

        assert result.success is False
        assert "concurrent" in (result.reason or "")
        assert "pause" not in runtime.calls


class TestEvents:
    def test_pause_emits_intermediate_and_final_events(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, _, bus = make_orchestrator(store=store)

        orchestrator.execute(make_command(action="pause"))

        assert EVENTS["pause_intermediate"] in bus.names
        assert EVENTS["pause_completed"] in bus.names

    def test_start_failure_emits_start_failed_event(self) -> None:
        runtime = FakeRuntime()
        runtime.fail_start = True
        orchestrator, _, bus = make_orchestrator(runtime=runtime)

        orchestrator.execute(make_command(action="start"))

        assert EVENTS["start_failed"] in bus.names
        assert EVENTS["start_completed"] not in bus.names

    def test_event_payload_carries_audit_fields(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        runtime = FakeRuntime()
        runtime.states["STRAT-001"] = "RUNNING"
        orchestrator, _, bus = make_orchestrator(
            store=store,
            runtime=runtime,
        )

        orchestrator.execute(make_command(action="pause"))

        _, payload = [
            event for event in bus.events
            if event[0] == EVENTS["pause_completed"]
        ][0]
        assert payload["strategy_id"] == "STRAT-001"
        assert payload["command_id"] == "CMD-001"
        assert payload["action"] == "pause"
        assert payload["principal_id"] == "operator-001"
        assert payload["previous_state"] == "RUNNING"
        assert payload["new_state"] == "PAUSED"
        assert payload["runtime_state"] == "RUNNING"
        assert payload["runtime_id"] == "RUNTIME-001"
        assert payload["correlation_id"] == "CORR-001"


class TestMetrics:
    def test_commands_are_counted(self) -> None:
        orchestrator, _, _ = make_orchestrator()

        orchestrator.execute(make_command(action="start"))

        assert orchestrator.metrics.commands_total == 1
        assert orchestrator.metrics.starts_total == 1

    def test_failed_commands_are_counted(self) -> None:
        runtime = FakeRuntime()
        runtime.fail_start = True
        orchestrator, _, _ = make_orchestrator(runtime=runtime)

        orchestrator.execute(make_command(action="start"))

        assert orchestrator.metrics.commands_failed_total == 1
        assert orchestrator.metrics.starts_total == 0

    def test_pause_and_stop_are_counted(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, _, _ = make_orchestrator(store=store)

        orchestrator.execute(make_command(action="pause"))
        orchestrator.execute(make_command(action="stop"))

        assert orchestrator.metrics.pauses_total == 1
        assert orchestrator.metrics.stops_total == 1
        assert orchestrator.metrics.commands_total == 2

    def test_lifecycle_durations_are_recorded(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        orchestrator, _, _ = make_orchestrator(store=store)

        orchestrator.execute(make_command(action="pause"))

        assert orchestrator.metrics.pause_duration_seconds is not None


class TestReconciliation:
    def test_reconcile_requires_recovery_for_unknown_runtime(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        runtime = FakeRuntime()
        runtime.states["STRAT-001"] = "UNKNOWN"
        orchestrator, _, bus = make_orchestrator(store=store, runtime=runtime)

        result = orchestrator.reconcile("STRAT-001")

        assert result.status == "RECOVERY_REQUIRED"
        assert orchestrator.metrics.recovery_total == 1
        assert orchestrator.metrics.reconciliation_total == 1
        assert EVENTS["runtime_unknown"] in bus.names
        assert EVENTS["recovery_required"] in bus.names

    def test_reconcile_is_healthy_for_matching_states(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        runtime = FakeRuntime()
        runtime.states["STRAT-001"] = "RUNNING"
        orchestrator, _, bus = make_orchestrator(store=store, runtime=runtime)

        result = orchestrator.reconcile("STRAT-001")

        assert result.status == "HEALTHY"
        assert orchestrator.metrics.recovery_total == 0
        assert EVENTS["reconciled"] in bus.names

    def test_reconcile_detects_killed_but_running_as_critical(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "KILLED")
        runtime = FakeRuntime()
        runtime.states["STRAT-001"] = "RUNNING"
        orchestrator, _, _ = make_orchestrator(store=store, runtime=runtime)

        result = orchestrator.reconcile("STRAT-001")

        assert result.status == "CRITICAL"
        assert orchestrator.metrics.recovery_total == 1
