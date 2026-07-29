"""Failover Manager.

Manages failover to backup services when primary becomes unavailable.

Examples:
- Primary Broker → Backup Broker
- Primary Redis → Read Replica
- Primary Database → Standby

Usage::

    fm = FailoverManager()
    fm.add_target(FailoverTarget(
        name="broker",
        primary="broker_primary",
        backup="broker_backup",
        health_check_fn=lambda t: check_health(t),
        switch_fn=lambda src, dst: switch_broker(src, dst),
    ))
    fm.check_and_failover(dependency_report)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class FailoverStatus(str, Enum):
    PRIMARY = "primary"
    FAILED_OVER = "failed_over"
    FAILING = "failing"
    SWITCHING = "switching"


@dataclass
class FailoverTarget:
    """A service with a primary and backup for failover."""

    name: str
    primary: str
    backup: str
    health_check_fn: Callable[[str], bool]
    switch_fn: Callable[[str, str], bool]  # (from_target, to_target) → success
    auto_failback: bool = True
    cooldown_seconds: float = 30.0
    max_failovers: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "primary": self.primary,
            "backup": self.backup,
            "auto_failback": self.auto_failback,
            "cooldown_seconds": self.cooldown_seconds,
            "max_failovers": self.max_failovers,
        }


@dataclass
class FailoverRecord:
    """Record of a failover event."""

    target_name: str
    from_target: str
    to_target: str
    success: bool
    timestamp: float = field(default_factory=time.time)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_name": self.target_name,
            "from_target": self.from_target,
            "to_target": self.to_target,
            "success": self.success,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


class FailoverManager:
    """Manages failover between primary and backup services.

    Monitors health of primary services and automatically switches
    to backup when primary becomes unhealthy. Supports automatic
    failback when primary recovers.
    """

    def __init__(self) -> None:
        self._targets: Dict[str, FailoverTarget] = {}
        self._current_state: Dict[str, str] = {}  # target_name → active target
        self._status: Dict[str, FailoverStatus] = {}
        self._failover_count: Dict[str, int] = {}
        self._last_failover: Dict[str, float] = {}
        self._history: List[FailoverRecord] = []

    def add_target(self, target: FailoverTarget) -> None:
        """Register a failover target."""
        self._targets[target.name] = target
        self._current_state[target.name] = target.primary
        self._status[target.name] = FailoverStatus.PRIMARY
        self._failover_count[target.name] = 0
        self._last_failover[target.name] = 0.0

    def remove_target(self, name: str) -> None:
        """Remove a failover target."""
        self._targets.pop(name, None)
        self._current_state.pop(name, None)
        self._status.pop(name, None)
        self._failover_count.pop(name, None)
        self._last_failover.pop(name, None)

    def get_target(self, name: str) -> Optional[FailoverTarget]:
        """Get a failover target by name."""
        return self._targets.get(name)

    def get_active(self, name: str) -> Optional[str]:
        """Get the currently active target for a service."""
        return self._current_state.get(name)

    def get_status(self, name: str) -> FailoverStatus:
        """Get current failover status for a service."""
        return self._status.get(name, FailoverStatus.PRIMARY)

    def check_and_failover(
        self,
        health_context: Optional[Dict[str, Any]] = None,
    ) -> List[FailoverRecord]:
        """Check all targets and perform failover if needed.

        Returns list of failover events that occurred.
        """
        now = time.time()
        events: List[FailoverRecord] = []

        for target in self._targets.values():
            current = self._current_state[target.name]

            # Check if current target is healthy
            try:
                healthy = target.health_check_fn(current)
            except Exception:
                healthy = False

            if healthy:
                # If we're on backup and primary is healthy again, failback
                if (
                    current == target.backup
                    and target.auto_failback
                    and self._status[target.name] == FailoverStatus.FAILED_OVER
                ):
                    try:
                        primary_healthy = target.health_check_fn(target.primary)
                    except Exception:
                        primary_healthy = False

                    if primary_healthy:
                        # Check cooldown
                        last = self._last_failover.get(target.name, 0.0)
                        if now - last >= target.cooldown_seconds:
                            self._do_switch(target, target.backup, target.primary, events)
                continue

            # Current target is unhealthy - need to failover
            if current == target.primary:
                new_target = target.backup
            else:
                # Already on backup and it's failing too
                # Try primary as a last resort
                new_target = target.primary

            # Check cooldown
            last = self._last_failover.get(target.name, 0.0)
            if now - last < target.cooldown_seconds:
                continue

            # Check max failovers
            if self._failover_count.get(target.name, 0) >= target.max_failovers:
                continue

            # Verify the new target is healthy
            try:
                new_healthy = target.health_check_fn(new_target)
            except Exception:
                new_healthy = False

            if new_healthy:
                self._do_switch(target, current, new_target, events)

        return events

    def force_failover(self, target_name: str) -> Optional[FailoverRecord]:
        """Force immediate failover for a target."""
        target = self._targets.get(target_name)
        if not target:
            return None

        current = self._current_state[target_name]
        new_target = target.backup if current == target.primary else target.primary

        events: List[FailoverRecord] = []
        self._do_switch(target, current, new_target, events)
        return events[0] if events else None

    def get_all_status(self) -> Dict[str, Any]:
        """Get status for all failover targets."""
        result = {}
        for name, target in self._targets.items():
            result[name] = {
                "active": self._current_state.get(name),
                "status": self._status.get(name, FailoverStatus.PRIMARY).value,
                "failover_count": self._failover_count.get(name, 0),
                "primary": target.primary,
                "backup": target.backup,
                "auto_failback": target.auto_failback,
            }
        return result

    def get_history(self, limit: int = 100) -> List[FailoverRecord]:
        """Get failover history."""
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_switch(
        self,
        target: FailoverTarget,
        from_target: str,
        to_target: str,
        events: List[FailoverRecord],
    ) -> None:
        """Perform a switch from one target to another."""
        self._status[target.name] = FailoverStatus.SWITCHING
        now = time.time()

        try:
            success = target.switch_fn(from_target, to_target)
        except Exception:
            success = False

        if success:
            self._current_state[target.name] = to_target
            self._status[target.name] = (
                FailoverStatus.PRIMARY
                if to_target == target.primary
                else FailoverStatus.FAILED_OVER
            )
            self._failover_count[target.name] = self._failover_count.get(target.name, 0) + 1
            self._last_failover[target.name] = now

            record = FailoverRecord(
                target_name=target.name,
                from_target=from_target,
                to_target=to_target,
                success=True,
                reason=f"Failover from {from_target} to {to_target}",
            )
            events.append(record)
            self._history.append(record)
        else:
            self._status[target.name] = FailoverStatus.FAILING
            record = FailoverRecord(
                target_name=target.name,
                from_target=from_target,
                to_target=to_target,
                success=False,
                reason=f"Failed to switch from {from_target} to {to_target}",
            )
            events.append(record)
            self._history.append(record)

        # Trim history
        if len(self._history) > 200:
            self._history = self._history[-200:]
