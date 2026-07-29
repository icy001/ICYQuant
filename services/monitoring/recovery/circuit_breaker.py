"""Circuit Breaker.

Prevents cascading failures by detecting when a downstream service
is failing and temporarily blocking calls to it.

States:
    CLOSED → OPEN → HALF_OPEN → CLOSED

Based on the Circuit Breaker pattern (Michael Nygard, "Release It!").

Usage::

    cb = CircuitBreaker(
        name="broker_gateway",
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    @cb.protect
    def call_broker(order):
        ...

    # Or manual:
    if cb.allow_request():
        try:
            result = call_broker(order)
            cb.on_success()
        except Exception:
            cb.on_failure()
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, Enum):
    CLOSED = "closed"          # Normal operation, requests pass through
    OPEN = "open"              # Failing, requests are blocked
    HALF_OPEN = "half_open"    # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker."""

    name: str
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    opened_at: Optional[float] = None
    state_changes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "opened_at": self.opened_at,
            "state_changes": self.state_changes,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""
    pass


class CircuitBreaker:
    """Circuit breaker for protecting downstream service calls.

    States:
    - CLOSED: Normal operation. After N failures, transitions to OPEN.
    - OPEN: Requests are blocked for recovery_timeout seconds.
      Then transitions to HALF_OPEN.
    - HALF_OPEN: Allows one probe request.
      Success → CLOSED, Failure → OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 1,
        on_open: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_requests = half_open_max_requests

        self.state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._half_open_requests: int = 0
        self._last_failure_time: float = 0.0
        self._opened_at: Optional[float] = None
        self._total_failures: int = 0
        self._total_successes: int = 0
        self._state_changes: int = 0

        self._on_open = on_open
        self._on_close = on_close

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._should_attempt_half_open():
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_requests = 0
            else:
                return False

        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_requests < self._half_open_max_requests:
                self._half_open_requests += 1
                return True
            return False

        return False

    def on_success(self) -> None:
        """Record a successful request."""
        self._total_successes += 1
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self._failure_count = 0

    def on_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif (
            self.state == CircuitState.CLOSED
            and self._failure_count >= self._failure_threshold
        ):
            self._transition_to(CircuitState.OPEN)

    def protect(self, func: F) -> F:
        """Decorator to protect a function with this circuit breaker."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is {self.state.value}"
                )
            try:
                result = func(*args, **kwargs)
                self.on_success()
                return result
            except Exception:
                self.on_failure()
                raise

        return wrapper  # type: ignore[return-value]

    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED."""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        self._half_open_requests = 0

    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics."""
        return CircuitBreakerStats(
            name=self.name,
            state=self.state,
            failure_count=self._failure_count,
            success_count=self._total_successes,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            last_failure_time=self._last_failure_time,
            last_success_time=time.time() if self.state == CircuitState.CLOSED else 0.0,
            opened_at=self._opened_at,
            state_changes=self._state_changes,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self.state
        self.state = new_state
        self._state_changes += 1

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            if self._on_open:
                self._on_open(self.name)
        elif new_state == CircuitState.CLOSED and old_state != CircuitState.CLOSED:
            if self._on_close:
                self._on_close(self.name)

    def _should_attempt_half_open(self) -> bool:
        if self._opened_at is None:
            return True
        return (time.time() - self._opened_at) >= self._recovery_timeout


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}

    def register(self, breaker: CircuitBreaker) -> None:
        """Register a circuit breaker."""
        self._breakers[breaker.name] = breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        """Get an existing breaker or create a new one."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    def get_all_stats(self) -> List[CircuitBreakerStats]:
        """Get stats for all registered circuit breakers."""
        return [b.get_stats() for b in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def status_summary(self) -> Dict[str, Any]:
        """Get a summary of all circuit breaker states."""
        stats = self.get_all_stats()
        return {
            "total": len(stats),
            "open": sum(1 for s in stats if s.state == CircuitState.OPEN),
            "half_open": sum(1 for s in stats if s.state == CircuitState.HALF_OPEN),
            "closed": sum(1 for s in stats if s.state == CircuitState.CLOSED),
            "details": {s.name: s.state.value for s in stats},
        }
