"""Handler registry and idempotency registry (Commit 29 Part 1.1 §8-9, §27-30).

* ``ControlRegistry``: every executable control command must be registered.
  Duplicate registration (e.g. a malicious plugin overwriting
  ``trading:pause``) is a startup/configuration error and raises ``ValueError``
  (§33).
* ``IdempotencyRegistry``: a resubmitted idempotency key with the *same*
  command fingerprint returns the previous result; the same key with a
  *different* fingerprint is a ``CommandConflict`` (§28-30).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import CommandConflict


@dataclass(frozen=True)
class _IdempotencyEntry:
    fingerprint: str
    result: Any


class ControlRegistry:
    """All executable control commands must be registered here (§8)."""

    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], Any] = {}

    def register(self, resource: str, action: str, handler: Any) -> None:
        key = (resource, action)
        if key in self._handlers:
            raise ValueError(
                f"control handler already registered: {resource}:{action}"
            )
        self._handlers[key] = handler

    def resolve(self, resource: str, action: str) -> Any:
        key = (resource, action)
        handler = self._handlers.get(key)
        if handler is None:
            raise LookupError(
                f"control handler not found: {resource}:{action}"
            )
        return handler

    def has(self, resource: str, action: str) -> bool:
        return (resource, action) in self._handlers

    def commands(self) -> list[tuple[str, str]]:
        """Sorted (resource, action) keys of all registered commands."""
        return sorted(self._handlers)

    def __len__(self) -> int:
        return len(self._handlers)


class IdempotencyRegistry:
    """Idempotency registry with command-fingerprint conflict detection (§28-30)."""

    def __init__(self) -> None:
        self._entries: dict[str, _IdempotencyEntry] = {}

    def get(self, key: str) -> Any:
        """Return the stored result for ``key`` or ``None`` when absent."""
        entry = self._entries.get(key)
        return entry.result if entry is not None else None

    def put(self, key: str, fingerprint: str, result: Any) -> Any:
        """Store ``result`` under ``key``; enforce fingerprint identity (§29).

        Returns the stored result, so idempotent resubmission returns the
        original result. Raises ``CommandConflict`` when the key is reused
        with a different fingerprint.
        """
        existing = self._entries.get(key)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise CommandConflict(
                    "idempotency key reused with a different command "
                    f"fingerprint: {key}"
                )
            return existing.result
        self._entries[key] = _IdempotencyEntry(
            fingerprint=fingerprint,
            result=result,
        )
        return result
