"""Unit tests: RecoveryOrchestrator happy path + events + policy gate."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.events.recovery_completed import RecoveryCompleted
from services.control_plane.events.recovery_started import RecoveryStarted
from services.control_plane.events.recovery_step_completed import RecoveryStepCompleted
from services.control_plane.events.recovery_step_started import RecoveryStepStarted
from services.control_plane.events.recovery_verified import RecoveryVerified
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.recovery.recovery_context import (
    RecoveryContext,
    RecoveryScope,
)
from services.control_plane.recovery.recovery_orchestrator import (
    InMemoryEventBus,
    RecoveryOrchestrator,
    RecoverySession,
    RetryPolicy,
)
from services.control_plane.recovery.recovery_result import RampUpLevel
from services.control_plane.recovery.recovery_state import RecoveryState
from services.control_plane.recovery.recovery_step import StepType
from services.control_plane.recovery.recovery_strategy import (
    EventRecoveryStrategy,
    GlobalRecoveryStrategy,
    LedgerRecoveryStrategy,
    PositionRecoveryStrategy,
    get_strategy,
    strategy_for_trigger,
)
from services.control_plane.repositories.recovery_checkpoint_repository import (
    RecoveryCheckpointRepository,
)
from services.control_plane.repositories.recovery_repository import RecoveryRepository


def _context(**overrides) -> RecoveryContext:
    defaults = {
        "recovery_id": "REC-0001",
        "incident_id": "INC-00042",
        "trigger": "position-integrity",
        "scope": RecoveryScope.STRATEGY,
        "affected_strategies": ["strategy-a"],
        "system_state": SystemState.DEGRADED,
        "trading_state": TradingState.TRADING_READY,
        "risk_state": ComponentState.HEALTHY,
        "position_state": ComponentState.UNHEALTHY,
        "ledger_state": ComponentState.HEALTHY,
        "correlation_id": "CORR-98273",
        "policy_version": "1.0.0",
    }
    defaults.update(overrides)
    return RecoveryContext(**defaults)


def _make_orchestrator(
    strategy=None, policy_engine=None, retry_policy=None
) -> RecoveryOrchestrator:
    return RecoveryOrchestrator(
        strategy=strategy or PositionRecoveryStrategy(),
        repository=RecoveryRepository(),
        checkpoint_repository=RecoveryCheckpointRepository(),
        event_bus=InMemoryEventBus(),
        policy_engine=policy_engine,
        retry_policy=retry_policy,
    )


class TestRecoveryOrchestratorLifecycle:
    def test_complete_position_recovery(self):
        orchestrator = _make_orchestrator()
        result = orchestrator.start(_context())

        assert result.success
        assert result.state is RecoveryState.COMPLETED
        assert result.verified is True
        assert result.ramp_up_level is RampUpLevel.LEVEL_1
        assert result.recovery_id == "REC-0001"
        assert orchestrator.checkpoints.checkpoint_count() == 8

    def test_plan_has_eight_position_steps(self):
        plan = PositionRecoveryStrategy().build_plan(_context())
        assert [s.step_type for s in plan.steps] == [
            StepType.ISOLATE_TRADING,
            StepType.FREEZE_STATE,
            StepType.REPLAY_EVENTS,
            StepType.REBUILD_LEDGER,
            StepType.REBUILD_POSITION,
            StepType.RECONCILE_STATE,
            StepType.VERIFY_INTEGRITY,
            StepType.RESUME_TRADING,
        ]

    def test_audit_trail_events(self):
        orchestrator = _make_orchestrator()
        orchestrator.start(_context())

        types = [e.event_type for e in orchestrator.events]
        assert types[0] == "RECOVERY_STARTED"
        assert types.count("RECOVERY_STEP_STARTED") == 8
        assert types.count("RECOVERY_STEP_COMPLETED") == 8
        assert "RECOVERY_VERIFIED" in types
        assert types[-1] == "RECOVERY_COMPLETED"

    def test_events_carry_ids(self):
        orchestrator = _make_orchestrator()
        orchestrator.start(_context())

        started = next(e for e in orchestrator.events if isinstance(e, RecoveryStarted))
        assert started.recovery_id == "REC-0001"
        assert started.incident_id == "INC-00042"
        assert started.correlation_id == "CORR-98273"
        assert started.policy_version == "1.0.0"

        completed = next(
            e for e in orchestrator.events if isinstance(e, RecoveryCompleted)
        )
        assert completed.recovery_id == "REC-0001"
        assert completed.ramp_up_level == "LEVEL_1"

        verified = next(
            e for e in orchestrator.events if isinstance(e, RecoveryVerified)
        )
        assert verified.verified is True

    def test_event_bus_receives_events(self):
        bus = InMemoryEventBus()
        seen = []
        bus.subscribe(lambda event: seen.append(event))
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=RecoveryRepository(),
            checkpoint_repository=RecoveryCheckpointRepository(),
            event_bus=bus,
        )
        orchestrator.start(_context())
        assert seen
        assert seen[-1].event_type == "RECOVERY_COMPLETED"

    def test_result_contains_coordination_actions(self):
        orchestrator = _make_orchestrator()
        result = orchestrator.start(_context())
        actions = {a.action for a in result.actions}
        assert "ISOLATE_TRADING" in actions
        assert "FREEZE_STATE" in actions
        assert "RESUME_TRADING" in actions

    def test_session_persisted(self):
        orchestrator = _make_orchestrator()
        orchestrator.start(_context())
        session = orchestrator.repository.get("REC-0001")
        assert session is not None
        assert session.state is RecoveryState.COMPLETED
        assert session.result.success

    def test_max_steps_budget(self):
        orchestrator = _make_orchestrator()
        context = _context()
        plan = PositionRecoveryStrategy().build_plan(context)
        session = RecoverySession(context.recovery_id, context, plan)
        orchestrator.repository.save(session)

        result = orchestrator.run("REC-0001", max_steps=2)
        assert result.in_progress
        assert orchestrator.checkpoints.checkpoint_count() == 2
        assert result.state is RecoveryState.RECOVERING


class TestRecoveryOrchestratorPolicyGate:
    def test_policy_engine_approves_resume(self):
        engine = PolicyEngine()  # no rules -> ALLOW
        orchestrator = _make_orchestrator(policy_engine=engine)
        result = orchestrator.start(_context())
        assert result.success

    def test_policy_engine_denies_resume_escalates(self):
        from services.control_plane.policy.policy import Policy
        from services.control_plane.policy.policy_condition import condition
        from services.control_plane.policy.policy_decision import PolicyDecision
        from services.control_plane.policy.policy_priority import PolicyPriority
        from services.control_plane.policy.policy_rule import PolicyRule

        engine = PolicyEngine()
        engine.register_policy(
            Policy("keep-restricted", "1.0.0", "Keep Restricted").add_rule(
                PolicyRule(
                    rule_id="deny-resume",
                    condition=condition("system_state", "equals", "RECOVERING"),
                    decision=PolicyDecision.DEGRADE,
                    priority=PolicyPriority.HIGH,
                )
            )
        )
        context = _context(system_state=SystemState.RECOVERING)
        orchestrator = _make_orchestrator(policy_engine=engine)
        result = orchestrator.start(context)
        assert result.state is RecoveryState.ESCALATED
        assert result.errors


class TestRecoveryStrategies:
    def test_strategy_registry(self):
        assert isinstance(get_strategy("position"), PositionRecoveryStrategy)
        assert isinstance(get_strategy("ledger"), LedgerRecoveryStrategy)
        assert isinstance(get_strategy("events"), EventRecoveryStrategy)
        assert isinstance(get_strategy("global"), GlobalRecoveryStrategy)

    def test_strategy_for_trigger(self):
        assert isinstance(
            strategy_for_trigger("ledger-corruption", RecoveryScope.STRATEGY),
            LedgerRecoveryStrategy,
        )
        assert isinstance(
            strategy_for_trigger("event-replay-gap", RecoveryScope.SERVICE),
            EventRecoveryStrategy,
        )
        assert isinstance(
            strategy_for_trigger("global-integrity-failure", RecoveryScope.SERVICE),
            GlobalRecoveryStrategy,
        )
        assert isinstance(
            strategy_for_trigger("position-divergence", RecoveryScope.STRATEGY),
            PositionRecoveryStrategy,
        )

    def test_global_scope_forces_global_strategy(self):
        assert isinstance(
            strategy_for_trigger("position-divergence", RecoveryScope.GLOBAL),
            GlobalRecoveryStrategy,
        )

    def test_strategy_step_counts(self):
        context = _context()
        assert len(PositionRecoveryStrategy().build_plan(context).steps) == 8
        assert len(LedgerRecoveryStrategy().build_plan(context).steps) == 7
        assert len(EventRecoveryStrategy().build_plan(context).steps) == 6
        assert len(GlobalRecoveryStrategy().build_plan(context).steps) == 8
