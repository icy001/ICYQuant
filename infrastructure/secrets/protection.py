"""
Secrets self-protection.

Provides protection mechanisms for secrets
operations, including rate limiting, circuit
breaker for provider failures, automatic
provider failover, and access denial protection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RateLimitEntry:
    """
    Rate limit tracking entry.

    Attributes:
        timestamp: When the operation occurred.
        operation: Operation type.
        key: Target secret key.
    """

    timestamp: float = 0.0
    operation: str = ""
    key: str = ""


@dataclass
class ProtectionEvent:
    """
    A protection event record.

    Attributes:
        event_type: Type of protection event.
        timestamp: When the event occurred.
        details: Additional event details.
    """

    event_type: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() + "Z",
            "details": self.details,
        }


class SecretsProtection:
    """
    Secrets self-protection manager.

    Provides rate limiting, circuit breaker,
    automatic provider failover, and access
    denial protection for secrets operations.

    Usage:
        protection = SecretsProtection()
        if protection.allow_operation("read", "db/password"):
            # perform operation
            protection.on_success()
        else:
            protection.on_failure()
    """

    def __init__(
        self,
        rate_limit: int = 100,
        rate_window: float = 60.0,
        circuit_threshold: int = 5,
        circuit_reset_timeout: float = 30.0,
        half_open_max_requests: int = 3,
        max_history: int = 500,
    ) -> None:
        """
        Initialize secrets protection.

        Args:
            rate_limit: Max operations per window.
            rate_window: Time window in seconds.
            circuit_threshold: Failures before opening circuit.
            circuit_reset_timeout: Seconds before half-open.
            half_open_max_requests: Max requests in half-open.
            max_history: Maximum history entries.
        """
        self._rate_limit = rate_limit
        self._rate_window = rate_window
        self._circuit_threshold = circuit_threshold
        self._circuit_reset_timeout = circuit_reset_timeout
        self._half_open_max_requests = half_open_max_requests
        self._max_history = max_history

        self._lock = threading.RLock()

        # Rate limiting
        self._rate_entries: deque[RateLimitEntry] = deque()
        self._operation_counts: Dict[str, int] = {}

        # Circuit breaker
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None

        # Provider failover
        self._primary_provider: Optional[str] = None
        self._secondary_providers: List[str] = []
        self._current_provider: Optional[str] = None
        self._failover_count = 0

        # Access denial tracking
        self._denied_operations: Dict[str, int] = {}
        self._blocked_keys: Dict[str, float] = {}

        # Event history
        self._events: List[ProtectionEvent] = []
        self._on_circuit_event: Optional[Callable[[CircuitState], None]] = None
        self._on_rate_limit: Optional[Callable[[str, str], None]] = None
        self._on_failover: Optional[Callable[[str, str], None]] = None

        # Statistics
        self._total_allowed = 0
        self._total_denied = 0
        self._total_failures = 0
        self._total_successes = 0

    # ── Configuration ──

    def set_providers(
        self,
        primary: str,
        secondary: Optional[List[str]] = None,
    ) -> None:
        """
        Set primary and secondary providers.

        Args:
            primary: Primary provider name.
            secondary: List of secondary provider names.
        """
        with self._lock:
            self._primary_provider = primary
            self._current_provider = primary
            self._secondary_providers = secondary or []

    def set_on_circuit_event(
        self,
        callback: Callable[[CircuitState], None],
    ) -> None:
        """
        Set circuit breaker event callback.

        Args:
            callback: Called when circuit state changes.
        """
        self._on_circuit_event = callback

    def set_on_rate_limit(
        self,
        callback: Callable[[str, str], None],
    ) -> None:
        """
        Set rate limit exceeded callback.

        Args:
            callback: Called when rate limit is exceeded.
        """
        self._on_rate_limit = callback

    def set_on_failover(
        self,
        callback: Callable[[str, str], None],
    ) -> None:
        """
        Set failover callback.

        Args:
            callback: Called on provider failover.
        """
        self._on_failover = callback

    # ── Operation Control ──

    def allow_operation(
        self,
        operation: str,
        key: str = "",
    ) -> bool:
        """
        Check if an operation is allowed.

        Evaluates rate limits, circuit breaker state,
        and access denial protections.

        Args:
            operation: Operation type (read, write, etc.).
            key: Target secret key.

        Returns:
            True if operation is allowed.
        """
        with self._lock:
            now = time.time()

            # Check circuit breaker
            if self._circuit_state == CircuitState.OPEN:
                if not self._check_circuit_timeout():
                    self._emit_event(
                        "circuit_blocked",
                        {"operation": operation, "key": key},
                    )
                    self._total_denied += 1
                    return False

            # Check blocked keys
            if key and key in self._blocked_keys:
                if now < self._blocked_keys[key]:
                    self._emit_event(
                        "key_blocked",
                        {"operation": operation, "key": key},
                    )
                    self._total_denied += 1
                    return False
                else:
                    del self._blocked_keys[key]

            # Check rate limit
            self._cleanup_rate_entries(now)
            recent_count = sum(
                1 for e in self._rate_entries if e.operation == operation
            )
            if recent_count >= self._rate_limit:
                self._emit_event(
                    "rate_limited",
                    {"operation": operation, "key": key},
                )
                if self._on_rate_limit:
                    try:
                        self._on_rate_limit(operation, key)
                    except Exception as e:
                        logger.error("Rate limit callback error: %s", e)
                self._total_denied += 1
                return False

            # Allow operation
            self._rate_entries.append(
                RateLimitEntry(timestamp=now, operation=operation, key=key)
            )

            if self._circuit_state == CircuitState.HALF_OPEN:
                self._half_open_requests += 1

            self._total_allowed += 1
            return True

    def on_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self._success_count += 1
            self._last_success_time = datetime.utcnow()
            self._total_successes += 1

            if self._circuit_state == CircuitState.HALF_OPEN:
                self._close_circuit()

    def on_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()
            self._total_failures += 1

            if self._circuit_state == CircuitState.HALF_OPEN:
                self._open_circuit()
            elif self._failure_count >= self._circuit_threshold:
                self._open_circuit()

    # ── Circuit Breaker ──

    def _check_circuit_timeout(self) -> bool:
        """Check if circuit breaker timeout has elapsed."""
        if self._last_failure_time:
            elapsed = (
                datetime.utcnow() - self._last_failure_time
            ).total_seconds()
            if elapsed >= self._circuit_reset_timeout:
                self._transition_circuit(CircuitState.HALF_OPEN)
                self._half_open_requests = 0
                return True
        return False

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        if self._circuit_state != CircuitState.OPEN:
            self._transition_circuit(CircuitState.OPEN)
            self._last_failure_time = datetime.utcnow()
            self._emit_event(
                "circuit_opened",
                {"failure_count": self._failure_count},
            )
            logger.warning(
                "Circuit breaker OPENED after %d failures",
                self._failure_count,
            )

    def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        if self._circuit_state != CircuitState.CLOSED:
            self._transition_circuit(CircuitState.CLOSED)
            self._failure_count = 0
            self._emit_event("circuit_closed", {})
            logger.info("Circuit breaker CLOSED")

    def _transition_circuit(self, new_state: CircuitState) -> None:
        """Transition to new circuit state."""
        old_state = self._circuit_state
        self._circuit_state = new_state

        if self._on_circuit_event:
            try:
                self._on_circuit_event(new_state)
            except Exception as e:
                logger.error("Circuit callback error: %s", e)

        logger.debug(
            "Circuit: %s -> %s", old_state.value, new_state.value
        )

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.

        Returns:
            Circuit status dictionary.
        """
        with self._lock:
            return {
                "state": self._circuit_state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_requests": self._half_open_requests,
                "threshold": self._circuit_threshold,
                "reset_timeout": self._circuit_reset_timeout,
                "last_failure": (
                    self._last_failure_time.isoformat() + "Z"
                    if self._last_failure_time
                    else None
                ),
                "last_success": (
                    self._last_success_time.isoformat() + "Z"
                    if self._last_success_time
                    else None
                ),
            }

    def reset_circuit(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._close_circuit()

    # ── Provider Failover ──

    def failover(self) -> Optional[str]:
        """
        Trigger provider failover.

        Switches to the next available provider
        in the secondary list.

        Returns:
            New provider name or None if no fallback.
        """
        with self._lock:
            old_provider = self._current_provider

            if not self._secondary_providers:
                logger.warning("No secondary providers for failover")
                return None

            if self._current_provider in self._secondary_providers:
                idx = self._secondary_providers.index(self._current_provider)
                if idx + 1 < len(self._secondary_providers):
                    self._current_provider = self._secondary_providers[idx + 1]
                else:
                    self._current_provider = self._primary_provider
            else:
                self._current_provider = self._secondary_providers[0]

            self._failover_count += 1
            self._emit_event(
                "failover",
                {"from": old_provider, "to": self._current_provider},
            )

            if self._on_failover and old_provider and self._current_provider:
                try:
                    self._on_failover(old_provider, self._current_provider)
                except Exception as e:
                    logger.error("Failover callback error: %s", e)

            logger.info(
                "Provider failover: %s -> %s",
                old_provider,
                self._current_provider,
            )
            return self._current_provider

    @property
    def current_provider(self) -> Optional[str]:
        """Get current active provider."""
        with self._lock:
            return self._current_provider

    # ── Access Denial Protection ──

    def block_key(
        self,
        key: str,
        duration: float = 300.0,
    ) -> None:
        """
        Block a specific key from operations.

        Args:
            key: Secret key to block.
            duration: Block duration in seconds.
        """
        with self._lock:
            self._blocked_keys[key] = time.time() + duration
            self._denied_operations[key] = (
                self._denied_operations.get(key, 0) + 1
            )
            self._emit_event(
                "key_blocked",
                {"key": key, "duration": duration},
            )
            logger.warning("Key blocked: %s for %.0fs", key, duration)

    def unblock_key(self, key: str) -> None:
        """
        Unblock a specific key.

        Args:
            key: Secret key to unblock.
        """
        with self._lock:
            self._blocked_keys.pop(key, None)
            self._emit_event("key_unblocked", {"key": key})

    def get_blocked_keys(self) -> List[Dict[str, Any]]:
        """
        Get currently blocked keys.

        Returns:
            List of blocked key info dicts.
        """
        with self._lock:
            now = time.time()
            result = []
            for key, expires_at in self._blocked_keys.items():
                remaining = max(0.0, expires_at - now)
                result.append({
                    "key": key,
                    "expires_at": datetime.fromtimestamp(expires_at).isoformat() + "Z",
                    "remaining_seconds": remaining,
                })
            return result

    # ── Rate Limit Management ──

    def _cleanup_rate_entries(self, now: float) -> None:
        """Remove expired rate limit entries."""
        cutoff = now - self._rate_window
        while self._rate_entries and self._rate_entries[0].timestamp < cutoff:
            self._rate_entries.popleft()

    def get_rate_stats(self) -> Dict[str, Any]:
        """
        Get rate limiting statistics.

        Returns:
            Rate stats dictionary.
        """
        with self._lock:
            now = time.time()
            self._cleanup_rate_entries(now)
            operation_counts: Dict[str, int] = {}
            for entry in self._rate_entries:
                operation_counts[entry.operation] = (
                    operation_counts.get(entry.operation, 0) + 1
                )
            return {
                "rate_limit": self._rate_limit,
                "rate_window": self._rate_window,
                "current_counts": operation_counts,
                "total_entries": len(self._rate_entries),
            }

    # ── Events ──

    def _emit_event(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a protection event."""
        event = ProtectionEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            details=details or {},
        )
        self._events.append(event)
        if len(self._events) > self._max_history:
            self._events = self._events[-self._max_history:]

    def get_events(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get protection event history.

        Args:
            limit: Maximum number of events.

        Returns:
            List of protection events.
        """
        with self._lock:
            return [e.to_dict() for e in reversed(self._events[-limit:])]

    # ── Stats ──

    def get_stats(self) -> Dict[str, Any]:
        """
        Get protection statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            return {
                "circuit": self.get_circuit_status(),
                "rate_limit": self.get_rate_stats(),
                "providers": {
                    "primary": self._primary_provider,
                    "current": self._current_provider,
                    "secondary": list(self._secondary_providers),
                    "failover_count": self._failover_count,
                },
                "access": {
                    "total_allowed": self._total_allowed,
                    "total_denied": self._total_denied,
                    "blocked_keys_count": len(self._blocked_keys),
                },
                "operations": {
                    "total_successes": self._total_successes,
                    "total_failures": self._total_failures,
                },
                "events_count": len(self._events),
            }