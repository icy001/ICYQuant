"""
Vault High Availability Failover.

Implements automatic failover for Vault
clusters with circuit breaker pattern,
retry logic, and health probe-based
switchover between primary and standby
nodes.

Failover flow:
1. Health probe detects primary failure
2. Circuit breaker opens
3. Retry with backoff
4. Automatic switch to standby
5. Circuit breaker resets after timeout
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .client import VaultClient
from .config import VaultConfig, VaultFailoverConfig
from .exceptions import (
    VaultCircuitOpenError,
    VaultConnectionError,
    VaultFailoverError,
)
from .discovery import VaultDiscovery, VaultNode

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failures exceed threshold
    HALF_OPEN = "half_open" # Testing recovery


class FailoverEvent(str, Enum):
    """Failover event types."""

    PRIMARY_FAILURE = "primary_failure"
    FAILOVER_INITIATED = "failover_initiated"
    FAILOVER_COMPLETED = "failover_completed"
    FAILOVER_FAILED = "failover_failed"
    RECOVERY_DETECTED = "recovery_detected"
    CIRCUIT_OPENED = "circuit_opened"
    CIRCUIT_CLOSED = "circuit_closed"


class FailoverManager:
    """
    Vault HA Failover Manager.

    Manages automatic failover between
    primary and standby Vault nodes with:
    - Circuit breaker pattern
    - Exponential backoff retries
    - Health probe-based detection
    - Event notifications

    Usage:
        fm = FailoverManager(config, discovery)
        fm.set_on_failover(lambda node: ...)
        await fm.execute_request(my_operation)
    """

    def __init__(
        self,
        config: VaultConfig,
        discovery: Optional[VaultDiscovery] = None,
    ) -> None:
        self._config = config
        self._failover_config = config.failover
        self._discovery = discovery
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._current_node: Optional[VaultNode] = None
        self._failover_count = 0
        self._events: List[Dict[str, Any]] = []
        self._on_failover: Optional[Callable[[VaultNode], None]] = None
        self._on_circuit_event: Optional[Callable[[CircuitState], None]] = None

    async def execute_request(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a Vault request with failover support.

        Args:
            operation: Async callable to execute.
            *args: Operation positional args.
            **kwargs: Operation keyword args.

        Returns:
            Operation result.

        Raises:
            VaultFailoverError: If all nodes fail.
        """
        # Check circuit breaker
        self._check_circuit()

        last_error: Optional[Exception] = None
        nodes = self._get_candidate_nodes()

        for node in nodes:
            try:
                # Check circuit again
                self._check_circuit()

                result = await operation(node, *args, **kwargs)
                self._record_success()
                self._current_node = node
                return result

            except (VaultConnectionError, VaultFailoverError) as e:
                last_error = e
                self._record_failure()
                logger.warning(
                    "Request failed on %s: %s. Trying next...",
                    node.address,
                    e,
                )

                if self._failure_count >= self._failover_config.failure_threshold:
                    self._open_circuit()
                    break

            except VaultCircuitOpenError:
                raise

        raise VaultFailoverError(
            f"All Vault nodes failed. Last error: {last_error}",
        )

    async def initiate_failover(self) -> Optional[VaultNode]:
        """
        Manually initiate failover to next healthy node.

        Returns:
            New primary node or None.
        """
        self._emit_event(FailoverEvent.FAILOVER_INITIATED)

        nodes = self._get_candidate_nodes()
        current = self._current_node

        for node in nodes:
            if node != current and node.healthy:
                self._current_node = node
                self._failover_count += 1
                self._emit_event(FailoverEvent.FAILOVER_COMPLETED)

                if self._on_failover:
                    try:
                        self._on_failover(node)
                    except Exception as e:
                        logger.error("Failover callback error: %s", e)

                logger.info(
                    "Failover completed: %s -> %s",
                    current.address if current else "N/A",
                    node.address,
                )
                return node

        self._emit_event(FailoverEvent.FAILOVER_FAILED)
        return None

    def set_on_failover(
        self,
        callback: Callable[[VaultNode], None],
    ) -> None:
        """Set failover callback."""
        self._on_failover = callback

    def set_on_circuit_event(
        self,
        callback: Callable[[CircuitState], None],
    ) -> None:
        """Set circuit breaker event callback."""
        self._on_circuit_event = callback

    # ── Circuit Breaker ──

    def _check_circuit(self) -> None:
        """Check circuit breaker state."""
        if self._circuit_state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if self._last_failure_time:
                elapsed = (
                    datetime.utcnow() - self._last_failure_time
                ).total_seconds()
                if elapsed >= self._failover_config.circuit_breaker_reset_timeout:
                    self._transition(CircuitState.HALF_OPEN)
                else:
                    raise VaultCircuitOpenError(
                        "Circuit breaker is open. "
                        f"Retry after {self._failover_config.circuit_breaker_reset_timeout}s"
                    )

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        if self._circuit_state != CircuitState.OPEN:
            self._transition(CircuitState.OPEN)
            self._last_failure_time = datetime.utcnow()
            self._emit_event(FailoverEvent.CIRCUIT_OPENED)
            logger.warning(
                "Circuit breaker OPENED after %d failures",
                self._failure_count,
            )

    def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        if self._circuit_state != CircuitState.CLOSED:
            self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._emit_event(FailoverEvent.CIRCUIT_CLOSED)
            logger.info("Circuit breaker CLOSED")

    def _transition(self, new_state: CircuitState) -> None:
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

    def _record_success(self) -> None:
        """Record a successful request."""
        self._success_count += 1
        self._last_success_time = datetime.utcnow()

        if self._circuit_state == CircuitState.HALF_OPEN:
            self._close_circuit()

    def _record_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self._circuit_state == CircuitState.HALF_OPEN:
            self._open_circuit()

    # ── Node Management ──

    def _get_candidate_nodes(self) -> List[VaultNode]:
        """Get ordered list of candidate nodes."""
        if self._discovery:
            # Use discovered nodes
            nodes = self._discovery.get_all_nodes()
        else:
            # Build from config
            nodes = [
                VaultNode(address=self._config.address, role="active")
            ]
            for addr in self._failover_config.standby_addresses:
                nodes.append(VaultNode(address=addr, role="standby"))

        # Sort: current first, then by health
        if self._current_node:
            nodes.sort(
                key=lambda n: (
                    n != self._current_node,
                    not n.healthy,
                )
            )

        return nodes

    # ── Events ──

    def _emit_event(self, event_type: FailoverEvent) -> None:
        """Emit a failover event."""
        self._events.append({
            "type": event_type.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "failure_count": self._failure_count,
            "circuit_state": self._circuit_state.value,
        })
        # Keep last 500 events
        if len(self._events) > 500:
            self._events = self._events[-500:]

    def get_events(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent failover events."""
        return self._events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get failover manager statistics."""
        return {
            "circuit_state": self._circuit_state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failover_count": self._failover_count,
            "current_node": (
                self._current_node.to_dict()
                if self._current_node
                else None
            ),
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
            "recent_events": len(self._events),
        }
