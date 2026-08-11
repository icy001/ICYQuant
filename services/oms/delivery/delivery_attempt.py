"""DeliveryAttempt — records a single delivery attempt."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeliveryAttempt:
    """A single attempt to deliver a request."""

    attempt_number: int = 1
    request_id: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    latency: float = 0.0
    success: bool = False
    error_code: str = ""
    error_message: str = ""
    response_id: str = ""

    @classmethod
    def success(cls, attempt_number: int, request_id: str,
                response_id: str = "", latency: float = 0) -> "DeliveryAttempt":
        return cls(
            attempt_number=attempt_number,
            request_id=request_id,
            success=True,
            response_id=response_id,
            latency=latency,
        )

    @classmethod
    def failure(cls, attempt_number: int, request_id: str,
                error_code: str, error_message: str = "",
                latency: float = 0) -> "DeliveryAttempt":
        return cls(
            attempt_number=attempt_number,
            request_id=request_id,
            success=False,
            error_code=error_code,
            error_message=error_message,
            latency=latency,
        )
