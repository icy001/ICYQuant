"""Duplicate detection tests (Commit 29 Part 1.4 §11-17, §40-41).

    same key + same fingerprint     -> DUPLICATE
    same key + different fingerprint -> IDEMPOTENCY_CONFLICT (§15)
"""

from __future__ import annotations

import pytest

from services.control_plane import (
    DuplicateDetector,
    IdempotencyConflict,
    InMemoryIdempotencyStore,
    fingerprint_command,
)


@pytest.fixture
def store():
    return InMemoryIdempotencyStore()


@pytest.fixture
def detector(store):
    return DuplicateDetector(store)


class TestDuplicateDetector:
    def test_check_returns_none_when_key_is_unknown(self, detector):
        assert detector.check("IDEMP-001") is None

    def test_first_submission_creates_record(self, detector):
        record, created = detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        assert created is True
        assert record.idempotency_key == "IDEMP-001"
        assert record.command_id == "CMD-001"
        assert record.fingerprint == "fp-1"
        assert record.state == "NEW_COMMAND"

    def test_second_submission_with_same_fingerprint_is_duplicate(self, detector):
        detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        record, created = detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        assert created is False
        assert record.command_id == "CMD-001"

    def test_same_key_different_fingerprint_is_conflict(self, detector):
        detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        with pytest.raises(IdempotencyConflict):
            detector.submit(
                idempotency_key="IDEMP-001",
                principal_id="ops-001",
                command_id="CMD-002",
                fingerprint="fp-2",
            )

    def test_conflict_message_names_the_key(self, detector):
        detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        with pytest.raises(IdempotencyConflict, match="IDEMP-001"):
            detector.submit(
                idempotency_key="IDEMP-001",
                principal_id="ops-001",
                command_id="CMD-002",
                fingerprint="fp-2",
            )

    def test_same_key_different_principal_is_distinct_operation(self, store):
        """value + principal_id jointly identify a request (§4)."""
        detector = DuplicateDetector(store)
        detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id="CMD-001",
            fingerprint="fp-1",
        )
        record, created = detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-002",
            command_id="CMD-002",
            fingerprint="fp-2",
        )
        assert created is True
        assert record.command_id == "CMD-002"

    def test_detector_round_trips_through_service_fingerprint(self, detector, make_command):
        command = make_command()
        detector.submit(
            idempotency_key="IDEMP-001",
            principal_id="ops-001",
            command_id=command.command_id,
            fingerprint=fingerprint_command(command),
        )
        record = detector.check("IDEMP-001")
        assert record.fingerprint == fingerprint_command(command)
