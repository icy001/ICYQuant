"""Circuit breaker for ICYQuant Service Mesh Traffic Management.

Provides ``TrafficCircuitBreaker`` with full state machine:
Closed → Open → Half-Open → Closed, supporting automatic recovery,
failure thresholds, and per-host tracking.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_s: float = 30.0,
        window_s: float = 60.0,
        max_requests_in_half_open: int = 5,
        failure_rate_threshold: float = 0.5,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_s = timeout_s
        self.window_s = window_s
        self.max_requests_in_half_open = max_requests_in_half_open
        self.failure_rate_threshold = failure_rate_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "timeout_s": self.timeout_s,
            "window_s": self.window_s,
            "max_requests_in_half_open": (
                self.max_requests_in_half_open
            ),
            "failure_rate_threshold": self.failure_rate_threshold,
        }


class TrafficCircuitBreaker:
    """Full circuit breaker with state machine."""

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._target = ""
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._opened_at = 0.0
        self._half_open_requests = 0
        self._request_timestamps: List[float] = []
        self._total_requests = 0
        self._total_failures = 0
        self._state_history: List[Dict[str, Any]] = []
        self._event_count = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    def allow_request(self, target: str = "") -> bool:
        """Check if a request is allowed through the circuit."""
        with self._lock:
            self._target = target
            self._clean_window()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if (
                    time.monotonic() - self._opened_at
                    >= self._config.timeout_s
                ):
                    self._transition_to(
                        CircuitState.HALF_OPEN,
                        "timeout_elapsed",
                    )
                    self._half_open_requests = 0
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if (
                    self._half_open_requests
                    < self._config.max_requests_in_half_open
                ):
                    self._half_open_requests += 1
                    return True
                return False

            return False

    def record_success(self) -> None:
        with self._lock:
            self._total_requests += 1
            self._success_count += 1
            self._request_timestamps.append(time.monotonic())

            if self._state == CircuitState.HALF_OPEN:
                if (
                    self._success_count
                    >= self._config.success_threshold
                ):
                    self._transition_to(
                        CircuitState.CLOSED,
                        "success_threshold_reached",
                    )
                    self._failure_count = 0
                    self._success_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._total_requests += 1
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            self._request_timestamps.append(time.monotonic())

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(
                    CircuitState.OPEN,
                    "failure_in_half_open",
                )
                self._opened_at = time.monotonic()
                return

            if self._state == CircuitState.CLOSED:
                if (
                    self._failure_count
                    >= self._config.failure_threshold
                ):
                    self._transition_to(
                        CircuitState.OPEN,
                        "failure_threshold_reached",
                    )
                    self._opened_at = time.monotonic()
                    return

                # Check failure rate
                total = len(self._request_timestamps)
                if total >= 10:
                    rate = self._failure_count / total
                    if rate >= self._config.failure_rate_threshold:
                        self._transition_to(
                            CircuitState.OPEN,
                            "failure_rate_exceeded",
                        )
                        self._opened_at = time.monotonic()

    def _transition_to(
        self, new_state: CircuitState, reason: str
    ) -> None:
        old_state = self._state
        self._state = new_state
        self._event_count += 1
        self._state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-100:]

    def _clean_window(self) -> None:
        now = time.monotonic()
        cutoff = now - self._config.window_s
        self._request_timestamps = [
            t for t in self._request_timestamps if t >= cutoff
        ]
        self._failure_count = len(
            [
                t
                for t in self._request_timestamps
                if t >= self._last_failure_time
            ]
        )

    def reset(self) -> None:
        with self._lock:
            self._transition_to(
                CircuitState.CLOSED, "manual_reset"
            )
            self._failure_count = 0
            self._success_count = 0
            self._half_open_requests = 0
            self._request_timestamps.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._total_requests
            return {
                "state": self._state.value,
                "target": self._target,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_requests": total,
                "total_failures": self._total_failures,
                "failure_rate": (
                    self._total_failures / total
                    if total > 0
                    else 0.0
                ),
                "opened_at": (
                    datetime.fromtimestamp(self._opened_at).isoformat()
                    if self._opened_at
                    else None
                ),
                "event_count": self._event_count,
                "state_history": self._state_history[-5:],
            }
