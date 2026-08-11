"""DeliveryManager — manages request delivery with retries and idempotency."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from .delivery_state import DeliveryState
from .delivery_attempt import DeliveryAttempt
from .delivery_policy import DeliveryPolicy


class DeliveryManager:
    """Manages delivery of requests to the execution gateway.

    Features:
      - Retry with exponential backoff
      - Idempotency (same request_id returns cached result)
      - Request hash validation (detects payload conflicts)
      - Delivery state tracking

    The manager does NOT decide whether to treat a timeout as
    failure — that's the caller's responsibility.
    """

    def __init__(self, policy: Optional[DeliveryPolicy] = None) -> None:
        self._policy = policy or DeliveryPolicy.default()
        self._deliveries: Dict[str, _DeliveryRecord] = {}

    def deliver(self, request_id: str,
                deliver_fn: Callable[[], Any],
                request_hash: str = "") -> Dict:
        """Deliver a request with retries.

        Args:
            request_id: Unique ID for idempotency.
            deliver_fn: Function that performs the actual delivery.
            request_hash: Hash of the request payload (for conflict detection).

        Returns:
            Dict with delivery result.
        """
        # Check idempotency
        if request_id in self._deliveries:
            record = self._deliveries[request_id]
            if request_hash and record.request_hash and \
                    record.request_hash != request_hash:
                return {
                    "success": False,
                    "error_code": "REQUEST_ID_REUSE_CONFLICT",
                    "error_message": f"Request {request_id} reused with different payload",
                }
            if record.state == DeliveryState.ACKNOWLEDGED:
                return {
                    "success": True,
                    "result": record.result,
                    "idempotent": True,
                    "attempts": record.attempts,
                }

        record = _DeliveryRecord(
            request_id=request_id,
            request_hash=request_hash,
            state=DeliveryState.PENDING,
        )

        for attempt_num in range(1, self._policy.max_attempts + 1):
            attempt = DeliveryAttempt(
                attempt_number=attempt_num,
                request_id=request_id,
            )
            start = time.time()

            try:
                result = deliver_fn()
                attempt.latency = time.time() - start
                attempt.success = True
                record.attempts.append(attempt)
                record.state = DeliveryState.ACKNOWLEDGED
                record.result = result
                self._deliveries[request_id] = record
                return {
                    "success": True,
                    "result": result,
                    "attempts": attempt_num,
                }

            except Exception as e:
                attempt.latency = time.time() - start
                attempt.success = False
                error_code = getattr(e, "code", "UNKNOWN_ERROR")
                attempt.error_code = error_code
                attempt.error_message = str(e)
                record.attempts.append(attempt)

                if not self._policy.is_retryable(error_code):
                    record.state = DeliveryState.FAILED
                    self._deliveries[request_id] = record
                    return {
                        "success": False,
                        "error_code": error_code,
                        "error_message": str(e),
                        "attempts": attempt_num,
                    }

                if attempt_num < self._policy.max_attempts:
                    record.state = DeliveryState.RETRYING
                    backoff = self._policy.get_backoff_ms(attempt_num + 1)
                    time.sleep(backoff / 1000.0)
                else:
                    record.state = DeliveryState.UNKNOWN

        record.state = DeliveryState.UNKNOWN
        self._deliveries[request_id] = record
        return {
            "success": False,
            "error_code": "MAX_RETRIES_EXCEEDED",
            "error_message": "Maximum delivery attempts exceeded",
            "attempts": len(record.attempts),
            "state": record.state.name,
        }

    def get_state(self, request_id: str) -> Optional[DeliveryState]:
        record = self._deliveries.get(request_id)
        return record.state if record else None

    def get_attempts(self, request_id: str) -> List[DeliveryAttempt]:
        record = self._deliveries.get(request_id)
        return record.attempts if record else []


class _DeliveryRecord:
    """Internal record of a delivery."""

    def __init__(self, request_id: str, request_hash: str,
                 state: DeliveryState) -> None:
        self.request_id = request_id
        self.request_hash = request_hash
        self.state = state
        self.attempts: List[DeliveryAttempt] = []
        self.result: Any = None
