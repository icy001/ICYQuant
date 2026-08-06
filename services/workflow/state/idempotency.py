"""Idempotency manager — guarantees same request always produces same result.

Based on execution ID, node ID, request hash, and retry tokens to
ensure that replayed or retried requests do not cause side effects.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyKey:
    """Composite key for idempotency checks."""

    execution_id: str
    node_id: str
    request_hash: str
    retry_token: Optional[str] = None

    @property
    def composite_key(self) -> str:
        parts = [self.execution_id, self.node_id, self.request_hash]
        if self.retry_token:
            parts.append(self.retry_token)
        return ":".join(parts)


@dataclass
class IdempotencyRecord:
    """Record of a completed idempotent operation."""

    key: IdempotencyKey
    result: Optional[Dict[str, Any]] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class IdempotencyManager:
    """Manages idempotency for workflow operations.

    Guarantees:
      - Same request → Execute once
      - Retries with same token → Return cached result
      - Different retry token → Re-execute (new attempt)
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._records: Dict[str, IdempotencyRecord] = {}
        self._ttl_seconds = ttl_seconds

    # ---- Core API -----------------------------------------------------------

    async def check_and_record(
        self,
        execution_id: str,
        node_id: str,
        request_payload: Dict[str, Any],
        retry_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Check if operation already completed.

        Returns:
          - None: operation not yet executed, caller should proceed
          - Dict: cached result from prior execution, caller should return it
        """
        request_hash = self._hash_payload(request_payload)
        key = IdempotencyKey(
            execution_id=execution_id,
            node_id=node_id,
            request_hash=request_hash,
            retry_token=retry_token,
        )

        composite = key.composite_key
        existing = self._records.get(composite)
        if existing is not None:
            logger.info("Idempotent hit: %s", composite)
            return existing.result
        return None

    async def record_result(
        self,
        execution_id: str,
        node_id: str,
        request_payload: Dict[str, Any],
        result: Dict[str, Any],
        retry_token: Optional[str] = None,
    ) -> None:
        """Record the result of a completed operation for future idempotency."""
        request_hash = self._hash_payload(request_payload)
        key = IdempotencyKey(
            execution_id=execution_id,
            node_id=node_id,
            request_hash=request_hash,
            retry_token=retry_token,
        )
        record = IdempotencyRecord(key=key, result=result)
        self._records[key.composite_key] = record
        logger.debug("Idempotency recorded: %s", key.composite_key)

    async def invalidate(self, execution_id: str, node_id: str = "") -> None:
        """Invalidate idempotency records for an execution/node."""
        prefix = f"{execution_id}:{node_id}" if node_id else execution_id
        to_remove = [k for k in self._records if k.startswith(prefix)]
        for k in to_remove:
            self._records.pop(k, None)
        logger.info("Invalidated %d idempotency records for %s", len(to_remove), prefix)

    # ---- Cleanup ------------------------------------------------------------

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [
            k for k, r in self._records.items()
            if (now - r.completed_at).total_seconds() > self._ttl_seconds
        ]
        for k in expired:
            self._records.pop(k, None)
        return len(expired)

    # ---- Internal -----------------------------------------------------------

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        raw = str(sorted(payload.items()))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
