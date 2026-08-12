"""Unit tests: crash recovery, resumption, idempotency."""

from __future__ import annotations

import pytest

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.recovery.recovery_context import (
    RecoveryContext,
    RecoveryScope,
)
from services.control_plane.recovery.recovery_orchestrator import (
    RecoveryOrchestrator,
    RecoverySession,
)
from services.control_plane.recovery.recovery_state import RecoveryState
from services.control_plane.recovery.recovery_step import StepStatus, StepType
from services.control_plane.recovery.recovery_strategy import PositionRecoveryStrategy
from services.control_plane.repositories.recovery_checkpoint_repository import (
    RecoveryCheckpointRepository,
)
from services.control_plane.repositories.recovery_repository import RecoveryRepository


def _context(**overrides) -> RecoveryContext:
    defaults = {
        "recovery_id": "REC-1",
        "incident_id": "INC-7",
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


def _repos():
    return RecoveryRepository(), RecoveryCheckpointRepository()


class TestCrashRecovery:
    def test_resume_from_checkpoint_after_crash(self):
        repo, checkpoints = _repos()
        first = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context()
        session = RecoverySession(
            context.recovery_id,
            context,
            PositionRecoveryStrategy().build_plan(context),
        )
        repo.save(session)
        result = first.run("REC-1", max_steps=2)
        assert result.in_progress
        assert checkpoints.checkpoint_count() == 2

        # orchestrator "crashed" — a fresh instance resumes from durable state
        second = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        result = second.resume("REC-1")
        assert result.success
        assert result.state is RecoveryState.COMPLETED
        assert checkpoints.checkpoint_count() == 8

    def test_resume_does_not_restart_completed_steps(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context()
        session = RecoverySession(
            context.recovery_id, context, PositionRecoveryStrategy().build_plan(context)
        )
        repo.save(session)
        orchestrator.run("REC-1", max_steps=2)
        orchestrator.resume("REC-1")

        loaded = repo.get("REC-1")
        assert loaded.plan.steps[0].status is StepStatus.COMPLETED  # ISOLATE_TRADING
        assert loaded.plan.steps[1].status is StepStatus.COMPLETED  # FREEZE_STATE
        assert loaded.plan.steps[2].status is StepStatus.COMPLETED  # REPLAY_EVENTS

    def test_resume_without_checkpoint_starts_from_beginning(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context()
        session = RecoverySession(
            context.recovery_id, context, PositionRecoveryStrategy().build_plan(context)
        )
        repo.save(session)
        result = orchestrator.resume("REC-1")
        assert result.success
        assert checkpoints.checkpoint_count() == 8


class TestIdempotency:
    def test_duplicate_start_resumes_existing_recovery(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context(incident_id="INC-X")
        session = RecoverySession(
            context.recovery_id, context, PositionRecoveryStrategy().build_plan(context)
        )
        repo.save(session)
        orchestrator.run("REC-1", max_steps=1)

        # same incident fires again while the recovery is still active
        result = orchestrator.start(
            _context(incident_id="INC-X", recovery_id="REC-NEW")
        )
        assert result.recovery_id == "REC-1"
        assert repo.recovery_count() == 1

    def test_new_incident_creates_new_recovery(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        orchestrator.start(_context(incident_id="INC-A", recovery_id=""))
        orchestrator.start(_context(incident_id="INC-B", recovery_id=""))
        assert repo.recovery_count() == 2

    def test_auto_generated_recovery_id(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context(incident_id="INC-C")
        context.recovery_id = ""
        result = orchestrator.start(context)
        assert result.recovery_id == "REC-0001"


class TestRepository:
    def test_find_active_by_incident(self):
        repo, checkpoints = _repos()
        orchestrator = RecoveryOrchestrator(
            strategy=PositionRecoveryStrategy(),
            repository=repo,
            checkpoint_repository=checkpoints,
        )
        context = _context(incident_id="INC-42")
        session = RecoverySession(
            context.recovery_id, context, PositionRecoveryStrategy().build_plan(context)
        )
        repo.save(session)
        found = repo.find_active_by_incident("INC-42")
        assert found is not None
        assert found.recovery_id == "REC-1"
        assert repo.find_by_incident("INC-42").recovery_id == "REC-1"

    def test_session_serialization_round_trip(self):
        context = _context()
        session = RecoverySession(
            context.recovery_id, context, PositionRecoveryStrategy().build_plan(context)
        )
        session.state = RecoveryState.ISOLATING
        restored = RecoverySession.from_dict(session.to_dict())
        assert restored.recovery_id == session.recovery_id
        assert restored.context.incident_id == "INC-7"
        assert restored.state is RecoveryState.ISOLATING
        assert [s.step_type for s in restored.plan.steps] == [
            s.step_type for s in session.plan.steps
        ]

    def test_checkpoint_repository_save_and_latest(self):
        from services.control_plane.recovery.recovery_checkpoint import (
            RecoveryCheckpoint,
        )

        repo = RecoveryCheckpointRepository()
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type=StepType.REPLAY_EVENTS,
            event_cursor=500000,
            payload={"event_cursor": 500000},
        )
        repo.save(cp)
        assert repo.latest("REC-1").event_cursor == 500000
        assert repo.checkpoint_count() == 1
        repo.delete("REC-1")
        assert repo.latest("REC-1") is None

    def test_checkpoint_repository_rejects_tampered_payload(self):
        from services.control_plane.recovery.recovery_checkpoint import (
            RecoveryCheckpoint,
        )

        repo = RecoveryCheckpointRepository()
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type=StepType.REPLAY_EVENTS,
            payload={"event_cursor": 500000},
        )
        cp.payload["event_cursor"] = 999999  # tamper with the checksum
        with pytest.raises(ValueError):
            repo.save(cp)
