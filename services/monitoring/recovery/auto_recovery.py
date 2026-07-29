"""Auto Recovery Engine.

Automatically attempts to recover from detected failures:
- Broker timeout → Reconnect
- Redis unavailable → Read replica
- Service DOWN → Restart (if orchestrated)
- Connection failure → Retry with backoff

Usage::

    recovery = AutoRecovery()
    recovery.register_action(RecoveryAction(
        name="broker_reconnect",
        condition_fn=lambda health: health["broker"] == "Unhealthy",
        action_fn=lambda: reconnect_broker(),
        max_attempts=3,
    ))
    results = recovery.check_and_recover(health_report)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RecoveryStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"
    NOT_NEEDED = "not_needed"


@dataclass
class RecoveryAction:
    """A recovery action that can be executed when a condition is met."""

    name: str
    description: str
    condition_fn: Callable[[Dict[str, Any]], bool]
    action_fn: Callable[[], bool]
    max_attempts: int = 3
    cooldown_seconds: float = 60.0
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "max_attempts": self.max_attempts,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
            "tags": self.tags,
        }


@dataclass
class RecoveryResult:
    """Result of executing a recovery action."""

    action_name: str
    status: RecoveryStatus
    attempt: int = 1
    duration_ms: float = 0.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "status": self.status.value,
            "attempt": self.attempt,
            "duration_ms": round(self.duration_ms, 2),
            "message": self.message,
            "timestamp": self.timestamp,
        }


class AutoRecovery:
    """Automatically recovers from detected failures.

    Monitors health reports and executes registered recovery actions
    when conditions are met. Actions have cooldown periods and max
    attempts to prevent infinite recovery loops.
    """

    def __init__(self) -> None:
        self._actions: Dict[str, RecoveryAction] = {}
        self._attempts: Dict[str, int] = {}
        self._last_attempt: Dict[str, float] = {}
        self._history: List[RecoveryResult] = []
        self._total_recoveries: int = 0
        self._successful_recoveries: int = 0

    def register_action(self, action: RecoveryAction) -> None:
        """Register a recovery action."""
        self._actions[action.name] = action
        self._attempts[action.name] = 0
        self._last_attempt[action.name] = 0.0

    def remove_action(self, name: str) -> None:
        """Remove a recovery action."""
        self._actions.pop(name, None)
        self._attempts.pop(name, None)
        self._last_attempt.pop(name, None)

    def get_action(self, name: str) -> Optional[RecoveryAction]:
        """Get a recovery action by name."""
        return self._actions.get(name)

    def list_actions(self) -> List[RecoveryAction]:
        """List all registered recovery actions."""
        return list(self._actions.values())

    def check_and_recover(
        self,
        context: Dict[str, Any],
        force_actions: Optional[List[str]] = None,
    ) -> List[RecoveryResult]:
        """Check conditions and execute recovery actions if needed.

        Args:
            context: Health data dict used to evaluate conditions
            force_actions: Optional list of action names to force-execute

        Returns:
            List of recovery results for actions that were attempted.
        """
        now = time.time()
        results: List[RecoveryResult] = []

        actions_to_check = force_actions or list(self._actions.keys())

        for name in actions_to_check:
            action = self._actions.get(name)
            if action is None:
                continue
            if not action.enabled:
                continue

            # Check cooldown
            last = self._last_attempt.get(name, 0.0)
            if now - last < action.cooldown_seconds and not force_actions:
                continue

            # Check max attempts
            attempts = self._attempts.get(name, 0)
            if attempts >= action.max_attempts:
                results.append(RecoveryResult(
                    action_name=name,
                    status=RecoveryStatus.MAX_ATTEMPTS_EXCEEDED,
                    attempt=action.max_attempts,
                    message=f"Max attempts ({action.max_attempts}) reached",
                ))
                continue

            # Check condition (skip for forced actions)
            if not force_actions:
                try:
                    should_recover = action.condition_fn(context)
                except Exception:
                    should_recover = False
                if not should_recover:
                    continue

            # Execute recovery
            self._attempts[name] = attempts + 1
            self._last_attempt[name] = now

            start = time.time()
            try:
                success = action.action_fn()
                duration = (time.time() - start) * 1000.0
            except Exception as e:
                success = False
                duration = (time.time() - start) * 1000.0

            self._total_recoveries += 1
            if success:
                self._successful_recoveries += 1
                self._attempts[name] = 0  # Reset on success
                status = RecoveryStatus.SUCCESS
                message = f"Recovery '{name}' succeeded"
            else:
                status = RecoveryStatus.FAILED
                message = f"Recovery '{name}' failed (attempt {self._attempts[name]}/{action.max_attempts})"

            result = RecoveryResult(
                action_name=name,
                status=status,
                attempt=self._attempts[name],
                duration_ms=duration,
                message=message,
            )
            results.append(result)
            self._history.append(result)

        # Trim history
        if len(self._history) > 500:
            self._history = self._history[-500:]

        return results

    def reset_attempts(self, action_name: str) -> None:
        """Reset attempt counter for an action."""
        self._attempts[action_name] = 0

    def reset_all(self) -> None:
        """Reset all attempt counters."""
        for name in self._attempts:
            self._attempts[name] = 0

    def get_history(self, limit: int = 100) -> List[RecoveryResult]:
        """Get recovery history."""
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get auto-recovery status summary."""
        return {
            "actions_count": len(self._actions),
            "total_recoveries": self._total_recoveries,
            "successful_recoveries": self._successful_recoveries,
            "success_rate": (
                self._successful_recoveries / max(self._total_recoveries, 1)
            ),
            "actions": {
                name: {
                    "attempts": self._attempts.get(name, 0),
                    "last_attempt": self._last_attempt.get(name, 0),
                    "enabled": action.enabled,
                }
                for name, action in self._actions.items()
            },
        }
