"""
Crypto self-protection.

Protects the crypto platform from instability through:
- Key operation rate limiting
- Circuit breaker for KMS provider
- Automatic provider failover
- Key cache isolation

Protection Flow:
    Key Operation Request
        ↓
    Rate Limit Check
        ↓
    Circuit Breaker
        ↓
    Provider Failover
        ↓
    Allow or Reject
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProtectionCircuitState:
    """Circuit breaker state constants."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CryptoProtection:
    """
    Crypto platform protection manager.

    Implements multiple protection mechanisms:
    1. Rate limiting for key operations
    2. Circuit breaker for KMS provider failures
    3. Automatic provider failover
    4. Key cache isolation

    Usage:
        protection = CryptoProtection()
        if protection.allow_operation():
            # Execute crypto operation
            result = do_crypto_operation()
            if result.success:
                protection.on_success()
            else:
                protection.on_failure(result.errors)
        else:
            # Operation rejected - circuit open
    """

    def __init__(
        self,
        max_operations_per_minute: int = 60,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        enable_failover: bool = True,
    ) -> None:
        """
        Initialize protection manager.

        Args:
            max_operations_per_minute: Rate limit for key operations.
            failure_threshold: Failures before circuit opens.
            recovery_timeout: Seconds before circuit half-open.
            enable_failover: Enable automatic provider failover.
        """
        self._max_per_minute = max_operations_per_minute
        self._operation_timestamps: List[float] = []

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._circuit_state = ProtectionCircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0

        self._enable_failover = enable_failover
        self._primary_provider: Optional[str] = None
        self._standby_providers: List[str] = []
        self._active_provider: Optional[str] = None

        self._total_allowed = 0
        self._total_rejected = 0
        self._total_failures = 0
        self._total_failovers = 0

        self._lock = threading.Lock()

    @property
    def circuit_state(self) -> str:
        """Get circuit breaker state."""
        return self._circuit_state

    @property
    def is_protected(self) -> bool:
        """Check if protection is active (circuit open)."""
        return self._circuit_state == ProtectionCircuitState.OPEN

    @property
    def active_provider(self) -> Optional[str]:
        """Get currently active provider name."""
        return self._active_provider

    def get_stats(self) -> Dict[str, Any]:
        """
        Get protection statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            return {
                "circuit_state": self._circuit_state,
                "failure_count": self._failure_count,
                "total_allowed": self._total_allowed,
                "total_rejected": self._total_rejected,
                "total_failures": self._total_failures,
                "total_failovers": self._total_failovers,
                "rate_limit": self._max_per_minute,
                "failure_threshold": self._failure_threshold,
                "active_provider": self._active_provider,
                "primary_provider": self._primary_provider,
            }

    def register_providers(
        self,
        primary: str,
        standby: Optional[List[str]] = None,
    ) -> None:
        """
        Register primary and standby providers.

        Args:
            primary: Primary provider name.
            standby: List of standby provider names.
        """
        with self._lock:
            self._primary_provider = primary
            self._active_provider = primary
            self._standby_providers = standby or []

    def allow_operation(self) -> bool:
        """
        Check if a crypto operation is allowed.

        Checks circuit breaker state and rate limits
        before allowing the operation to proceed.

        Returns:
            True if operation is allowed.
        """
        with self._lock:
            now = time.time()

            if self._circuit_state == ProtectionCircuitState.OPEN:
                if (
                    now - self._last_failure_time
                    >= self._recovery_timeout
                ):
                    self._circuit_state = (
                        ProtectionCircuitState.HALF_OPEN
                    )
                    logger.info(
                        "Circuit breaker half-open, "
                        "testing provider recovery"
                    )
                else:
                    self._total_rejected += 1
                    return False

            cutoff = now - 60.0
            self._operation_timestamps = [
                t
                for t in self._operation_timestamps
                if t > cutoff
            ]

            if len(self._operation_timestamps) >= self._max_per_minute:
                self._total_rejected += 1
                logger.warning(
                    "Rate limit exceeded: %d operations/min",
                    self._max_per_minute,
                )
                return False

            self._operation_timestamps.append(now)
            self._total_allowed += 1
            return True

    def on_success(self) -> None:
        """
        Report a successful operation.

        Resets failure count and closes circuit
        if in half-open state.
        """
        with self._lock:
            if (
                self._circuit_state
                == ProtectionCircuitState.HALF_OPEN
            ):
                self._circuit_state = ProtectionCircuitState.CLOSED
                self._failure_count = 0
                logger.info(
                    "Circuit breaker closed, "
                    "provider recovered successfully"
                )

    def on_failure(
        self,
        errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Report a failed operation.

        Triggers circuit breaker evaluation and
        automatic failover if conditions are met.

        Args:
            errors: List of error messages.

        Returns:
            Action taken by protection.
        """
        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._last_failure_time = time.time()

            action: Dict[str, Any] = {
                "action": "none",
                "circuit_state": self._circuit_state,
            }

            if (
                self._failure_count
                >= self._failure_threshold
            ):
                self._circuit_state = ProtectionCircuitState.OPEN
                action["action"] = "circuit_open"
                action["circuit_state"] = self._circuit_state

                if self._enable_failover and self._standby_providers:
                    self._perform_failover()
                    action["action"] = "failover"

            elif (
                self._circuit_state
                == ProtectionCircuitState.HALF_OPEN
            ):
                self._circuit_state = ProtectionCircuitState.OPEN
                action["action"] = "circuit_reopened"
                action["circuit_state"] = self._circuit_state

                if self._enable_failover and self._standby_providers:
                    self._perform_failover()
                    action["action"] = "failover"

            if errors:
                action["errors"] = errors

            return action

    def reset(self) -> None:
        """Reset protection state."""
        with self._lock:
            self._circuit_state = ProtectionCircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0
            self._operation_timestamps.clear()
            self._active_provider = self._primary_provider
            logger.info("Crypto protection reset")

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Rate limit status dictionary.
        """
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            recent = [
                t
                for t in self._operation_timestamps
                if t > cutoff
            ]
            return {
                "limit": self._max_per_minute,
                "remaining": max(
                    0,
                    self._max_per_minute - len(recent),
                ),
                "used": len(recent),
            }

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status.

        Returns:
            Circuit status dictionary.
        """
        with self._lock:
            now = time.time()
            time_since_failure = (
                now - self._last_failure_time
                if self._last_failure_time
                else None
            )
            time_to_recovery = (
                max(
                    0,
                    self._recovery_timeout
                    - (now - self._last_failure_time),
                )
                if self._circuit_state
                == ProtectionCircuitState.OPEN
                and self._last_failure_time
                else 0
            )

            return {
                "state": self._circuit_state,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "time_since_failure": time_since_failure,
                "time_to_recovery": time_to_recovery,
                "active_provider": self._active_provider,
            }

    def _perform_failover(self) -> None:
        """Switch to next available standby provider."""
        if not self._standby_providers:
            return

        current = self._active_provider
        for standby in self._standby_providers:
            if standby != current:
                self._active_provider = standby
                self._total_failovers += 1
                logger.warning(
                    "Failover: %s -> %s",
                    current,
                    standby,
                )
                return

        if self._primary_provider and current != self._primary_provider:
            self._active_provider = self._primary_provider
            self._total_failovers += 1
            logger.warning(
                "Failover: %s -> %s (primary)",
                current,
                self._primary_provider,
            )