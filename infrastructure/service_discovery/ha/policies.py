"""HA policy management for ICYQuant service discovery HA.

Provides ``HAPolicy`` enum and ``HAPolicyManager`` for managing
service-level HA policies including auto-recovery, maintenance
mode, and priority-based failover strategies.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAPolicy(Enum):
    """HA policy types for service-level configuration."""

    AUTO_RECOVERY = "auto_recovery"
    MANUAL_RECOVERY = "manual_recovery"
    PRIORITY_FAILOVER = "priority_failover"
    REGION_PRIORITY = "region_priority"
    ZONE_PRIORITY = "zone_priority"
    MAINTENANCE_MODE = "maintenance_mode"


class HAPolicyManager:
    """Manages HA policies per service.

    Supports per-service policy configuration, global maintenance
    mode toggling, and auto-recovery enablement.

    Default policy: AUTO_RECOVERY for all services.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._service_policies: Dict[str, HAPolicy] = {}
        self._maintenance_mode = False
        self._policy_change_count = 0
        self._maintenance_toggle_count = 0
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    def set_policy(
        self, service_name: str, policy: HAPolicy
    ) -> None:
        """Set the HA policy for a service.

        Args:
            service_name: The logical service name.
            policy: The HAPolicy to apply.
        """
        if not service_name:
            raise ValueError("service_name cannot be empty.")
        if not isinstance(policy, HAPolicy):
            raise TypeError("policy must be an HAPolicy enum value.")

        with self._lock:
            old_policy = self._service_policies.get(service_name)
            self._service_policies[service_name] = policy
            self._policy_change_count += 1

        result = {
            "service_name": service_name,
            "old_policy": old_policy.value if old_policy else None,
            "new_policy": policy.value,
            "timestamp": self._now_iso(),
        }
        self._record_history("set_policy", result)
        logger.info(
            "Set HA policy for '%s': %s -> %s.",
            service_name,
            old_policy.value if old_policy else "none",
            policy.value,
        )

    def get_policy(self, service_name: str) -> HAPolicy:
        """Get the current HA policy for a service.

        Args:
            service_name: The logical service name.

        Returns:
            The current HAPolicy, or AUTO_RECOVERY as default.
        """
        with self._lock:
            return self._service_policies.get(
                service_name, HAPolicy.AUTO_RECOVERY
            )

    def is_auto_recovery_enabled(self, service_name: str) -> bool:
        """Check whether auto-recovery is enabled for a service.

        Args:
            service_name: The logical service name.

        Returns:
            True if the service uses AUTO_RECOVERY policy.
        """
        with self._lock:
            policy = self._service_policies.get(
                service_name, HAPolicy.AUTO_RECOVERY
            )
            return policy == HAPolicy.AUTO_RECOVERY

    def set_maintenance_mode(self, enabled: bool) -> None:
        """Enable or disable global maintenance mode.

        In maintenance mode, automatic failover and recovery
        are suspended.

        Args:
            enabled: True to enable maintenance mode.
        """
        with self._lock:
            self._maintenance_mode = bool(enabled)
            self._maintenance_toggle_count += 1

        result = {
            "maintenance_mode": self._maintenance_mode,
            "timestamp": self._now_iso(),
        }
        self._record_history("maintenance_mode", result)
        logger.info(
            "Maintenance mode %s.",
            "enabled" if self._maintenance_mode else "disabled",
        )

    def is_maintenance_mode(self) -> bool:
        """Check whether maintenance mode is active.

        Returns:
            True if maintenance mode is enabled.
        """
        with self._lock:
            return self._maintenance_mode

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the policy manager."""
        with self._lock:
            policy_counts: Dict[str, int] = {}
            for policy in self._service_policies.values():
                key = policy.value
                policy_counts[key] = policy_counts.get(key, 0) + 1

            return {
                "service_count": len(self._service_policies),
                "policy_distribution": policy_counts,
                "maintenance_mode": self._maintenance_mode,
                "policy_change_count": self._policy_change_count,
                "maintenance_toggle_count": (
                    self._maintenance_toggle_count
                ),
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAPolicyManager(services={len(self._service_policies)}, "
                f"maintenance={self._maintenance_mode})"
            )