"""Traffic drain for ICYQuant service discovery HA.

Provides ``TrafficDrain`` for gracefully stopping new requests
to an instance while allowing existing requests to complete.

Pipeline: Stop New Requests -> Finish Existing -> Drain Complete
          -> Remove
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrafficDrain:
    """Manages graceful traffic draining for service instances.

    Tracks draining state per (service, instance) pair and
    supports waiting for in-flight requests to complete
    before marking the drain as finished.

    Args:
        timeout: Default timeout in seconds for drain operations.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = float(timeout) if timeout > 0 else 30.0
        self._lock = threading.RLock()
        self._draining: Dict[str, Dict[str, Any]] = {}
        self._drain_count = 0
        self._complete_count = 0
        self._timeout_count = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    async def drain(
        self,
        service_name: str,
        instance_id: str,
        current_requests: int = 0,
    ) -> Dict[str, Any]:
        """Drain traffic from an instance.

        Stops new requests, waits for existing requests to
        complete, then marks the drain as finished.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            current_requests: Number of currently in-flight requests.

        Returns:
            A dictionary describing the drain result.
        """
        key = self._make_key(service_name, instance_id)
        start = time.monotonic()

        with self._lock:
            self._draining[key] = {
                "service_name": service_name,
                "instance_id": instance_id,
                "status": "draining",
                "started_at": time.time(),
                "started_at_iso": self._now_iso(),
                "current_requests": int(current_requests),
                "completed": False,
                "timed_out": False,
            }
            self._drain_count += 1

        logger.info(
            "Draining traffic from '%s/%s' (%d active requests).",
            service_name,
            instance_id,
            current_requests,
        )

        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "drained": False,
            "stages": {},
            "timestamp": self._now_iso(),
        }

        result["stages"]["begin"] = await self.begin_drain(
            service_name, instance_id
        )

        result["stages"]["finish"] = await self.finish_drain(
            service_name, instance_id
        )

        elapsed = time.monotonic() - start
        result["drained"] = result["stages"]["finish"].get(
            "completed", False
        )
        result["duration_s"] = elapsed

        if result["drained"]:
            with self._lock:
                self._complete_count += 1

        return result

    async def begin_drain(
        self, service_name: str, instance_id: str
    ) -> None:
        """Stop accepting new requests for the instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._draining.get(key)
            if record is None:
                self._draining[key] = {
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "status": "draining",
                    "started_at": time.time(),
                    "started_at_iso": self._now_iso(),
                    "current_requests": 0,
                    "no_new_requests": True,
                    "no_new_since": time.time(),
                    "completed": False,
                    "timed_out": False,
                }
            else:
                record["no_new_requests"] = True
                record["no_new_since"] = time.time()

        logger.debug(
            "New requests stopped for '%s/%s'.",
            service_name,
            instance_id,
        )

    async def finish_drain(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Wait for existing requests to complete.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the drain completion.
        """
        key = self._make_key(service_name, instance_id)
        deadline = time.time() + self._timeout

        while time.time() < deadline:
            with self._lock:
                record = self._draining.get(key)
                if record is None:
                    return {
                        "completed": True,
                        "message": "Drain record not found.",
                    }
                active = record.get("current_requests", 0)
                if active <= 0:
                    record["status"] = "drained"
                    record["completed"] = True
                    record["completed_at"] = time.time()
                    record["completed_at_iso"] = self._now_iso()
                    return {
                        "completed": True,
                        "active_requests": 0,
                        "message": "All requests completed.",
                    }
            await asyncio.sleep(0.05)

        with self._lock:
            record = self._draining.get(key)
            if record is not None:
                record["status"] = "timeout"
                record["timed_out"] = True
                record["completed_at"] = time.time()
                self._timeout_count += 1

        logger.warning(
            "Drain timed out for '%s/%s'.", service_name, instance_id
        )
        return {
            "completed": False,
            "timed_out": True,
            "message": "Drain timed out; some requests may still be active.",
        }

    def is_draining(
        self, service_name: str, instance_id: str
    ) -> bool:
        """Return whether an instance is currently draining.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._draining.get(key)
            if record is None:
                return False
            return record.get("status") not in ("drained", "timeout")

    def get_drain_status(
        self, service_name: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the drain status for an instance, if draining.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary with drain status fields, or None.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._draining.get(key)
            if record is None:
                return None
            return dict(record)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the traffic drain."""
        with self._lock:
            active = sum(
                1
                for r in self._draining.values()
                if r.get("status") not in ("drained", "timeout")
            )
            return {
                "timeout": self._timeout,
                "active_drains": active,
                "total_drains": self._drain_count,
                "completed_drains": self._complete_count,
                "timeout_drains": self._timeout_count,
                "total_tracked": len(self._draining),
            }

    def __repr__(self) -> str:
        with self._lock:
            active = sum(
                1
                for r in self._draining.values()
                if r.get("status") not in ("drained", "timeout")
            )
            return (
                f"TrafficDrain(active={active}, "
                f"completed={self._complete_count})"
            )