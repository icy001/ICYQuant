"""Idempotency record and durable store (Commit 29 Part 1.4 §9-10, §40-42).

Core relationship (§9)::

    Idempotency Key -> Command ID -> Command Fingerprint

The store is the authoritative idempotency layer. Production implementations
may back it with PostgreSQL (or Redis + PostgreSQL), but the authoritative
record must always live in a durable store (§10).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class IdempotencyRecord:
    """Ties an idempotency key to a command id and its fingerprint (§9)."""

    idempotency_key: str
    principal_id: str
    command_id: str
    fingerprint: str
    created_at: datetime
    expires_at: datetime | None = None
    state: str = "NEW_COMMAND"


class IdempotencyStore(Protocol):
    """Durable authority for idempotency records (§10)."""

    def get(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Return the record bound to ``idempotency_key`` or None."""

    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        """Atomically insert ``record`` (§40).

        Follows ``INSERT ... ON CONFLICT DO NOTHING`` semantics: it never
        overwrites. Returns the authoritative record — the freshly created
        one, or the existing record when the composite key was already taken
        (§41).
        """

    def update_state(
        self, idempotency_key: str, state: str
    ) -> IdempotencyRecord | None:
        """Advance the record's state (e.g. NEW_COMMAND -> SUCCEEDED)."""

    def get_by_identity(
        self, idempotency_key: str, principal_id: str
    ) -> IdempotencyRecord | None:
        """Resolve by the composite (idempotency_key, principal_id) identity (§4)."""

    def get_by_command_id(self, command_id: str) -> IdempotencyRecord | None:
        """Resolve the record that owns ``command_id`` (used for retry/safe-retry)."""


class InMemoryIdempotencyStore:
    """Thread-safe in-memory implementation with atomic create (§40)."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get(self, idempotency_key: str) -> IdempotencyRecord | None:
        with self._lock:
            for (key, _principal), record in self._records.items():
                if key == idempotency_key:
                    return record
            return None

    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        with self._lock:
            identity = (record.idempotency_key, record.principal_id)
            existing = self._records.get(identity)
            if existing is not None:
                return existing
            self._records[identity] = record
            return record

    def update_state(
        self, idempotency_key: str, state: str
    ) -> IdempotencyRecord | None:
        with self._lock:
            for identity, record in list(self._records.items()):
                if record.idempotency_key != idempotency_key:
                    continue
                updated = IdempotencyRecord(
                    idempotency_key=record.idempotency_key,
                    principal_id=record.principal_id,
                    command_id=record.command_id,
                    fingerprint=record.fingerprint,
                    created_at=record.created_at,
                    expires_at=record.expires_at,
                    state=state,
                )
                self._records[identity] = updated
                return updated
            return None

    def get_by_identity(
        self, idempotency_key: str, principal_id: str
    ) -> IdempotencyRecord | None:
        with self._lock:
            return self._records.get((idempotency_key, principal_id))

    def get_by_command_id(self, command_id: str) -> IdempotencyRecord | None:
        with self._lock:
            for record in self._records.values():
                if record.command_id == command_id:
                    return record
            return None

    def delete_expired(self, now: datetime | None = None) -> int:
        """Remove records whose TTL expired; returns the count removed (§42).

        Only the idempotency cache layer expires — the audit / command
        history must remain durable and untouched (§42).
        """
        reference = now or datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            for identity, record in list(self._records.items()):
                if record.expires_at is not None and record.expires_at <= reference:
                    del self._records[identity]
                    removed += 1
        return removed
