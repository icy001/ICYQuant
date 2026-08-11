"""AdmissionDeduplicator — prevents duplicate orders via fingerprint and idempotency keys.

Uses OrderFingerprint to detect exact duplicates AND idempotency keys to
return previous admission results for retried requests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from .order_intent import OrderIntent
from .order_fingerprint import OrderFingerprint
from .admission_result import AdmissionResult


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool = False
    existing_result_id: str = ""
    fingerprint: str = ""
    message: str = ""


@dataclass
class AdmissionDeduplicator:
    """Detects and prevents duplicate order submissions.

    Two layers of protection:
    1. OrderFingerprint: exact content hash match → DUPLICATE (prevent double submission)
    2. Idempotency Key: same flow:order key → return previous result (retry safety)
    """

    # In-memory stores. In production, these would be backed by Redis/DB.
    _seen_fingerprints: Set[str] = field(default_factory=set, repr=False)
    _idempotency_results: Dict[str, Dict[str, Any]] = field(default_factory=dict, repr=False)

    # TTL for idempotency results (seconds)
    idempotency_ttl: float = 3600.0

    def check_duplicate(
        self, intent: OrderIntent, idempotency_key: str = ""
    ) -> DeduplicationResult:
        """Check if this intent is a duplicate."""
        fp = OrderFingerprint.compute(intent)

        # Layer 1: Check idempotency key first (exact retry)
        if idempotency_key:
            cached = self._idempotency_results.get(idempotency_key)
            if cached:
                age = time.time() - cached.get("timestamp", 0)
                if age < self.idempotency_ttl:
                    return DeduplicationResult(
                        is_duplicate=True,
                        existing_result_id=cached.get("result_id", ""),
                        fingerprint=fp.fingerprint,
                        message=f"Idempotent retry: returning previous result {cached.get('result_id', '')}",
                    )

        # Layer 2: Check fingerprint (exact content match)
        if fp.fingerprint in self._seen_fingerprints:
            return DeduplicationResult(
                is_duplicate=True,
                fingerprint=fp.fingerprint,
                message="Duplicate order detected: same fingerprint already submitted",
            )

        # Not a duplicate — record
        fp.mark_seen()
        self._seen_fingerprints.add(fp.fingerprint)

        return DeduplicationResult(fingerprint=fp.fingerprint)

    def store_idempotency_result(
        self, key: str, result: AdmissionResult
    ) -> None:
        """Store admission result for idempotency key."""
        self._idempotency_results[key] = {
            "result_id": result.result_id,
            "status": result.status.name,
            "order_id": result.order_id,
            "timestamp": time.time(),
        }

    def get_idempotency_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a previously stored idempotency result."""
        cached = self._idempotency_results.get(key)
        if not cached:
            return None
        age = time.time() - cached.get("timestamp", 0)
        if age > self.idempotency_ttl:
            del self._idempotency_results[key]
            return None
        return cached

    def clear_expired(self) -> int:
        """Remove expired idempotency entries. Returns count removed."""
        now = time.time()
        expired = [
            k for k, v in self._idempotency_results.items()
            if now - v.get("timestamp", 0) > self.idempotency_ttl
        ]
        for k in expired:
            del self._idempotency_results[k]
        return len(expired)

    def reset(self) -> None:
        """Clear all stored state (for testing)."""
        self._seen_fingerprints.clear()
        self._idempotency_results.clear()

    def __repr__(self) -> str:
        return (
            f"AdmissionDeduplicator(seen_fingerprints={len(self._seen_fingerprints)}, "
            f"idempotency_keys={len(self._idempotency_results)})"
        )
