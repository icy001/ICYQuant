"""Duplicate submission tests through the IdempotencyService (Commit 29 Part 1.4 §12-14, §38, §44-45).

Exactly-once command identity: the second submission of the same
idempotency key returns the *original* command instead of creating a new one
(§14, §44).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.control_plane import (
    ControlResult,
    DuplicateDetector,
    IdempotencyService,
    InMemoryIdempotencyStore,
)


@pytest.fixture
def service():
    executor = MagicMock(
        return_value=ControlResult(command_id="CMD-001", state="SUCCEEDED")
    )
    svc = IdempotencyService(
        detector=DuplicateDetector(InMemoryIdempotencyStore()),
        executor=executor,
    )
    return svc, executor


class TestDuplicateSubmission:
    def test_duplicate_submission_returns_existing_command(self, service, make_command, make_request):
        """§44: both submissions share one command id; the executor runs once."""
        svc, executor = service
        request = make_request(command=make_command())
        first = svc.submit(request)
        second = svc.submit(request)
        assert first.command_id == second.command_id
        assert first.duplicate is False
        assert second.duplicate is True
        executor.assert_called_once()

    def test_duplicate_never_creates_a_second_command(self, service, make_command, make_request):
        svc, executor = service
        request = make_request(command=make_command())
        svc.submit(request)
        duplicate = svc.submit(request)
        assert duplicate.command_id == "CMD-001"
        assert duplicate.duplicate is True
        assert duplicate.state == "SUCCEEDED"
        executor.assert_called_once()

    def test_duplicate_response_exposes_original_state(self, service, make_command, make_request):
        """§38: a duplicate returns the original command, not a bare 409."""
        svc, _executor = service
        request = make_request(command=make_command())
        first = svc.submit(request)
        duplicate = svc.submit(request)
        assert duplicate.command_id == first.command_id
        assert duplicate.state == first.state
        assert duplicate.duplicate is True
        assert duplicate.conflict is False

    def test_different_keys_create_distinct_commands(self, service, make_command, make_request):
        svc, executor = service
        request_a = make_request(command=make_command(), idempotency_key="IDEMP-001")
        request_b = make_request(command=make_command(), idempotency_key="IDEMP-002")
        result_a = svc.submit(request_a)
        result_b = svc.submit(request_b)
        assert result_a.duplicate is False
        assert result_b.duplicate is False
        assert executor.call_count == 2

    def test_same_key_different_command_is_rejected(self, service, make_command, make_request):
        """§45: pause then kill under one key is an IDEMPOTENCY_CONFLICT."""
        svc, executor = service
        pause = make_request(command=make_command(action="pause"))
        kill = make_request(command=make_command(action="kill"))
        svc.submit(pause)
        conflicting = svc.submit(kill)
        assert conflicting.error_code == "IDEMPOTENCY_CONFLICT"
        assert conflicting.conflict is True
        assert conflicting.duplicate is False
        executor.assert_called_once()

    def test_conflict_does_not_execute(self, service, make_command, make_request):
        """§17: on conflict neither dispatcher nor executor is invoked again."""
        svc, executor = service
        pause = make_request(command=make_command(action="pause"))
        kill = make_request(command=make_command(action="kill"))
        svc.submit(pause)
        conflicting = svc.submit(kill)
        assert conflicting.error_code == "IDEMPOTENCY_CONFLICT"
        executor.assert_called_once()

    def test_new_command_reports_not_duplicate(self, service, make_command, make_request):
        svc, _executor = service
        first = svc.submit(make_request(command=make_command()))
        assert first.duplicate is False
        assert first.conflict is False
