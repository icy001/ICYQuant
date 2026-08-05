"""Multi-registry failover for ICYQuant service discovery HA.

Provides ``MultiRegistryFailover`` for managing primary, secondary,
and tertiary registries with automatic failover and dual-warm
standby support.

Supports: Primary -> Secondary -> Tertiary
Automatic switching with dual-warm standby.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MultiRegistryFailover:
    """Manages failover across multiple service registries.

    Supports a priority-based chain: primary -> secondary ->
    tertiary.  Automatic health verification and failover
    ensure seamless registry transitions.

    Registries are stored in priority order (lower number =
    higher priority).  The active registry is the first one
    that passes health verification.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._registries: Dict[str, Dict[str, Any]] = {}
        self._registry_order: List[str] = []
        self._active_registry: Optional[str] = None
        self._switch_count = 0
        self._failover_count = 0
        self._verification_count = 0
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _sorted_names(self) -> List[str]:
        return sorted(
            self._registry_order,
            key=lambda n: self._registries[n]["priority"],
        )

    # ── Public API ──

    def add_registry(
        self, name: str, registry: Any, priority: int = 0
    ) -> None:
        """Add a registry to the failover chain.

        Args:
            name: Unique registry name.
            registry: The registry object.
            priority: Lower values indicate higher priority.
        """
        if not name:
            raise ValueError("name cannot be empty.")
        with self._lock:
            self._registries[name] = {
                "registry": registry,
                "priority": int(priority),
                "healthy": True,
                "added_at": self._now_iso(),
                "last_check": 0.0,
            }
            if name not in self._registry_order:
                self._registry_order.append(name)
            if self._active_registry is None:
                self._active_registry = name
                logger.info(
                    "Activated registry '%s' as first registry.",
                    name,
                )
            logger.info(
                "Added registry '%s' (priority=%d).", name, priority
            )

    def remove_registry(self, name: str) -> None:
        """Remove a registry from the failover chain.

        Args:
            name: The registry name to remove.
        """
        with self._lock:
            if name not in self._registries:
                logger.warning(
                    "Registry '%s' not found; skipping removal.", name
                )
                return
            del self._registries[name]
            if name in self._registry_order:
                self._registry_order.remove(name)
            if self._active_registry == name:
                sorted_names = self._sorted_names()
                self._active_registry = (
                    sorted_names[0] if sorted_names else None
                )
                if self._active_registry is not None:
                    logger.info(
                        "Switched to '%s' after removing active registry.",
                        self._active_registry,
                    )
            logger.info("Removed registry '%s'.", name)

    def get_active_registry(self) -> str:
        """Return the name of the currently active registry.

        Returns:
            The active registry name, or empty string if none.
        """
        with self._lock:
            return self._active_registry or ""

    async def switch_to(self, name: str) -> Dict[str, Any]:
        """Switch to a specific registry by name.

        Args:
            name: The target registry name.

        Returns:
            A dictionary describing the switch result.
        """
        with self._lock:
            self._switch_count += 1

        result: Dict[str, Any] = {
            "switched": False,
            "target": name,
            "previous": None,
            "reason": "",
            "timestamp": self._now_iso(),
        }

        with self._lock:
            if name not in self._registries:
                result["reason"] = "registry_not_found"
                self._record_history("switch", result)
                return result
            result["previous"] = self._active_registry

        healthy = await self.verify_registry(name)
        if not healthy:
            result["reason"] = "registry_unhealthy"
            with self._lock:
                self._registries[name]["healthy"] = False
            self._record_history("switch", result)
            logger.warning(
                "Cannot switch to '%s': registry is unhealthy.", name
            )
            return result

        with self._lock:
            self._active_registry = name
            self._registries[name]["healthy"] = True

        result["switched"] = True
        result["reason"] = "ok"
        self._record_history("switch", result)
        logger.info(
            "Switched registry from '%s' to '%s'.",
            result["previous"],
            name,
        )
        return result

    async def failover(self) -> Dict[str, Any]:
        """Perform automatic failover to the next healthy registry.

        Iterates through registries in priority order and activates
        the first healthy one after the current active.

        Returns:
            A dictionary describing the failover result.
        """
        with self._lock:
            self._failover_count += 1
            current = self._active_registry

        result: Dict[str, Any] = {
            "failover": False,
            "from_registry": current,
            "to_registry": None,
            "reason": "",
            "timestamp": self._now_iso(),
        }

        sorted_names = self._sorted_names()

        if current is None:
            if sorted_names:
                target = sorted_names[0]
                healthy = await self.verify_registry(target)
                if healthy:
                    with self._lock:
                        self._active_registry = target
                    result["failover"] = True
                    result["to_registry"] = target
                    result["reason"] = "activated_first"
                    self._record_history("failover", result)
                    logger.info("Failover: activated '%s'.", target)
                    return result
            result["reason"] = "no_registries"
            self._record_history("failover", result)
            return result

        current_idx = (
            sorted_names.index(current) if current in sorted_names else -1
        )
        candidates = sorted_names[current_idx + 1 :]

        if not candidates:
            candidates = sorted_names[:current_idx]

        for candidate in candidates:
            healthy = await self.verify_registry(candidate)
            if healthy:
                with self._lock:
                    self._active_registry = candidate
                    self._registries[candidate]["healthy"] = True
                result["failover"] = True
                result["to_registry"] = candidate
                result["reason"] = "switched_to_backup"
                self._record_history("failover", result)
                logger.info(
                    "Failover: '%s' -> '%s'.", current, candidate
                )
                return result
            else:
                with self._lock:
                    self._registries[candidate]["healthy"] = False

        result["reason"] = "no_healthy_backup"
        self._record_history("failover", result)
        logger.warning(
            "Failover failed: no healthy backup for '%s'.", current
        )
        return result

    async def verify_registry(self, name: str) -> bool:
        """Verify health of a specific registry.

        Args:
            name: The registry name to verify.

        Returns:
            True if the registry is healthy.
        """
        with self._lock:
            self._verification_count += 1

        with self._lock:
            entry = self._registries.get(name)
            if entry is None:
                return False

        registry = entry["registry"]
        is_healthy_func = getattr(registry, "is_healthy", None)
        check_func = getattr(registry, "check", None)
        ping_func = getattr(registry, "ping", None)

        try:
            if callable(is_healthy_func):
                result = is_healthy_func()
                if asyncio.iscoroutine(result):
                    result = await result
                healthy = bool(result)
            elif callable(check_func):
                result = check_func()
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, dict):
                    healthy = bool(result.get("healthy", result.get("ok", False)))
                else:
                    healthy = bool(result)
            elif callable(ping_func):
                result = ping_func()
                if asyncio.iscoroutine(result):
                    result = await result
                healthy = bool(result)
            else:
                healthy = True
        except Exception as exc:
            logger.warning(
                "Verification failed for '%s': %s", name, exc
            )
            healthy = False

        with self._lock:
            if name in self._registries:
                self._registries[name]["healthy"] = healthy
                self._registries[name]["last_check"] = time.time()

        return healthy

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the multi-registry failover."""
        with self._lock:
            registries_info = {}
            for n, entry in self._registries.items():
                registries_info[n] = {
                    "priority": entry["priority"],
                    "healthy": entry["healthy"],
                    "last_check": entry["last_check"],
                }
            return {
                "active_registry": self._active_registry,
                "registry_count": len(self._registries),
                "registries": registries_info,
                "switch_count": self._switch_count,
                "failover_count": self._failover_count,
                "verification_count": self._verification_count,
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
                f"MultiRegistryFailover(active={self._active_registry!r}, "
                f"registries={len(self._registries)}, "
                f"failovers={self._failover_count})"
            )