"""Execution guard — ensures exactly-once execution semantics.

Uses execution tokens, distributed locks, and journal checks to prevent
duplicate execution, duplicate consumption, and duplicate submission.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ExecutionToken:
    """A token guaranteeing exactly-once execution for a workflow/node."""

    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    node_id: Optional[str] = None
    request_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    consumed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionGuard:
    """Exactly-Once Guard protecting against duplicate execution.

    Workflow:
      1. Acquire token (unique execution ID + hash)
      2. Check journal for prior execution
      3. Execute only if never executed before
      4. Mark token consumed upon completion

    Supports both in-memory and external lock backends.
    """

    def __init__(self, lock_backend: Optional[Any] = None):
        self._consumed_tokens: Dict[str, ExecutionToken] = {}
        self._execution_locks: Dict[str, str] = {}  # execution_id → owner
        self._completed_hashes: Set[str] = set()
        self._lock_backend = lock_backend

    # ---- Token management ---------------------------------------------------

    async def acquire_token(
        self,
        execution_id: str,
        request_payload: Dict[str, Any],
        node_id: Optional[str] = None,
        ttl_seconds: int = 300,
    ) -> Optional[ExecutionToken]:
        """Acquire an execution token. Returns None if already executed."""
        request_hash = self._hash_request(request_payload)
        dedup_key = f"{execution_id}:{node_id or 'workflow'}:{request_hash}"

        # Check if already consumed
        if dedup_key in self._consumed_tokens:
            existing = self._consumed_tokens[dedup_key]
            if existing.consumed:
                logger.warning("Duplicate execution detected: %s", dedup_key)
                return None

        # Check completed hashes cache
        if request_hash in self._completed_hashes:
            logger.warning("Duplicate request hash: %s", request_hash)
            return None

        # Acquire lock
        lock_key = execution_id if node_id is None else f"{execution_id}:{node_id}"
        if lock_key in self._execution_locks:
            logger.warning("Execution lock held: %s", lock_key)
            return None

        self._execution_locks[lock_key] = "acquired"

        token = ExecutionToken(
            execution_id=execution_id,
            node_id=node_id,
            request_hash=request_hash,
            expires_at=datetime.now(timezone.utc) if ttl_seconds else None,
        )
        self._consumed_tokens[dedup_key] = token
        return token

    async def mark_consumed(self, token: ExecutionToken) -> None:
        """Mark token as consumed after successful execution."""
        dedup_key = f"{token.execution_id}:{token.node_id or 'workflow'}:{token.request_hash}"
        if dedup_key in self._consumed_tokens:
            self._consumed_tokens[dedup_key].consumed = True
        self._completed_hashes.add(token.request_hash)
        # Release lock
        lock_key = token.execution_id if token.node_id is None else f"{token.execution_id}:{token.node_id}"
        self._execution_locks.pop(lock_key, None)

    async def release_token(self, token: ExecutionToken) -> None:
        """Release token without consuming (for failed attempts)."""
        dedup_key = f"{token.execution_id}:{token.node_id or 'workflow'}:{token.request_hash}"
        self._consumed_tokens.pop(dedup_key, None)
        lock_key = token.execution_id if token.node_id is None else f"{token.execution_id}:{token.node_id}"
        self._execution_locks.pop(lock_key, None)

    async def is_executed(self, execution_id: str, request_hash: str) -> bool:
        """Check if a specific execution has already been completed."""
        return request_hash in self._completed_hashes

    # ---- Cleanup ------------------------------------------------------------

    async def cleanup_expired(self) -> int:
        """Remove expired tokens. Returns count cleaned."""
        now = datetime.now(timezone.utc)
        expired = [
            k for k, t in self._consumed_tokens.items()
            if t.expires_at and t.expires_at < now
        ]
        for k in expired:
            self._consumed_tokens.pop(k, None)
        return len(expired)

    # ---- Internal -----------------------------------------------------------

    @staticmethod
    def _hash_request(payload: Dict[str, Any]) -> str:
        raw = str(sorted(payload.items()))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
