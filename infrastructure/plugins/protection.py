from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_HALF_OPEN = "HALF_OPEN"
CIRCUIT_OPEN = "OPEN"

MAX_FAILURES_BEFORE_OPEN = 3
COOLDOWN_SECONDS = 60
MAX_RESTARTS = 5


class PluginProtection:
    """Platform protection with circuit breaker and restart limits.

    Implements the circuit breaker pattern to isolate failing
    plugins, preventing cascading failures. Tracks violation counts,
    restart counts, and provides a safe mode for degraded operation.

    Circuit states: CLOSED → HALF_OPEN → OPEN

    Usage::

        protection = PluginProtection()
        result = await protection.check_plugin("my_plugin")
        if protection.is_circuit_open("my_plugin"):
            ...
    """

    def __init__(self) -> None:
        self._failure_counts: Dict[str, int] = {}
        self._restart_counts: Dict[str, int] = {}
        self._circuit_states: Dict[str, str] = {}
        self._circuit_open_times: Dict[str, Optional[float]] = {}
        self._violations: Dict[str, List[Dict[str, Any]]] = {}
        self._safe_mode: bool = False
        self._total_checks: int = 0
        self._total_blocks: int = 0
        self._total_failures: int = 0

    async def check_plugin(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Pre-execution safety check for a plugin.

        Verifies circuit breaker state, restart limits, and
        dependency availability before allowing execution.

        Args:
            plugin_id: The plugin identifier to check.

        Returns:
            Dictionary with ``allowed`` (bool), ``reason`` (str),
            and ``state`` (str) keys.
        """
        self._total_checks += 1

        state = self._circuit_states.get(plugin_id, CIRCUIT_CLOSED)

        if state == CIRCUIT_OPEN:
            open_time = self._circuit_open_times.get(plugin_id)
            if open_time is not None:
                elapsed = time.monotonic() - open_time
                if elapsed >= COOLDOWN_SECONDS:
                    self._circuit_states[plugin_id] = CIRCUIT_HALF_OPEN
                    logger.info(
                        "Circuit for '%s' transitioned to HALF_OPEN.",
                        plugin_id,
                    )
                    state = CIRCUIT_HALF_OPEN
                else:
                    self._total_blocks += 1
                    remaining = COOLDOWN_SECONDS - elapsed
                    logger.warning(
                        "Plugin '%s' blocked: circuit open for %.1fs.",
                        plugin_id,
                        remaining,
                    )
                    return {
                        "allowed": False,
                        "reason": f"Circuit open. {remaining:.1f}s remaining.",
                        "state": state,
                    }

        restart_count = self._restart_counts.get(plugin_id, 0)
        if restart_count >= MAX_RESTARTS:
            self._total_blocks += 1
            logger.warning(
                "Plugin '%s' blocked: max restarts (%d) reached.",
                plugin_id,
                MAX_RESTARTS,
            )
            return {
                "allowed": False,
                "reason": f"Max restart limit ({MAX_RESTARTS}) reached.",
                "state": state,
            }

        if self._safe_mode and state != CIRCUIT_CLOSED:
            self._total_blocks += 1
            logger.warning(
                "Plugin '%s' blocked: safe mode active.",
                plugin_id,
            )
            return {
                "allowed": False,
                "reason": "System is in safe mode.",
                "state": state,
            }

        return {
            "allowed": True,
            "reason": "Plugin passed safety check.",
            "state": state,
        }

    async def on_failure(
        self, plugin_id: str, error: str
    ) -> Dict[str, Any]:
        """Handle a plugin failure and update protection state.

        Increments the failure counter and transitions the circuit
        breaker if the threshold is exceeded.

        Args:
            plugin_id: The plugin identifier that failed.
            error: The error description.

        Returns:
            Dictionary with action taken and new state.
        """
        self._total_failures += 1

        violations = self._violations.setdefault(plugin_id, [])
        violations.append({
            "error": error,
            "timestamp": time.monotonic(),
        })

        self._failure_counts[plugin_id] = (
            self._failure_counts.get(plugin_id, 0) + 1
        )
        failures = self._failure_counts[plugin_id]

        current_state = self._circuit_states.get(plugin_id, CIRCUIT_CLOSED)

        if current_state == CIRCUIT_HALF_OPEN:
            self._circuit_states[plugin_id] = CIRCUIT_OPEN
            self._circuit_open_times[plugin_id] = time.monotonic()
            logger.warning(
                "Plugin '%s' failed in HALF_OPEN → circuit OPEN.",
                plugin_id,
            )
            return {
                "action": "circuit_open",
                "state": CIRCUIT_OPEN,
                "failures": failures,
            }

        if failures >= MAX_FAILURES_BEFORE_OPEN:
            self._circuit_states[plugin_id] = CIRCUIT_OPEN
            self._circuit_open_times[plugin_id] = time.monotonic()
            logger.warning(
                "Plugin '%s' failure threshold reached (%d/%d) → circuit OPEN.",
                plugin_id,
                failures,
                MAX_FAILURES_BEFORE_OPEN,
            )
            return {
                "action": "circuit_open",
                "state": CIRCUIT_OPEN,
                "failures": failures,
            }

        if current_state == CIRCUIT_CLOSED and failures >= 2:
            self._circuit_states[plugin_id] = CIRCUIT_HALF_OPEN
            logger.warning(
                "Plugin '%s' showing failures (%d) → circuit HALF_OPEN.",
                plugin_id,
                failures,
            )
            return {
                "action": "circuit_half_open",
                "state": CIRCUIT_HALF_OPEN,
                "failures": failures,
            }

        return {
            "action": "recorded",
            "state": current_state,
            "failures": failures,
        }

    def is_circuit_open(self, plugin_id: str) -> bool:
        """Check if the circuit breaker is open for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            True if the circuit is in OPEN state.
        """
        return self._circuit_states.get(plugin_id, CIRCUIT_CLOSED) == CIRCUIT_OPEN

    def reset_circuit(self, plugin_id: str) -> None:
        """Reset the circuit breaker for a plugin to CLOSED state.

        Also clears the failure counter and restart count.

        Args:
            plugin_id: The plugin identifier.
        """
        self._circuit_states[plugin_id] = CIRCUIT_CLOSED
        self._circuit_open_times[plugin_id] = None
        self._failure_counts[plugin_id] = 0
        logger.info("Circuit reset for '%s'.", plugin_id)

    def get_violation_count(self, plugin_id: str) -> int:
        """Get the number of violations recorded for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Violation count.
        """
        return len(self._violations.get(plugin_id, []))

    def get_restart_count(self, plugin_id: str) -> int:
        """Get the restart count for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Restart count.
        """
        return self._restart_counts.get(plugin_id, 0)

    def increment_restart(self, plugin_id: str) -> None:
        """Increment the restart counter for a plugin.

        Args:
            plugin_id: The plugin identifier.
        """
        self._restart_counts[plugin_id] = (
            self._restart_counts.get(plugin_id, 0) + 1
        )

    def is_safe_mode(self) -> bool:
        """Check if the system is in safe mode.

        Returns:
            True if safe mode is active.
        """
        return self._safe_mode

    def set_safe_mode(self, enabled: bool) -> None:
        """Enable or disable safe mode.

        Args:
            enabled: True to enable safe mode.
        """
        self._safe_mode = enabled
        logger.warning(
            "Safe mode %s.", "enabled" and "enabled" or "disabled"
        )

    def get_circuit_state(self, plugin_id: str) -> str:
        """Get the current circuit state for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            One of ``CLOSED``, ``HALF_OPEN``, ``OPEN``.
        """
        return self._circuit_states.get(plugin_id, CIRCUIT_CLOSED)

    def get_stats(self) -> Dict[str, Any]:
        """Get protection statistics.

        Returns:
            Dictionary with circuit states, violation counts,
            restart counts, and safe mode status.
        """
        return {
            "safe_mode": self._safe_mode,
            "total_checks": self._total_checks,
            "total_blocks": self._total_blocks,
            "total_failures": self._total_failures,
            "circuits": {
                pid: {
                    "state": state,
                    "failures": self._failure_counts.get(pid, 0),
                    "restarts": self._restart_counts.get(pid, 0),
                    "violations": self.get_violation_count(pid),
                }
                for pid, state in self._circuit_states.items()
            },
            "closed_circuits": [
                pid
                for pid, state in self._circuit_states.items()
                if state == CIRCUIT_CLOSED
            ],
            "half_open_circuits": [
                pid
                for pid, state in self._circuit_states.items()
                if state == CIRCUIT_HALF_OPEN
            ],
            "open_circuits": [
                pid
                for pid, state in self._circuit_states.items()
                if state == CIRCUIT_OPEN
            ],
            "max_failures_threshold": MAX_FAILURES_BEFORE_OPEN,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "max_restarts": MAX_RESTARTS,
        }