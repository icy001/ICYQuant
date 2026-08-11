"""ExecutionRequest — OMS → Execution submission request."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionRequest:
    """A request to submit an order to the execution layer.

    Identity:
        request_id: Unique ID for this request (used for idempotency).
        order_id: The OMS order being submitted.

    The request_hash ensures that retries with the same request_id
    but different payload are detected as conflicts.
    """

    request_id: str = field(
        default_factory=lambda: f"EXREQ-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    order_id: str = ""
    client_order_id: str = ""

    # Order details
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    order_type: str = ""
    price: float = 0.0
    time_in_force: str = "DAY"

    # Routing
    routing_policy: str = ""
    venue: str = ""

    # Lineage
    lineage_id: str = ""
    certificate_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""

    # Timing
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    expires_at: Optional[float] = None

    # Computed
    request_hash: str = ""

    def __post_init__(self) -> None:
        if not self.request_hash:
            self.request_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps({
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
        }, sort_keys=True)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        return self.request_hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
            "time_in_force": self.time_in_force,
            "routing_policy": self.routing_policy,
            "venue": self.venue,
            "lineage_id": self.lineage_id,
            "certificate_id": self.certificate_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "request_hash": self.request_hash,
        }


@dataclass
class CancelRequest:
    """A request to cancel an order at the execution layer."""

    cancel_request_id: str = field(
        default_factory=lambda: f"CXREQ-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    order_id: str = ""
    request_id: str = ""  # original submission request_id
    reason: str = ""
    cancel_quantity: float = 0.0

    lineage_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cancel_request_id": self.cancel_request_id,
            "order_id": self.order_id,
            "request_id": self.request_id,
            "reason": self.reason,
            "cancel_quantity": self.cancel_quantity,
            "lineage_id": self.lineage_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp,
        }
