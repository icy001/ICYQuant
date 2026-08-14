"""Safe retry tests (Commit 29 Part 1.4 §31-37, §47-48).

A retry is *safe* only when it returns the historical outcome instead of
re-executing: completed, pending and executing commands must never be
replayed into a new side effect (§32-35).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.control_plane import (
    ControlResult,
    DuplicateDetector,
    IdempotencyService,
    InMemoryIdempotencyStore,
    ReplayPolicy,
    ReplayProtector,
    RetryMetadata,
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


class TestCompletedCommandRetry:
    def test_completed_command_is_not_reexecuted(self, service, make_command, make_request):
        """§47: a SUCCEEDED command submitted again returns SUCCEEDED, no re-run."""
        svc, executor = service
        request = make_request(command=make_command())
        first = svc.submit(request)
        assert first.state == "SUCCEEDED"
        second = svc.submit(request)
        assert second.state == "SUCCEEDED"
        assert second.duplicate is True
        executor.assert_called_once()

    def test_complete_helper_marks_record_finished(self, service, make_command, make_request):
        """The response was lost; the client retries with the same key (§32)."""
        svc, executor = service
        request = make_request(command=make_command())
        first = svc.submit(request)
        svc.complete(first.command_id, state="SUCCEEDED")
        retry = svc.submit(request)
        assert retry.command_id == first.command_id
        assert retry.state == "SUCCEEDED"
        assert retry.duplicate is True
        executor.assert_called_once()

    def test_completed_replay_disabled_is_rejected(self, make_command, make_request):
        """§31: allow_completed_replay=False refuses even the historical result."""
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="SUCCEEDED")
        )
        svc = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
            replay=ReplayProtector(
                ReplayPolicy(max_age_seconds=300, allow_completed_replay=False)
            ),
        )
        request = make_request(command=make_command())
        svc.submit(request)
        retry = svc.submit(request)
        assert retry.error_code == "REPLAY_REJECTED"
        executor.assert_called_once()


class TestPendingCommandRetry:
    def test_waiting_approval_is_not_duplicated(self, make_command, make_request):
        """§48: the same key must not re-create an approval."""
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="WAITING_APPROVAL")
        )
        svc = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        request = make_request(command=make_command())
        first = svc.submit(request)
        second = svc.submit(request)
        assert first.command_id == second.command_id
        assert second.state == "WAITING_APPROVAL"
        assert second.duplicate is True
        executor.assert_called_once()


class TestExecutingCommandRetry:
    def test_executing_command_returns_original_attempt(self, make_command, make_request):
        """§34: an EXECUTING command retried stays EXECUTING — no ATTEMPT-002."""
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="EXECUTING")
        )
        svc = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        request = make_request(command=make_command())
        first = svc.submit(request)
        retry = svc.submit(request)
        assert first.command_id == retry.command_id
        assert retry.state == "EXECUTING"
        assert retry.duplicate is True
        executor.assert_called_once()


class TestFailedCommandRetry:
    def test_failed_command_is_not_auto_retried(self, make_command, make_request):
        """§35: FAILED returns the original result; never auto re-executes."""
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="FAILED", success=False)
        )
        svc = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        request = make_request(command=make_command())
        first = svc.submit(request)
        retry = svc.submit(request)
        assert first.state == "FAILED"
        assert retry.state == "FAILED"
        assert retry.duplicate is True
        executor.assert_called_once()

    def test_retry_requires_a_new_idempotency_key(self, make_command, make_request):
        """§36: a retry is a new command under a new key — audit stays clear."""
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="FAILED", success=False)
        )
        svc = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        failed = svc.submit(make_request(command=make_command(), idempotency_key="IDEMP-001"))
        assert failed.state == "FAILED"
        executor.return_value = ControlResult(
            command_id="CMD-002", state="SUCCEEDED"
        )
        retried = svc.submit(make_request(command=make_command(command_id="CMD-002"), idempotency_key="IDEMP-002"))
        assert retried.command_id == "CMD-002"
        assert retried.state == "SUCCEEDED"
        assert executor.call_count == 2


class TestRetryMetadata:
    def test_retry_metadata_links_commands(self):
        """§37: CMD-002 records retry_of CMD-001 for an unambiguous audit trail."""
        metadata = RetryMetadata(
            retry_of_command_id="CMD-001",
            retry_reason="ledger repair retry",
            retry_number=1,
        )
        assert metadata.retry_of_command_id == "CMD-001"
        assert metadata.retry_reason == "ledger repair retry"
        assert metadata.retry_number == 1

    def test_first_command_has_no_retry_relationship(self):
        metadata = RetryMetadata()
        assert metadata.retry_of_command_id is None
        assert metadata.retry_reason is None
