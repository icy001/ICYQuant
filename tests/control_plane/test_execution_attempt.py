"""Execution attempts — one attempt per actual run (§11-13, §30, §39)."""

from __future__ import annotations

import pytest

from services.control_plane.errors import ControlErrorCode, TargetResponseTimeout
from services.control_plane.execution_attempt import (
    ExecutionAttempt,
    ExecutionRunner,
    ExecutionState,
)


def test_attempt_model_fields(make_command):
    attempt = ExecutionAttempt(
        attempt_id="ATTEMPT-001",
        command_id="CMD-001",
        attempt_number=1,
        started_at=None,
        finished_at=None,
        state=ExecutionState.CREATED,
    )
    assert attempt.attempt_id == "ATTEMPT-001"
    assert attempt.command_id == "CMD-001"
    assert attempt.attempt_number == 1
    assert attempt.state is ExecutionState.CREATED


def test_start_creates_numbered_attempts(make_command):
    runner = ExecutionRunner()
    first = runner.start(make_command())
    second = runner.start(make_command())
    assert first.attempt_number == 1
    assert second.attempt_number == 2
    assert first.state is ExecutionState.STARTED
    assert first.finished_at is None


def test_run_success_records_succeeded(make_command):
    runner = ExecutionRunner()

    def handler(command):
        return command

    attempt = runner.run(make_command(), handler)
    assert attempt.state is ExecutionState.SUCCEEDED
    assert attempt.finished_at is not None


def test_run_handler_failure_records_failed_with_classified_error(make_command):
    runner = ExecutionRunner()

    def handler(command):
        raise RuntimeError("boom")

    attempt = runner.run(make_command(), handler)
    assert attempt.state is ExecutionState.FAILED
    assert attempt.error_code == ControlErrorCode.EXECUTION_ERROR.value


def test_run_timeout_becomes_unknown_not_failed(make_command):
    """§15-16: a missing response never proves the target did not execute."""

    runner = ExecutionRunner()

    def handler(command):
        raise TargetResponseTimeout("no ack")

    attempt = runner.run(make_command(), handler)
    assert attempt.state is ExecutionState.UNKNOWN
    # §16: TIMEOUT is classified separately (TIMEOUT_ERROR), never FAILED.
    assert attempt.error_code == ControlErrorCode.TIMEOUT_ERROR.value


def test_ledger_keeps_every_attempt(make_command):
    runner = ExecutionRunner()
    command = make_command()

    def failing(command):
        raise RuntimeError("boom")

    def succeeding(command):
        return command

    runner.run(command, failing)
    runner.run(command, succeeding)
    ledger = runner.attempts_for(command.command_id)
    assert [a.attempt_number for a in ledger] == [1, 2]
    assert [a.state for a in ledger] == [ExecutionState.FAILED, ExecutionState.SUCCEEDED]


def test_timeout_and_unknown_are_distinct_states(make_command):
    runner = ExecutionRunner()
    attempt = runner.start(make_command())
    timed_out = runner.timeout(attempt)
    assert timed_out.state is ExecutionState.TIMED_OUT
    assert timed_out.error_code == ControlErrorCode.TIMEOUT_ERROR.value
    unknown = runner.mark_unknown(timed_out)
    assert unknown.state is ExecutionState.UNKNOWN
