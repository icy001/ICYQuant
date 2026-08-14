"""Idempotency key — stable business identity of a control operation (Commit 29 Part 1.4 §3-5).

A request id identifies a single message; an idempotency key identifies a
single business operation — many request ids may belong to one key (§5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class IdempotencyKey:
    """(value, principal_id) together form the unique request identity (§4)."""

    value: str
    created_at: datetime
    principal_id: str

    def identity(self) -> tuple[str, str]:
        """The composite (value, principal_id) used for uniqueness checks (§4)."""
        return (self.value, self.principal_id)

    def is_expired(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        """True when the key is older than ``ttl_seconds`` (§42)."""
        reference = now or datetime.now(timezone.utc)
        return (reference - self.created_at).total_seconds() > ttl_seconds
