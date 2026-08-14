"""Tests for the strategy execution readiness gate."""

from typing import Any, Mapping

from services.strategy.readiness import READINESS_EVENTS
from services.strategy.readiness.checks import CheckResult, ReadinessCheck
from services.strategy.readiness.gate import (
    ReadinessCache,
    ReadinessTracker,
    StrategyExecutionReadinessGate,
    can_execute,
)
from services.strategy.readiness.policy import ReadinessPolicy
from services.strategy.readiness.result import ReadinessResult
from services.strategy.readiness.state import ReadinessContext
from services.strategy.runtime.readiness_adapter import (
    RuntimeReadinessAdapter,
    snapshot_to_context,
)


def healthy_context(**overrides) -> ReadinessContext:
    fields = {
        "strategy_id": "STRAT-001",
        "control_state": "RUNNING",
        "runtime_state": "RUNNING",
        "market_data_state": "FRESH",
        "configuration_state": "VALID",
        "risk_state": "ALLOWED",
        "execution_state": "CONNECTED",
        "timestamp": 1000.0,
        "evaluation_id": "READINESS-20260813-000001",
    }
    fields.update(overrides)
    return ReadinessContext(**fields)


def make_gate(**policy) -> StrategyExecutionReadinessGate:
    return StrategyExecutionReadinessGate(policy=ReadinessPolicy(**policy))


def make_result(**overrides) -> ReadinessResult:
    fields = {
        "strategy_id": "STRAT-001",
        "state": "BLOCKED",
        "ready": False,
        "reasons": ("risk",),
        "checked_at": 1000.0,
    }
    fields.update(overrides)
    return ReadinessResult(**fields)


# --- Gate aggregation -----------------------------------------------------


def test_strategy_is_ready_when_all_checks_pass() -> None:
    result = make_gate().evaluate(healthy_context())
    assert result.ready is True
    assert result.state == "READY"
    assert result.reasons == ()


def test_runtime_failure_blocks_execution() -> None:
    result = make_gate().evaluate(
        healthy_context(runtime_state="STOPPED")
    )
    assert result.ready is False
    assert result.state == "BLOCKED"
    assert "runtime" in result.reasons


def test_risk_block_has_priority() -> None:
    result = make_gate().evaluate(healthy_context(risk_state="BLOCKED"))
    assert result.state == "BLOCKED"
    assert "risk" in result.reasons


def test_risk_block_dominates_other_failures() -> None:
    result = make_gate().evaluate(
        healthy_context(
            risk_state="BLOCKED",
            market_data_state="STALE",
            execution_state="DISCONNECTED",
        )
    )
    assert result.state == "BLOCKED"
    assert result.ready is False
    assert "risk" in result.reasons


def test_stale_market_data_blocks_strategy() -> None:
    result = make_gate().evaluate(
        healthy_context(market_data_state="STALE")
    )
    assert result.ready is False
    assert result.state == "BLOCKED"
    assert "market_data" in result.reasons


def test_invalid_configuration_blocks_execution() -> None:
    result = make_gate().evaluate(
        healthy_context(configuration_state="INVALID")
    )
    assert result.ready is False
    assert result.state == "BLOCKED"


def test_execution_disconnect_blocks_strategy() -> None:
    result = make_gate().evaluate(
        healthy_context(execution_state="DISCONNECTED")
    )
    assert result.state == "BLOCKED"
    assert "execution" in result.reasons


def test_lifecycle_paused_is_not_ready() -> None:
    result = make_gate().evaluate(healthy_context(control_state="PAUSED"))
    assert result.ready is False
    assert result.state == "BLOCKED"
    assert "lifecycle" in result.reasons


def test_unknown_runtime_is_not_ready() -> None:
    result = make_gate().evaluate(healthy_context(runtime_state="UNKNOWN"))
    assert result.ready is False
    assert result.state == "BLOCKED"


# --- Policy ---------------------------------------------------------------


def test_policy_can_disable_risk_gate() -> None:
    gate = make_gate(require_risk=False)
    result = gate.evaluate(healthy_context(risk_state="BLOCKED"))
    assert result.ready is True
    assert result.state == "READY"


def test_policy_can_disable_market_data_gate() -> None:
    gate = make_gate(require_market_data=False)
    result = gate.evaluate(healthy_context(market_data_state="STALE"))
    assert result.ready is True
    assert result.state == "READY"


class SecondaryDataCheck(ReadinessCheck):
    """A soft gate: a failure merely degrades the strategy."""

    name = "secondary_data"

    def check(self, context: ReadinessContext) -> CheckResult:
        return CheckResult(
            passed=context.market_data_state != "SECONDARY_STALE",
            hard=False,
            reasons=(),
        )


def test_soft_failure_only_degrades() -> None:
    gate = StrategyExecutionReadinessGate(
        checks=(SecondaryDataCheck(),),
        policy=ReadinessPolicy(),
    )
    result = gate.evaluate(
        healthy_context(market_data_state="SECONDARY_STALE")
    )
    assert result.state == "DEGRADED"
    assert result.ready is False
    assert "secondary_data" in result.reasons


def test_allow_degraded_policy_still_degrades_but_executes() -> None:
    gate = StrategyExecutionReadinessGate(
        checks=(SecondaryDataCheck(),),
        policy=ReadinessPolicy(allow_degraded=True),
    )
    result = gate.evaluate(
        healthy_context(market_data_state="SECONDARY_STALE")
    )
    assert result.state == "DEGRADED"
    assert result.ready is True
    assert can_execute(result) is True


class RiskReadinessCheckInstance(ReadinessCheck):
    """Local copy of the risk check so this test stays self-contained."""

    name = "risk"

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.risk_state == "ALLOWED"
        return CheckResult(
            passed=passed,
            hard=True,
            reasons=("risk_state is %s" % context.risk_state,),
        )


