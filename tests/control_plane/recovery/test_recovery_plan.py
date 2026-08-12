"""Unit tests: RecoveryPlan building, progress, resumption."""

from __future__ import annotations

from services.control_plane.recovery.recovery_checkpoint import RecoveryCheckpoint
from services.control_plane.recovery.recovery_plan import RecoveryPlan
from services.control_plane.recovery.recovery_step import (
    RecoveryStep,
    StepStatus,
    StepType,
    make_step,
)


def _sample_plan(recovery_id="REC-0001") -> RecoveryPlan:
    plan = RecoveryPlan(recovery_id)
    plan.add_step(make_step(StepType.ISOLATE_TRADING))
    plan.add_step(make_step(StepType.FREEZE_STATE))
    plan.add_step(make_step(StepType.REPLAY_EVENTS))
    plan.add_step(make_step(StepType.REBUILD_POSITION))
    return plan


class TestRecoveryPlanBuild:
    def test_with_steps_preserves_order(self):
        plan = _sample_plan()
        assert [s.step_type for s in plan.steps] == [
            StepType.ISOLATE_TRADING,
            StepType.FREEZE_STATE,
            StepType.REPLAY_EVENTS,
            StepType.REBUILD_POSITION,
        ]

    def test_current_step_is_first_pending(self):
        plan = _sample_plan()
        assert plan.current_step().step_type is StepType.ISOLATE_TRADING
        plan.steps[0].mark_completed()
        assert plan.current_step().step_type is StepType.FREEZE_STATE

    def test_current_step_none_when_done(self):
        plan = _sample_plan()
        for step in plan.steps:
            step.mark_completed()
        assert plan.current_step() is None
        assert plan.is_complete()

    def test_progress(self):
        plan = _sample_plan()
        assert plan.progress() == 0.0
        plan.steps[0].mark_completed()
        plan.steps[1].mark_completed()
        assert plan.progress() == 0.5
        assert plan.completed_count == 2
        assert plan.total == 4

    def test_is_failed(self):
        plan = _sample_plan()
        plan.steps[2].mark_failed("boom")
        assert plan.is_failed()
        assert plan.failed_step().step_id == "REPLAY_EVENTS"

    def test_serialization_round_trip(self):
        plan = _sample_plan()
        plan.steps[1].mark_completed(output={"snapshot_id": "SNAP-1"})
        restored = RecoveryPlan.from_dict(plan.to_dict())
        assert restored.recovery_id == plan.recovery_id
        assert [s.step_type for s in restored.steps] == [
            s.step_type for s in plan.steps
        ]
        assert restored.steps[1].status is StepStatus.COMPLETED
        assert restored.steps[1].output == {"snapshot_id": "SNAP-1"}
        assert restored.to_dict() == plan.to_dict()


class TestRecoveryPlanResume:
    def test_resume_resets_inflight_step_after_checkpoint(self):
        plan = _sample_plan()
        plan.steps[0].mark_completed()
        plan.steps[1].mark_completed()
        plan.steps[2].mark_running()  # crashed mid-step
        checkpoint = RecoveryCheckpoint(
            recovery_id="REC-0001",
            step_id="FREEZE_STATE",
            step_type=StepType.FREEZE_STATE,
        )
        assert plan.resume_from(checkpoint)
        assert plan.steps[0].status is StepStatus.COMPLETED
        assert plan.steps[1].status is StepStatus.COMPLETED
        assert plan.steps[2].status is StepStatus.PENDING
        assert plan.current_step().step_type is StepType.REPLAY_EVENTS

    def test_resume_resets_failed_step_after_checkpoint(self):
        plan = _sample_plan()
        plan.steps[0].mark_completed()
        plan.steps[1].mark_completed()
        plan.steps[2].mark_failed("EVENT_GAP")
        checkpoint = RecoveryCheckpoint(
            recovery_id="REC-0001",
            step_id="FREEZE_STATE",
            step_type=StepType.FREEZE_STATE,
        )
        plan.resume_from(checkpoint)
        assert plan.steps[2].status is StepStatus.PENDING
        assert plan.steps[2].error is None

    def test_resume_injects_checkpoint_payload(self):
        plan = _sample_plan()
        plan.steps[0].mark_completed()
        checkpoint = RecoveryCheckpoint(
            recovery_id="REC-0001",
            step_id="ISOLATE_TRADING",
            step_type=StepType.ISOLATE_TRADING,
            payload={"event_cursor": 500000},
        )
        plan.resume_from(checkpoint)
        target = plan.steps[1]
        assert target.input.get("event_cursor") == 500000

    def test_resume_returns_false_when_checkpoint_step_unknown(self):
        plan = _sample_plan()
        checkpoint = RecoveryCheckpoint(
            recovery_id="REC-0001",
            step_id="NOPE",
            step_type=StepType.REPLAY_EVENTS,
        )
        assert not plan.resume_from(checkpoint)
