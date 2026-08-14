"""Execution attempts — one attempt per actual run (Commit 29 Part 1.3 §11-13, §30, §39).

A command is the business intent (``trading:pause``); an ``ExecutionAttempt``
is a single concrete run of that intent. A command may have several attempts
(``ATTEMPT-001`` timed out, ``ATTEMPT-002`` succeeded) and the ledger keeps
every one of them so the final answer to *why did this command execute twice*
is auditable (§12, §30).

Timeout does not imply failure: a missing response never proves the target
did not execute, so a timed-out attempt is marked ``TIMED_OUT`` and then
``UNKNOWN`` — never ``FAILED`` (§15-16). ``UNKNOWN`` is the signal for the
recovery engine to reconcile with the target instead of blind-retrying (§16).

Note: the Part 1.3 spec names this module ``execution.py``; it is shipped as
``execution_attempt.py`` so it does not shadow the existing ``execution/``
package.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from .errors import ControlErrorCode, TargetResponseTimeout, classify_error

_UNSET = object()


class ExecutionState(str, Enum):
    """Attempt-level execution state (§13, §17)."""

    CREATED = "CREATED"
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExecutionAttempt:
    """Immutable record of one execution attempt (§11)."""

    attempt_id: str
    command_id: str
    attempt_number: int
    started_at: datetime
    finished_at: datetime | None
    state: ExecutionState
    error_code: str | None = None


class ExecutionRunner:
    """Runs attempts and keeps the per-command attempt ledger (§30)."""

    def __init__(self) -> None:
        self._attempts: dict[str, list[ExecutionAttempt]] = {}

    def attempts_for(self, command_id: str) -> tuple[ExecutionAttempt, ...]:
        """Ledger for one command (§30)."""
        return tuple(self._attempts.get(command_id, ()))

    def start(
        self,
        command: Any,
        *,
        started_at: datetime | None = None,
    ) -> ExecutionAttempt:
        number = len(self._attempts.get(command.command_id, ())) + 1
        attempt = ExecutionAttempt(
            attempt_id=f"ATTEMPT-{command.command_id}-{number:03d}",
            command_id=command.command_id,
            attempt_number=number,
            started_at=started_at or datetime.now(timezone.utc),
            finished_at=None,
            state=ExecutionState.STARTED,
        )
        self._attempts.setdefault(command.command_id, []).append(attempt)
        return attempt

    def _record(
        self,
        attempt: ExecutionAttempt,
        state: ExecutionState,
        *,
        finished_at: datetime | None = None,
        error_code: object = _UNSET,
    ) -> ExecutionAttempt:
        kwargs: dict[str, Any] = {
            "state": state,
            "finished_at": finished_at or datetime.now(timezone.utc),
        }
        if error_code is not _UNSET:
            kwargs["error_code"] = error_code
        recorded = replace(attempt, **kwargs)
        entries = self._attempts.get(attempt.command_id, [])
        for index, entry in enumerate(entries):
            if entry.attempt_id == attempt.attempt_id:
                entries[index] = recorded
                break
        return recorded

    def succeed(
        self,
        attempt: ExecutionAttempt,
        *,
        finished_at: datetime | None = None,
    ) -> ExecutionAttempt:
        return self._record(
            attempt,
            ExecutionState.SUCCEEDED,
            finished_at=finished_at,
        )

    def fail(
        self,
        attempt: ExecutionAttempt,
        *,
        error_code: str | None = None,
        finished_at: datetime | None = None,
    ) -> ExecutionAttempt:
        return self._record(
            attempt,
            ExecutionState.FAILED,
            finished_at=finished_at,
            error_code=error_code or ControlErrorCode.EXECUTION_ERROR.value,
        )

    def timeout(
        self,
        attempt: ExecutionAttempt,
        *,
        finished_at: datetime | None = None,
    ) -> ExecutionAttempt:
        return self._record(
            attempt,
            ExecutionState.TIMED_OUT,
            finished_at=finished_at,
            error_code=ControlErrorCode.TIMEOUT_ERROR.value,
        )

    def mark_unknown(
        self,
        attempt: ExecutionAttempt,
        *,
        finished_at: datetime | None = None,
    ) -> ExecutionAttempt:
        return self._record(attempt, ExecutionState.UNKNOWN, finished_at=finished_at)

    def run(
        self,
        command: Any,
        handler: Callable[[Any], Any],
    ) -> ExecutionAttempt:
        """Execute one attempt and record the outcome (§39).

        * handler returns normally              -> SUCCEEDED
        * handler raises TargetResponseTimeout  -> TIMED_OUT, then UNKNOWN
          (a missing response never proves the target did not execute,
          §15-16) — the caller must reconcile, not blind-retry
        * any other exception                   -> FAILED (classified §44)
        """
        attempt = self.start(command)
        try:
            handler(command)
        except TargetResponseTimeout:
            timed_out = self.timeout(attempt)
            return self.mark_unknown(timed_out)
        except Exception as exc:
            return self.fail(attempt, error_code=classify_error(exc).value)
        return self.succeed(attempt)
