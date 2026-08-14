"""Duplicate detection results and conflict error (Commit 29 Part 1.4 §15-17, §38-39).

Duplicate and conflict must never be conflated (§15)::

    same key + same fingerprint     -> DUPLICATE
    same key + different fingerprint -> IDEMPOTENCY_CONFLICT
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import IdempotencyConflict


@dataclass(frozen=True)
class IdempotencyResult:
    """Outcome of an idempotent submission (§38-39).

    First submission:      duplicate=False, conflict=False
    Repeated submission:   duplicate=True,  conflict=False
    Key reused w/ mismatch: duplicate=False, conflict=True
    """

    command_id: str
    state: str
    duplicate: bool = False
    conflict: bool = False
    error_code: str | None = None
    error_message: str | None = None


__all__ = ["IdempotencyConflict", "IdempotencyResult"]
