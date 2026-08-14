"""Command deduplication — exactly-once command identity (Commit 29 Part 1.4 §11-14, §18-19, §40-41).

Idempotency sits *before* governance (§18-19): the same request must never
re-enter the governance decision flow, must never re-create an approval, and
must never re-execute (§32-35).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .duplicate import IdempotencyConflict, IdempotencyResult
from .fingerprint import fingerprint_command
from .idempotency_store import IdempotencyRecord, IdempotencyStore
from .replay import ReplayProtector
from .request import ControlRequest


@dataclass(frozen=True)
class RetryMetadata:
    """Retry relationship between commands (§36-37).

    A retry is a *new* command under a *new* idempotency key, so the audit
    trail stays unambiguous (§36)::

        CMD-001  ATTEMPT-001  FAILED
        CMD-002  ATTEMPT-001  SUCCEEDED   (retry_of = CMD-001)
    """

    retry_of_command_id: str | None = None
    retry_reason: str | None = None
    retry_number: int = 1


class DuplicateDetector:
    """Detects and registers idempotency records before governance (§11).

    ``submit`` is the atomic path (§40): an unseen key is created exactly
    once; a repeated key returns the original record; a repeated key with a
    different fingerprint raises ``IdempotencyConflict`` (§15-16).
    """

    def __init__(self, store: IdempotencyStore) -> None:
        self.store = store

    def check(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Return the stored record for ``idempotency_key`` or None (§11)."""
        return self.store.get(idempotency_key)

    def submit(
        self,
        *,
        idempotency_key: str,
        principal_id: str,
        command_id: str,
        fingerprint: str,
        now: datetime | None = None,
    ) -> tuple[IdempotencyRecord, bool]:
        """Register the first use of a key atomically (§40).

        Returns ``(record, created)``:
        - ``created=True``  -> the record was just inserted (NEW_COMMAND)
        - ``created=False`` -> the key already existed (DUPLICATE)

        Raises ``IdempotencyConflict`` when the existing record carries a
        different fingerprint (§41).
        """
        existing = self.store.get_by_identity(idempotency_key, principal_id)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise IdempotencyConflict(
                    "idempotency key reused with a different command fingerprint: "
                    f"{idempotency_key}"
                )
            return existing, False
        timestamp = now or datetime.now(timezone.utc)
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            principal_id=principal_id,
            command_id=command_id,
            fingerprint=fingerprint,
            created_at=timestamp,
        )
        stored = self.store.create(record)
        if stored.fingerprint != fingerprint:
            raise IdempotencyConflict(
                "idempotency key reused with a different command fingerprint: "
                f"{idempotency_key}"
            )
        return stored, stored is record


class IdempotencyService:
    """End-to-end idempotent submission (Commit 29 Part 1.4 §12-19, §27, §53).

    Pipeline position (fail closed, §18-19, §53)::

        Request -> Replay Check -> Idempotency Check -> Fingerprint
                -> Deduplication -> Governance -> Execution

    A duplicate request never re-enters governance, never re-creates an
    approval and never re-executes (§32-35); a conflicting key is rejected
    before the dispatcher and executor are reached (§17).
    """

    def __init__(
        self,
        *,
        detector: DuplicateDetector,
        executor: Callable[[ControlRequest], Any],
        replay: ReplayProtector | None = None,
        claims: Any | None = None,
    ) -> None:
        self.detector = detector
        self.executor = executor
        self.replay = replay
        self.claims = claims

    def submit(self, request: ControlRequest) -> IdempotencyResult:
        """Submit once, exactly once (§12-14, §44-49)."""
        now = datetime.now(timezone.utc)

        # 1. Replay check — oldest gate, before everything (§18, §28-29).
        if self.replay is not None:
            decision = self.replay.check(request.submitted_at, now=now)
            if not decision.allowed:
                return IdempotencyResult(
                    command_id=request.command.command_id,
                    state="REPLAY_REJECTED",
                    duplicate=False,
                    conflict=False,
                    error_code="REPLAY_REJECTED",
                    error_message=decision.reason,
                )

        # 2. Fingerprint + atomic deduplication (§6-8, §40).
        fingerprint = fingerprint_command(request.command)
        try:
            record, created = self.detector.submit(
                idempotency_key=request.idempotency_key,
                principal_id=request.command.requested_by,
                command_id=request.command.command_id,
                fingerprint=fingerprint,
                now=now,
            )
        except IdempotencyConflict as exc:
            return IdempotencyResult(
                command_id=request.command.command_id,
                state="IDEMPOTENCY_CONFLICT",
                duplicate=False,
                conflict=True,
                error_code="IDEMPOTENCY_CONFLICT",
                error_message=str(exc),
            )

        # 3. Existing key — return the original command, never re-execute (§32-35).
        if not created:
            if self.replay is not None:
                replay_decision = self.replay.check_command_state(record.state)
                if not replay_decision.allowed:
                    return IdempotencyResult(
                        command_id=record.command_id,
                        state=record.state,
                        duplicate=True,
                        conflict=False,
                        error_code="REPLAY_REJECTED",
                        error_message=replay_decision.reason,
                    )
            return IdempotencyResult(
                command_id=record.command_id,
                state=record.state,
                duplicate=True,
                conflict=False,
            )

        # 4. Ownership — a command may only run under a valid claim (§26-27).
        if self.claims is not None:
            claim_result = self.claims.acquire_with_result(
                request.command.command_id,
                worker_id="control-service",
                now=now,
            )
            if not claim_result.acquired:
                return IdempotencyResult(
                    command_id=request.command.command_id,
                    state="CLAIM_ALREADY_HELD",
                    duplicate=False,
                    conflict=False,
                    error_code="CLAIM_ALREADY_HELD",
                    error_message=claim_result.reason,
                )

        # 5. Governance + execution.
        outcome = self.executor(request)
        self.detector.store.update_state(request.idempotency_key, outcome.state)
        return IdempotencyResult(
            command_id=request.command.command_id,
            state=outcome.state,
            duplicate=False,
            conflict=False,
            error_code=getattr(outcome, "error_code", None),
            error_message=getattr(outcome, "error_message", None),
        )

    def complete(
        self, command_id: str, *, state: str = "SUCCEEDED"
    ) -> IdempotencyResult | None:
        """Mark the command's idempotency record as finished (§47).

        A subsequent submission with the same key then returns the completed
        state instead of re-executing (safe retry, §31-32).
        """
        record = self.detector.store.get_by_command_id(command_id)
        if record is None:
            return None
        self.detector.store.update_state(record.idempotency_key, state)
        return IdempotencyResult(
            command_id=command_id,
            state=state,
            duplicate=False,
            conflict=False,
        )


__all__ = ["DuplicateDetector", "IdempotencyService", "RetryMetadata"]
