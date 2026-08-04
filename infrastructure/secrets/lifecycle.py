"""
Secret lifecycle management.

Defines the lifecycle states and
state transitions for secrets,
enforcing proper progression
through creation, rotation,
and eventual retirement.

Also provides platform-level lifecycle
management for the secrets platform,
coordinating startup, reload, and
graceful shutdown of all components.

Platform Lifecycle Flow:
    Startup -> Running -> (Reload | Health Check) -> Shutdown

Secret Lifecycle Flow:
    Created -> Active -> Rotating/Deprecated/Revoked/Expired
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class SecretLifecycle(str, Enum):
    """Secret lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"
    EXPIRED = "expired"


LIFECYCLE_TRANSITIONS: Dict[SecretLifecycle, List[SecretLifecycle]] = {
    SecretLifecycle.CREATED: [SecretLifecycle.ACTIVE],
    SecretLifecycle.ACTIVE: [
        SecretLifecycle.ROTATING,
        SecretLifecycle.DEPRECATED,
        SecretLifecycle.REVOKED,
        SecretLifecycle.EXPIRED,
    ],
    SecretLifecycle.ROTATING: [
        SecretLifecycle.ACTIVE,
        SecretLifecycle.REVOKED,
    ],
    SecretLifecycle.DEPRECATED: [
        SecretLifecycle.REVOKED,
        SecretLifecycle.EXPIRED,
    ],
    SecretLifecycle.REVOKED: [],
    SecretLifecycle.EXPIRED: [],
}


@dataclass
class LifecycleState:
    """
    Represents the lifecycle state of a secret.

    Tracks current state, transition history,
    and lifecycle timestamps.

    Attributes:
        state: Current lifecycle state.
        current_version: Current version number.
        previous_version: Previous version (for rotation).
        created_at: When the lifecycle began.
        last_transition: When the last state change occurred.
        transitions: History of state transitions.
    """

    state: SecretLifecycle = SecretLifecycle.CREATED
    current_version: int = 1
    previous_version: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_transition: Optional[datetime] = None
    transitions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """Check if secret is in an active state."""
        return self.state in (SecretLifecycle.ACTIVE, SecretLifecycle.ROTATING)

    @property
    def is_terminal(self) -> bool:
        """Check if secret is in a terminal state."""
        return self.state in (SecretLifecycle.REVOKED, SecretLifecycle.EXPIRED)

    @property
    def age_days(self) -> float:
        """Get age in days since creation."""
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() / 86400.0

    def can_transition_to(
        self,
        target: SecretLifecycle,
    ) -> bool:
        """
        Check if transition to target state is valid.

        Args:
            target: Target lifecycle state.

        Returns:
            True if the transition is allowed.
        """
        allowed = LIFECYCLE_TRANSITIONS.get(self.state, [])
        return target in allowed

    def transition_to(
        self,
        target: SecretLifecycle,
        reason: str = "",
    ) -> bool:
        """
        Perform a state transition.

        Args:
            target: Target lifecycle state.
            reason: Reason for the transition.

        Returns:
            True if transition succeeded.

        Raises:
            ValueError: If the transition is not allowed.
        """
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid lifecycle transition: {self.state.value} -> {target.value}"
            )

        now = datetime.utcnow()
        self.transitions.append({
            "from": self.state.value,
            "to": target.value,
            "reason": reason,
            "timestamp": now.isoformat() + "Z",
        })
        self.state = target
        self.last_transition = now
        return True

    def begin_rotation(self) -> None:
        """Mark secret as rotating."""
        self.transition_to(
            SecretLifecycle.ROTATING,
            reason="Rotation started",
        )

    def complete_rotation(self) -> None:
        """Complete rotation and mark as active."""
        self.previous_version = self.current_version
        self.current_version += 1
        self.transition_to(
            SecretLifecycle.ACTIVE,
            reason="Rotation completed",
        )

    def mark_deprecated(self, reason: str = "") -> None:
        """Mark secret as deprecated."""
        self.transition_to(SecretLifecycle.DEPRECATED, reason=reason or "Deprecated")

    def revoke(self, reason: str = "") -> None:
        """Revoke the secret."""
        self.transition_to(SecretLifecycle.REVOKED, reason=reason or "Revoked")

    def expire(self, reason: str = "") -> None:
        """Mark the secret as expired."""
        self.transition_to(SecretLifecycle.EXPIRED, reason=reason or "Expired")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "current_version": self.current_version,
            "previous_version": self.previous_version,
            "created_at": self.created_at.isoformat() + "Z",
            "last_transition": (
                self.last_transition.isoformat() + "Z"
                if self.last_transition
                else None
            ),
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
            "age_days": round(self.age_days, 2),
            "transition_count": len(self.transitions),
            "transitions": self.transitions[-10:],
        }