def test_hard_failure_wins_over_degraded_policy() -> None:
    gate = StrategyExecutionReadinessGate(
        checks=(SecondaryDataCheck(), RiskReadinessCheckInstance()),
        policy=ReadinessPolicy(allow_degraded=True),
    )
    result = gate.evaluate(healthy_context(risk_state="BLOCKED"))
    assert result.state == "BLOCKED"
    assert result.ready is False


# --- Evaluation id --------------------------------------------------------


def test_evaluation_id_is_generated_when_missing() -> None:
    result = make_gate().evaluate(healthy_context(evaluation_id=None))
    assert result.evaluation_id is not None
    assert result.evaluation_id.startswith("READINESS-")


def test_evaluation_id_is_carried_from_context() -> None:
    result = make_gate().evaluate(
        healthy_context(evaluation_id="READINESS-20260813-000007")
    )
    assert result.evaluation_id == "READINESS-20260813-000007"


# --- Readiness TTL / cache ------------------------------------------------


def test_readiness_expires() -> None:
    cache = ReadinessCache(default_ttl=5.0)
    result = make_result(state="READY", ready=True, reasons=())
    cache.put(result)
    assert cache.get(strategy_id="STRAT-001", now=result.checked_at + 4) is not None
    assert cache.get(strategy_id="STRAT-001", now=result.checked_at + 10) is None


def test_cache_returns_none_for_unknown_strategy() -> None:
    cache = ReadinessCache(default_ttl=5.0)
    assert cache.get(strategy_id="STRAT-999", now=1000.0) is None


def test_cache_uses_result_ttl() -> None:
    cache = ReadinessCache(default_ttl=60.0)
    result = make_result(
        state="READY",
        ready=True,
        reasons=(),
        checked_at=1000.0,
        ttl=2.0,
    )
    cache.put(result)
    assert cache.get(strategy_id="STRAT-001", now=1001.0) is not None
    assert cache.get(strategy_id="STRAT-001", now=1003.0) is None


def test_cache_drop_removes_entry() -> None:
    cache = ReadinessCache(default_ttl=60.0)
    cache.put(make_result(state="READY", ready=True, reasons=()))
    cache.drop("STRAT-001")
    assert cache.get(strategy_id="STRAT-001", now=1000.0) is None


# --- Signal generation gate -----------------------------------------------


def test_blocked_strategy_cannot_generate_signal() -> None:
    readiness = make_result()
    assert can_execute(readiness) is False


def test_ready_strategy_can_generate_signal() -> None:
    readiness = make_result(state="READY", ready=True, reasons=())
    assert can_execute(readiness) is True


# --- Runtime readiness adapter --------------------------------------------


class FakeRuntimeReadinessAdapter:
    """A runtime readiness adapter that returns a fixed snapshot."""

    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        self._snapshot = snapshot

    def snapshot(self, strategy_id: str) -> Mapping[str, Any]:
        snapshot = dict(self._snapshot)
        snapshot["strategy_id"] = strategy_id
        return snapshot


def test_snapshot_adapter_feeds_the_gate() -> None:
    adapter: RuntimeReadinessAdapter = FakeRuntimeReadinessAdapter(
        {
            "control_state": "RUNNING",
            "runtime_state": "RUNNING",
            "market_data_state": "FRESH",
            "configuration_state": "VALID",
            "risk_state": "ALLOWED",
            "execution_state": "CONNECTED",
            "timestamp": 1000.0,
        }
    )
    context = snapshot_to_context(adapter.snapshot("STRAT-001"))
    result = make_gate().evaluate(context)
    assert result.ready is True
    assert result.state == "READY"


def test_snapshot_missing_states_fail_safe() -> None:
    context = snapshot_to_context({"strategy_id": "STRAT-001"})
    result = make_gate().evaluate(context)
    assert result.ready is False
    assert result.state == "BLOCKED"


# --- Readiness events -----------------------------------------------------


def test_tracker_emits_blocked_and_unblocked() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    tracker = ReadinessTracker(emit=lambda event, payload: events.append((event, payload)))

    ready = make_result(state="READY", ready=True, reasons=())
    blocked = make_result()
    tracker.record(ready)
    tracker.record(blocked)
    tracker.record(ready)

    names = [event for event, _ in events]
    assert names == [
        READINESS_EVENTS["ready"],
        READINESS_EVENTS["blocked"],
        READINESS_EVENTS["unblocked"],
    ]


def test_tracker_payload_carries_audit_fields() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    tracker = ReadinessTracker(emit=lambda event, payload: events.append((event, payload)))

    tracker.record(make_result(state="READY", ready=True, reasons=()))
    tracker.record(
        make_result(
            evaluation_id="READINESS-20260813-000009",
            reasons=("risk",),
        )
    )

    _, payload = events[-1]
    assert payload["strategy_id"] == "STRAT-001"
    assert payload["evaluation_id"] == "READINESS-20260813-000009"
    assert payload["previous_state"] == "READY"
    assert payload["new_state"] == "BLOCKED"
    assert payload["ready"] is False
    assert payload["reasons"] == ["risk"]


def test_tracker_initial_blocked_state_emits_blocked() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    tracker = ReadinessTracker(emit=lambda event, payload: events.append((event, payload)))

    tracker.record(make_result())
    assert events[0][0] == READINESS_EVENTS["blocked"]


def test_tracker_last_returns_latest() -> None:
    tracker = ReadinessTracker()
    tracker.record(make_result(state="READY", ready=True, reasons=()))
    latest = tracker.last("STRAT-001")
    assert latest is not None
    assert latest.state == "READY"
