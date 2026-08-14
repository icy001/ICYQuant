"""Execution claim — ownership, lease and fencing token (Commit 29 Part 1.4 §20-27, §51-52).

Deduplication alone is not enough: two workers can both see *Not Found* for
the same key. An atomic Execution Claim plus a fencing token makes execution
ownership explicit (§20-22). A claim is never a permanent lock — the worker
must heartbeat to keep the lease alive (§24), and a database lock alone can
never prove business ownership (§25).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ExecutionClaim:
    """Proof that one worker owns a command for a bounded time (§21)."""

    claim_id: str
    command_id: str
    worker_id: str
    acquired_at: datetime
    expires_at: datetime
    fencing_token: int

    def is_expired(self, now: datetime | None = None) -> bool:
        """True when the lease has elapsed (§24)."""
        return self.expires_at <= (now or datetime.now(timezone.utc))


@dataclass(frozen=True)
class ClaimResult:
    """Result of an acquisition attempt (§23)."""

    acquired: bool
    claim: ExecutionClaim | None = None
    error_code: str = "CLAIM_ALREADY_HELD"
    reason: str = ""


class ExecutionClaimStore:
    """Atomic claim acquisition with lease and fencing token (§22-24).

    When a lease expires the claim may be taken over by a recovery worker
    with a *higher* fencing token. A zombie worker that wakes up later with
    its old token can never write — targets only accept
    ``token >= current_token`` (§22).
    """

    def __init__(self, *, lease_seconds: int = 30) -> None:
        self.lease_seconds = lease_seconds
        self._claims: dict[str, ExecutionClaim] = {}
        self._tokens: dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        command_id: str,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int | None = None,
    ) -> ExecutionClaim | None:
        """Acquire the claim, or None while it is still held (§23, §51)."""
        result = self.acquire_with_result(
            command_id,
            worker_id,
            now=now,
            lease_seconds=lease_seconds,
        )
        return result.claim if result.acquired else None

    def acquire_with_result(
        self,
        command_id: str,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int | None = None,
    ) -> ClaimResult:
        """Acquire with a structured result (CLAIM_ACQUIRED / CLAIM_ALREADY_HELD)."""
        reference = now or datetime.now(timezone.utc)
        lease = lease_seconds if lease_seconds is not None else self.lease_seconds
        with self._lock:
            current = self._claims.get(command_id)
            if current is not None and not current.is_expired(reference):
                return ClaimResult(
                    acquired=False,
                    claim=current,
                    error_code="CLAIM_ALREADY_HELD",
                    reason=f"command {command_id} is claimed by {current.worker_id}",
                )
            token = self._tokens.get(command_id, 0) + 1
            claim = ExecutionClaim(
                claim_id=f"CLAIM-{command_id}-{token}",
                command_id=command_id,
                worker_id=worker_id,
                acquired_at=reference,
                expires_at=reference + timedelta(seconds=lease),
                fencing_token=token,
            )
            self._claims[command_id] = claim
            self._tokens[command_id] = token
            return ClaimResult(
                acquired=True,
                claim=claim,
                error_code="CLAIM_ACQUIRED",
                reason="claim acquired",
            )

    def heartbeat(
        self,
        command_id: str,
        worker_id: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Extend the lease; False when held by another worker (§24)."""
        reference = now or datetime.now(timezone.utc)
        with self._lock:
            current = self._claims.get(command_id)
            if current is None or current.worker_id != worker_id:
                return False
            renewed = ExecutionClaim(
                claim_id=current.claim_id,
                command_id=current.command_id,
                worker_id=current.worker_id,
                acquired_at=current.acquired_at,
                expires_at=reference + timedelta(seconds=self.lease_seconds),
                fencing_token=current.fencing_token,
            )
            self._claims[command_id] = renewed
            return True

    def release(self, command_id: str, worker_id: str) -> bool:
        """Release the claim; False when not held by ``worker_id``."""
        with self._lock:
            current = self._claims.get(command_id)
            if current is None or current.worker_id != worker_id:
                return False
            del self._claims[command_id]
            return True

    def current_fencing_token(self, command_id: str) -> int:
        """The highest token ever issued for ``command_id`` (§22)."""
        return self._tokens.get(command_id, 0)

    def get(self, command_id: str) -> ExecutionClaim | None:
        """The current claim (possibly expired) for ``command_id``."""
        with self._lock:
            return self._claims.get(command_id)


__all__ = ["ClaimResult", "ExecutionClaim", "ExecutionClaimStore"]
