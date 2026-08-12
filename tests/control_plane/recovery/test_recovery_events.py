"""Unit tests: recovery domain events (audit trail)."""

from __future__ import annotations

from services.control_plane.events.recovery_completed import RecoveryCompleted
from services.control_plane.events.recovery_failed import RecoveryFailed
from services.control_plane.events.recovery_started import RecoveryStarted
from services.control_plane.events.recovery_step_completed import RecoveryStepCompleted
from services.control_plane.events.recovery_step_started import RecoveryStepStarted
from services.control_plane.events.recovery_verified import RecoveryVerified


class TestRecoveryStarted:
    def test_construction(self):
        event = RecoveryStarted(
            recovery_id="REC-0001",
            incident_id="INC-00042",
            scope="STRATEGY",
            trigger="position-integrity",
            correlation_id="CORR-1",
            policy_version="1.0.0",
        )
        assert event.event_type == "RECOVERY_STARTED"
        assert event.recovery_id == "REC-0001"
        assert event.incident_id == "INC-00042"

    def test_serialization_round_trip(self):
        event = RecoveryStarted(
            recovery_id="REC-1",
            incident_id="INC-2",
            scope="GLOBAL",
            trigger="risk-failure",
            correlation_id="CORR-9",
            policy_version="1.0.0",
        )
        restored = RecoveryStarted.from_dict(event.to_dict())
        assert restored.recovery_id == "REC-1"
        assert restored.scope == "GLOBAL"
        assert restored.to_dict() == event.to_dict()


class TestRecoveryStepEvents:
    def test_step_started_round_trip(self):
        event = RecoveryStepStarted(
            recovery_id="REC-1",
            step_id="ISOLATE_TRADING",
            step_type="ISOLATE_TRADING",
            attempt=1,
            correlation_id="CORR-1",
        )
        restored = RecoveryStepStarted.from_dict(event.to_dict())
        assert restored.event_type == "RECOVERY_STEP_STARTED"
        assert restored.step_id == "ISOLATE_TRADING"
        assert restored.to_dict() == event.to_dict()

    def test_step_completed_round_trip(self):
        event = RecoveryStepCompleted(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type="REPLAY_EVENTS",
            attempt=2,
            output={"event_cursor": 500000, "replayed_events": 42},
            correlation_id="CORR-1",
        )
        restored = RecoveryStepCompleted.from_dict(event.to_dict())
        assert restored.output["event_cursor"] == 500000
        assert restored.attempt == 2
        assert restored.to_dict() == event.to_dict()


class TestRecoveryFailed:
    def test_construction(self):
        event = RecoveryFailed(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            error="EVENT_GAP: missing event 102",
            failure_class="INTEGRITY",
            retryable=False,
            escalated=True,
            correlation_id="CORR-1",
        )
        assert event.event_type == "RECOVERY_FAILED"
        assert event.escalated is True
        assert event.failure_class == "INTEGRITY"

    def test_serialization_round_trip(self):
        event = RecoveryFailed(
            recovery_id="REC-1",
            step_id="REBUILD_LEDGER",
            error="temporary timeout",
            failure_class="TRANSIENT",
            retryable=True,
            escalated=False,
        )
        restored = RecoveryFailed.from_dict(event.to_dict())
        assert restored.retryable is True
        assert restored.to_dict() == event.to_dict()


class TestRecoveryVerified:
    def test_construction(self):
        event = RecoveryVerified(
            recovery_id="REC-1",
            verified=True,
            checks={"event_replay": True, "ledger_balance": True},
        )
        assert event.event_type == "RECOVERY_VERIFIED"
        assert event.verified is True
        assert event.checks["event_replay"] is True

    def test_serialization_round_trip(self):
        event = RecoveryVerified(
            recovery_id="REC-1", verified=False, checks={"risk_trusted": False}
        )
        restored = RecoveryVerified.from_dict(event.to_dict())
        assert restored.verified is False
        assert restored.to_dict() == event.to_dict()


class TestRecoveryCompleted:
    def test_construction(self):
        event = RecoveryCompleted(
            recovery_id="REC-1", ramp_up_level="LEVEL_1", correlation_id="CORR-1"
        )
        assert event.event_type == "RECOVERY_COMPLETED"
        assert event.ramp_up_level == "LEVEL_1"

    def test_serialization_round_trip(self):
        event = RecoveryCompleted(
            recovery_id="REC-1", ramp_up_level="LEVEL_3", correlation_id="CORR-2"
        )
        restored = RecoveryCompleted.from_dict(event.to_dict())
        assert restored.ramp_up_level == "LEVEL_3"
        assert restored.to_dict() == event.to_dict()
