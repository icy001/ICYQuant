"""
Configuration platform self-protection.

Protects the platform from instability through:
- Reload rate limiting
- Validation failure detection
- Circuit breaker pattern
- Automatic rollback on persistent failures

Protection Flow:
    Reload Request
        ↓
    Rate Limit Check
        ↓
    Validation Check
        ↓
    Circuit Breaker
        ↓
    Allow or Reject
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState:
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, rejecting requests
    HALF_OPEN = "half_open" # Testing if recovered


class ConfigurationProtection:
    """
    Configuration platform protection manager.

    Implements multiple protection mechanisms:
    1. Rate limiting for reload requests
    2. Circuit breaker for repeated failures
    3. Automatic rollback on persistent errors

    Usage:
        protection = ConfigurationProtection()
        if await protection.allow_reload():
            # Execute reload
            result = reload()
            if not result.success:
                await protection.on_failure(result.errors)
        else:
            # Reload rejected
    """

    def __init__(
        self,
        max_reload_per_minute: int = 10,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        enable_auto_rollback: bool = True,
    ) -> None:
        """
        Initialize protection manager.

        Args:
            max_reload_per_minute: Rate limit for reloads.
            failure_threshold: Failures before circuit opens.
            recovery_timeout: Seconds before circuit half-open.
            enable_auto_rollback: Enable automatic rollback on failure.
        """
        # Rate limiting
        self._max_per_minute = max_reload_per_minute
        self._reload_timestamps: List[float] = []

        # Circuit breaker
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0

        # Auto rollback
        self._enable_auto_rollback = enable_auto_rollback

        # Metrics
        self._total_allowed = 0
        self._total_rejected = 0
        self._total_failures = 0
        self._total_rollbacks = 0

        self._lock = threading.Lock()

    @property
    def circuit_state(
        self,
    ) -> str:
        """Get circuit breaker state."""
        return self._circuit_state

    @property
    def is_protected(
        self,
    ) -> bool:
        """Check if protection is active (circuit open)."""
        return self._circuit_state == CircuitState.OPEN

    @property
    def stats(
        self,
    ) -> Dict[str, Any]:
        """Get protection statistics."""
        return {
            "circuit_state": self._circuit_state,
            "failure_count": self._failure_count,
            "total_allowed": self._total_allowed,
            "total_rejected": self._total_rejected,
            "total_failures": self._total_failures,
            "total_rollbacks": self._total_rollbacks,
            "rate_limit": self._max_per_minute,
            "failure_threshold": self._failure_threshold,
        }

    def allow_reload(
        self,
    ) -> bool:
        """
        Check if a reload is allowed.

        Returns:
            True if reload is allowed.
        """
        with self._lock:
            now = time.time()

            # Check circuit breaker
            if self._circuit_state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if now - self._last_failure_time >= self._recovery_timeout:
                    self._circuit_state = CircuitState.HALF_OPEN
                else:
                    self._total_rejected += 1
                    return False

            # Check rate limit
            cutoff = now - 60.0  # Last minute
            self._reload_timestamps = [
                t for t in self._reload_timestamps if t > cutoff
            ]

            if len(self._reload_timestamps) >= self._max_per_minute:
                self._total_rejected += 1
                return False

            # Allowed
            self._reload_timestamps.append(now)
            self._total_allowed += 1
            return True

    def on_success(
        self,
    ) -> None:
        """Report a successful reload."""
        with self._lock:
            if self._circuit_state == CircuitState.HALF_OPEN:
                # Recovery successful
                self._circuit_state = CircuitState.CLOSED
                self._failure_count = 0

    def on_failure(
        self,
        errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Report a failed reload.

        Args:
            errors: List of error messages.

        Returns:
            Action taken by protection.
        """
        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._last_failure_time = time.time()

            action = {"action": "none", "circuit_state": self._circuit_state}

            # Check if circuit should open
            if self._failure_count >= self._failure_threshold:
                self._circuit_state = CircuitState.OPEN
                action["action"] = "circuit_open"
                action["circuit_state"] = self._circuit_state

                # Trigger automatic rollback if enabled
                if self._enable_auto_rollback:
                    action["action"] = "auto_rollback"
                    self._total_rollbacks += 1

            elif self._circuit_state == CircuitState.HALF_OPEN:
                # Half-open test failed
                self._circuit_state = CircuitState.OPEN
                action["action"] = "circuit_reopened"
                action["circuit_state"] = self._circuit_state

            return action

    def reset(
        self,
    ) -> None:
        """Reset protection state."""
        with self._lock:
            self._circuit_state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0
            self._reload_timestamps.clear()

    def get_rate_limit_status(
        self,
    ) -> Dict[str, Any]:
        """Get current rate limit status."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            recent = [t for t in self._reload_timestamps if t > cutoff]
            return {
                "limit": self._max_per_minute,
                "remaining": max(0, self._max_per_minute - len(recent)),
                "used": len(recent),
            }

    def get_circuit_status(
        self,
    ) -> Dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            now = time.time()
            time_since_failure = now - self._last_failure_time if self._last_failure_time else None
            time_to_recovery = max(
                0,
                self._recovery_timeout - (now - self._last_failure_time)
            ) if self._circuit_state == CircuitState.OPEN and self._last_failure_time else 0

            return {
                "state": self._circuit_state,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "time_since_failure": time_since_failure,
                "time_to_recovery": time_to_recovery,
            }