class LifecycleManager:
    """
    Manages lifecycles for multiple secrets.

    Provides tracking, querying, and
    bulk operations on secret lifecycles.

    Usage:
        manager = LifecycleManager()
        lifecycle = manager.create("secret-key")
        lifecycle.begin_rotation()
        lifecycle.complete_rotation()
    """

    def __init__(self) -> None:
        self._lifecycles: Dict[str, LifecycleState] = {}

    def create(
        self,
        secret_id: str,
    ) -> LifecycleState:
        """
        Create a new lifecycle for a secret.

        Args:
            secret_id: Unique secret identifier.

        Returns:
            New LifecycleState instance.
        """
        lifecycle = LifecycleState()
        self._lifecycles[secret_id] = lifecycle
        return lifecycle

    def get(
        self,
        secret_id: str,
    ) -> Optional[LifecycleState]:
        """Get lifecycle by secret ID."""
        return self._lifecycles.get(secret_id)

    def remove(self, secret_id: str) -> bool:
        """Remove a lifecycle."""
        return self._lifecycles.pop(secret_id, None) is not None

    def get_by_state(
        self,
        state: SecretLifecycle,
    ) -> List[str]:
        """Get all secret IDs in a given state."""
        return [
            sid for sid, lc in self._lifecycles.items()
            if lc.state == state
        ]

    def get_active(self) -> List[str]:
        """Get all active secret IDs."""
        return [
            sid for sid, lc in self._lifecycles.items()
            if lc.is_active
        ]

    def get_terminal(self) -> List[str]:
        """Get all terminal secret IDs."""
        return [
            sid for sid, lc in self._lifecycles.items()
            if lc.is_terminal
        ]

    def count(self) -> int:
        """Get total lifecycle count."""
        return len(self._lifecycles)

    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle statistics."""
        state_counts: Dict[str, int] = {}
        for lc in self._lifecycles.values():
            state_name = lc.state.value
            state_counts[state_name] = state_counts.get(state_name, 0) + 1

        return {
            "total": len(self._lifecycles),
            "by_state": state_counts,
            "active_count": len(self.get_active()),
            "terminal_count": len(self.get_terminal()),
        }


class SecretsLifecycleState(str, Enum):
    """Secrets platform lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    RELOADING = "reloading"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class SecretsLifecycle:
    """
    Unified lifecycle management for secrets platform.

    Coordinates the startup, reload, and shutdown
    of all secrets platform components, while
    wrapping the existing secret lifecycle
    management for individual secret tracking.

    Usage:
        lifecycle = SecretsLifecycle()
        await lifecycle.startup()
        # ... platform running ...
        await lifecycle.reload()
        # ... shutdown ...
        await lifecycle.shutdown()
    """

    def __init__(
        self,
        lifecycle_manager: Optional[LifecycleManager] = None,
    ) -> None:
        """
        Initialize secrets lifecycle manager.

        Args:
            lifecycle_manager: Existing lifecycle manager
                for individual secret tracking.
        """
        self._lifecycle_manager = lifecycle_manager or LifecycleManager()
        self._state = SecretsLifecycleState.CREATED
        self._lock = threading.RLock()
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []
        self._reload_hooks: List[Callable] = []
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

    @property
    def state(self) -> SecretsLifecycleState:
        """Get current platform lifecycle state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if secrets platform is running."""
        return self._state == SecretsLifecycleState.RUNNING

    @property
    def lifecycle_manager(self) -> LifecycleManager:
        """Get the underlying lifecycle manager."""
        return self._lifecycle_manager

    def add_startup_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a startup hook."""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a shutdown hook."""
        self._shutdown_hooks.append(hook)

    def add_reload_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a reload hook."""
        self._reload_hooks.append(hook)

    async def startup(
        self,
    ) -> Dict[str, Any]:
        """
        Start the secrets platform.

        Executes startup hooks and transitions
        to RUNNING state.

        Returns:
            Startup result.
        """
        with self._lock:
            if self._state not in (
                SecretsLifecycleState.CREATED,
                SecretsLifecycleState.STOPPED,
            ):
                return {
                    "success": False,
                    "error": f"Cannot start from state {self._state}",
                }

            self._state = SecretsLifecycleState.STARTING

        try:
            results = []
            for hook in self._startup_hooks:
                if asyncio.iscoroutinefunction(hook):
                    result = await hook()
                else:
                    result = hook()
                results.append(result)

            self._started_at = datetime.utcnow()
            self._state = SecretsLifecycleState.RUNNING

            return {
                "success": True,
                "state": self._state.value,
                "started_at": self._started_at.isoformat(),
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = SecretsLifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
                "state": self._state.value,
            }

    async def reload(
        self,
    ) -> Dict[str, Any]:
        """
        Reload the secrets platform.

        Returns:
            Reload result.
        """
        with self._lock:
            if self._state != SecretsLifecycleState.RUNNING:
                return {
                    "success": False,
                    "error": f"Cannot reload from state {self._state}",
                }

            self._state = SecretsLifecycleState.RELOADING

        try:
            results = []
            for hook in self._reload_hooks:
                if asyncio.iscoroutinefunction(hook):
                    result = await hook()
                else:
                    result = hook()
                results.append(result)

            self._state = SecretsLifecycleState.RUNNING

            return {
                "success": True,
                "state": self._state.value,
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = SecretsLifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
            }

    async def shutdown(
        self,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Gracefully shut down the secrets platform.

        Args:
            timeout: Maximum shutdown time.

        Returns:
            Shutdown result.
        """
        with self._lock:
            if self._state == SecretsLifecycleState.STOPPED:
                return {"success": True, "state": "already_stopped"}

            self._state = SecretsLifecycleState.STOPPING

        try:
            results = []
            for hook in reversed(self._shutdown_hooks):
                try:
                    if asyncio.iscoroutinefunction(hook):
                        result = await asyncio.wait_for(
                            hook(),
                            timeout=timeout,
                        )
                    else:
                        result = hook()
                    results.append(result)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

            self._stopped_at = datetime.utcnow()
            self._state = SecretsLifecycleState.STOPPED

            return {
                "success": True,
                "state": self._state.value,
                "stopped_at": self._stopped_at.isoformat(),
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = SecretsLifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
            }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get secrets lifecycle status."""
        return {
            "state": self._state.value,
            "is_running": self.is_running,
            "started_at": (
                self._started_at.isoformat()
                if self._started_at
                else None
            ),
            "stopped_at": (
                self._stopped_at.isoformat()
                if self._stopped_at
                else None
            ),
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
            "reload_hooks": len(self._reload_hooks),
            "secret_lifecycles": self._lifecycle_manager.get_stats(),
        }