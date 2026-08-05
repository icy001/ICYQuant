"""Quarantine manager for ICYQuant service discovery.

Provides ``QuarantineManager`` for temporarily isolating unhealthy
service instances from traffic routing. Supports automatic recovery
and manual release of quarantined instances.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .events import ServiceEvent, ServiceEventBus, ServiceEventType

logger = logging.getLogger(__name__)


class QuarantineManager:
    """Manages quarantined service instances.

    Tracks quarantined (service, instance) pairs with a reason, the
    originating event, and timestamps. Supports automatic recovery
    after a configurable TTL and manual release.

    Args:
        event_bus: Optional ``ServiceEventBus`` for publishing
            quarantine/release events.
        auto_release_ttl: Default TTL after which a quarantined
            instance is automatically released (seconds). 0 disables.
    """

    def __init__(
        self,
        event_bus: Optional[ServiceEventBus] = None,
        auto_release_ttl: float = 300.0,
    ) -> None:
        self._event_bus = event_bus
        self._auto_release_ttl = (
            float(auto_release_ttl) if auto_release_ttl > 0 else 0.0
        )
        self._lock = threading.RLock()
        self._quarantined: Dict[str, Dict[str, Any]] = {}
        self._quarantine_count = 0
        self._release_count = 0
        self._auto_release_count = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    # ── Public API ──

    def quarantine(
        self,
        service_name: str,
        instance_id: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Quarantine an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            reason: Optional reason for quarantine.

        Returns:
            A dictionary describing the quarantine record.
        """
        key = self._make_key(service_name, instance_id)
        now = time.time()
        record = {
            "service_name": service_name,
            "instance_id": instance_id,
            "reason": reason,
            "quarantined_at": now,
            "quarantined_at_iso": datetime.utcfromtimestamp(now).isoformat(),
            "expires_at": (
                now + self._auto_release_ttl
                if self._auto_release_ttl > 0
                else 0.0
            ),
            "released": False,
            "released_at": None,
        }
        with self._lock:
            self._quarantined[key] = record
            self._quarantine_count += 1
        logger.warning(
            "Quarantined '%s/%s': %s", service_name, instance_id, reason or "unspecified"
        )
        self._publish_event(
            ServiceEventType.SERVICE_UPDATED,
            service_name,
            instance_id,
            {"action": "quarantined", "reason": reason},
        )
        return dict(record)

    def release(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Release an instance from quarantine.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the release result.
        """
        key = self._make_key(service_name, instance_id)
        now = time.time()
        with self._lock:
            record = self._quarantined.pop(key, None)
            if record is not None:
                record["released"] = True
                record["released_at"] = now
                record["released_at_iso"] = datetime.utcfromtimestamp(
                    now
                ).isoformat()
                self._release_count += 1
        logger.info(
            "Released '%s/%s' from quarantine.", service_name, instance_id
        )
        self._publish_event(
            ServiceEventType.SERVICE_UPDATED,
            service_name,
            instance_id,
            {"action": "released"},
        )
        if record is None:
            return {
                "service_name": service_name,
                "instance_id": instance_id,
                "released": False,
                "message": "Instance was not quarantined.",
                "timestamp": now,
            }
        return dict(record)

    def is_quarantined(self, service_name: str, instance_id: str) -> bool:
        """Return whether an instance is currently quarantined."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            return key in self._quarantined

    def get_quarantined(self) -> List[Dict[str, Any]]:
        """Return a list of all currently quarantined instances."""
        with self._lock:
            return [dict(r) for r in self._quarantined.values()]

    def get_quarantine_info(
        self, service_name: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return quarantine info for an instance, if present."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._quarantined.get(key)
            if record is None:
                return None
            return dict(record)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the quarantine manager."""
        with self._lock:
            return {
                "quarantined_count": len(self._quarantined),
                "quarantine_total": self._quarantine_count,
                "release_total": self._release_count,
                "auto_release_total": self._auto_release_count,
                "auto_release_ttl": self._auto_release_ttl,
                "event_bus_attached": self._event_bus is not None,
            }

    # ── Auto-release ──

    def release_expired(self) -> int:
        """Release all quarantined instances whose TTL has elapsed.

        Returns:
            The number of instances automatically released.
        """
        if self._auto_release_ttl <= 0:
            return 0
        now = time.time()
        to_release: List[str] = []
        with self._lock:
            for key, record in self._quarantined.items():
                expires_at = record.get("expires_at", 0.0)
                if expires_at and expires_at <= now:
                    to_release.append(key)
        released = 0
        for key in to_release:
            service_name, _, instance_id = key.partition(":")
            self.release(service_name, instance_id)
            with self._lock:
                self._auto_release_count += 1
            released += 1
        if released:
            logger.info(
                "Auto-released %d quarantined instance(s).", released
            )
        return released

    # ── Internal helpers ──

    def _publish_event(
        self,
        event_type: ServiceEventType,
        service_name: str,
        instance_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Best-effort event publishing (synchronous wrapper)."""
        if self._event_bus is None:
            return
        try:
            import asyncio

            event = ServiceEvent(
                event_type=event_type,
                service_name=service_name,
                instance_id=instance_id,
                data=dict(data),
            )
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._event_bus.publish(event))
                else:
                    loop.run_until_complete(self._event_bus.publish(event))
            except RuntimeError:
                logger.debug("No running event loop for quarantine event.")
        except Exception:
            logger.exception("Failed to publish quarantine event.")

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"QuarantineManager(quarantined={len(self._quarantined)})"
            )
