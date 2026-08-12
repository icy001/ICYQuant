"""Unit tests: RecoveryCheckpoint + checksum integrity."""

from __future__ import annotations

from services.control_plane.recovery.recovery_checkpoint import (
    RecoveryCheckpoint,
    compute_checksum,
)
from services.control_plane.recovery.recovery_step import StepType, make_step


class TestComputeChecksum:
    def test_deterministic(self):
        payload = {"event_cursor": 500000, "ledger_version": "L-9"}
        assert compute_checksum(payload) == compute_checksum(payload)

    def test_changes_when_payload_changes(self):
        assert compute_checksum({"a": 1}) != compute_checksum({"a": 2})

    def test_order_independent(self):
        assert compute_checksum({"a": 1, "b": 2}) == compute_checksum({"b": 2, "a": 1})


class TestRecoveryCheckpoint:
    def test_defaults(self):
        cp = RecoveryCheckpoint(
            recovery_id="REC-1", step_id="REPLAY_EVENTS", step_type=StepType.REPLAY_EVENTS
        )
        assert cp.event_cursor == 0
        assert cp.timestamp is not None
        assert cp.checksum == compute_checksum({})

    def test_verify_passes_on_pristine_checkpoint(self):
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type=StepType.REPLAY_EVENTS,
            event_cursor=918273,
            payload={"event_cursor": 918273},
        )
        assert cp.verify()

    def test_verify_fails_on_tampered_payload(self):
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type=StepType.REPLAY_EVENTS,
            payload={"event_cursor": 100},
        )
        cp.payload["event_cursor"] = 999999
        assert not cp.verify()

    def test_from_step_extracts_cursor_and_versions(self):
        step = make_step(StepType.REPLAY_EVENTS, event_cursor=0)
        step.mark_completed(
            output={
                "event_cursor": 500001,
                "ledger_version": "L-7",
                "position_version": "P-3",
            }
        )
        cp = RecoveryCheckpoint.from_step("REC-1", step)
        assert cp.step_id == "REPLAY_EVENTS"
        assert cp.event_cursor == 500001
        assert cp.ledger_version == "L-7"
        assert cp.position_version == "P-3"
        assert cp.verify()

    def test_update_payload_recomputes_checksum(self):
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REPLAY_EVENTS",
            step_type=StepType.REPLAY_EVENTS,
            payload={"event_cursor": 1},
        )
        old = cp.checksum
        cp.update_payload(event_cursor=2)
        assert cp.verify()
        assert cp.payload["event_cursor"] == 2
        assert cp.checksum != old

    def test_serialization_round_trip(self):
        cp = RecoveryCheckpoint(
            recovery_id="REC-1",
            step_id="REBUILD_LEDGER",
            step_type=StepType.REBUILD_LEDGER,
            event_cursor=0,
            ledger_version="L-9",
            payload={"ledger_version": "L-9", "balance_verified": True},
        )
        restored = RecoveryCheckpoint.from_dict(cp.to_dict())
        assert restored.recovery_id == cp.recovery_id
        assert restored.step_type is StepType.REBUILD_LEDGER
        assert restored.verify()
        assert restored.to_dict() == cp.to_dict()
