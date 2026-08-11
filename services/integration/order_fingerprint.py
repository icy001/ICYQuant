"""OrderFingerprint — deterministic hash for deduplication, idempotency, and audit."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .order_intent import OrderIntent


@dataclass
class OrderFingerprint:
    """Deterministic fingerprint of an OrderIntent for deduplication.

    Generated from the key fields that uniquely identify an order.
    Used for: deduplication, idempotency, audit trail integrity.
    """

    fingerprint: str = ""
    intent_id: str = ""
    created_at: float = field(default_factory=lambda: time.time())

    # Track previously seen fingerprints for replay detection
    _seen: Set[str] = field(default_factory=set, repr=False)
    _results: Dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def compute(cls, intent: OrderIntent) -> "OrderFingerprint":
        """Compute fingerprint from intent's identity fields."""
        canonical = {
            "account_id": intent.account_id,
            "strategy_id": intent.strategy_id,
            "symbol": intent.symbol.upper(),
            "side": intent.side.name,
            "quantity": str(intent.quantity),
            "order_type": intent.order_type.name,
            "limit_price": str(intent.limit_price) if intent.limit_price else "",
            "venue": intent.venue.upper() if intent.venue else "",
            "flow_id": intent.flow_id,
        }
        raw = json.dumps(canonical, sort_keys=True)
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return cls(fingerprint=h, intent_id=intent.intent_id)

    @classmethod
    def from_idempotency_key(cls, key: str) -> "OrderFingerprint":
        """Compute fingerprint directly from an idempotency key."""
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return cls(fingerprint=h)

    def is_duplicate(self) -> bool:
        """Check if this fingerprint has been seen before."""
        return self.fingerprint in self._seen

    def mark_seen(self, result_id: str = "") -> None:
        """Record this fingerprint as having been processed."""
        self._seen.add(self.fingerprint)
        if result_id:
            self._results[self.fingerprint] = result_id

    def get_previous_result(self) -> Optional[str]:
        """Return the result_id from a previous admission (idempotency)."""
        return self._results.get(self.fingerprint)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "intent_id": self.intent_id,
            "created_at": self.created_at,
            "seen_count": len(self._seen),
        }

    def __repr__(self) -> str:
        return f"OrderFingerprint(fp={self.fingerprint[:16]}..., intent={self.intent_id})"
