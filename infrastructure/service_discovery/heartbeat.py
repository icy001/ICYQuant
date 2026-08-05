"""Heartbeat service for ICYQuant service discovery.

Provides ``HeartbeatService`` for sending periodic heartbeats to keep
service instance leases alive. Tracks per-instance heartbeat latency,
beat counts, missed counts, and integrates with ``LeaseManager`` for
lease renewal. Thread-safe and async-friendly.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .exceptions import LeaseExpiredError, LeaseRenewalError, ServiceDiscoveryError
from .lease import LeaseManager, ServiceLease

logger = logging.getLogger(__name__)


class HeartbeatService:
    """Sends and tracks heartbeats for service instances.

    Each heartbeat records the timestamp, increments a beat counter,
    measures round-trip latency, and attempts to renew the associated
    lease via the supplied ``LeaseManager``. Missed heartbeats are
    recorded when a beat fails.

    Args:
        interval: Default interval between heartbeats in seconds.
        timeout: Maximum time to wait for a single heartbeat in seconds.
        lease_manager: Optional ``LeaseManager`` for lease renewal.
    """

    def __init__(
        self,
        interval: float = 5.0,
        timeout: float = 15.0,
        lease_manager: Optional[LeaseManager] = None,
    ) -> None:
        self._interval = float(interval) if interval > 0 else 5.0
        self._timeout = float(timeout) if timeout > 0 else 15.0
        self._lease_manager = lease_manager
        self._lock = threading.RLock()
        self._heartbeats: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._total_beats = 0
        self._total_missed = 0
        self._total_failures = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def _new_record(self, service_name: str, instance_id: str) -> Dict[str, Any]:
        return {
            "service_name": service_name,
            "instance_id": instance_id,
            "started": False,
            "last_heartbeat": None,
            "last_heartbeat_ts": 0.0,
            "beat_count": 0,
            "missed_count": 0,
            "latency": 0.0,
            "avg_latency": 0.0,
            "last_error": None,
            "interval": self._interval,
        }

    # ── Public API ──

    async def start(self, service_name: str, instance_id: str) -> None:
        """Start sending periodic heartbeats for an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            existing = self._heartbeats.get(key)
            if existing and existing.get("started"):
                logger.debug(
                    "Heartbeat already running for '%s'.", key
                )
                return
            record = existing or self._new_record(service_name, instance_id)
            record["started"] = True
            record["interval"] = self._interval
            self._heartbeats[key] = record
        logger.info(
            "Started heartbeat for '%s/%s' (interval=%.2fs).",
            service_name,
            instance_id,
            self._interval,
        )
        # Send an initial beat immediately.
        try:
            await self.beat(service_name, instance_id)
        except Exception:
            logger.exception(
                "Initial heartbeat failed for '%s/%s'.",
                service_name,
                instance_id,
            )

    async def beat(self, service_name: str, instance_id: str) -> Dict[str, Any]:
        """Send a single heartbeat for an instance.

        Renews the lease via the configured ``LeaseManager`` (if any)
        and updates tracking statistics.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the heartbeat result.

        Raises:
            ServiceDiscoveryError: If the heartbeat times out.
        """
        key = self._make_key(service_name, instance_id)
        start = time.monotonic()
        try:
            await asyncio.wait_for(
                self._do_beat(service_name, instance_id),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            latency = time.monotonic() - start
            self._record_failure(key, latency, f"heartbeat timeout: {exc}")
            raise ServiceDiscoveryError(
                f"Heartbeat timed out for '{service_name}/{instance_id}'."
            ) from exc
        except Exception as exc:
            latency = time.monotonic() - start
            self._record_failure(key, latency, str(exc))
            raise

        latency = time.monotonic() - start
        result = self._record_success(key, latency)
        logger.debug(
            "Heartbeat for '%s/%s' succeeded (latency=%.4fs).",
            service_name,
            instance_id,
            latency,
        )
        return result

    async def _do_beat(self, service_name: str, instance_id: str) -> None:
        """Perform the actual heartbeat work (lease renewal)."""
        if self._lease_manager is None:
            return
        loop = asyncio.get_event_loop()
        renewed = await loop.run_in_executor(
            None, self._lease_manager.renew_lease, service_name, instance_id
        )
        if renewed is None:
            logger.debug(
                "No active lease to renew for '%s/%s'; heartbeat recorded only.",
                service_name,
                instance_id,
            )

    async def stop(self, service_name: str, instance_id: str) -> None:
        """Stop sending heartbeats for an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        task: Optional[asyncio.Task] = None
        with self._lock:
            record = self._heartbeats.get(key)
            if record is not None:
                record["started"] = False
            task = self._tasks.pop(key, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info(
            "Stopped heartbeat for '%s/%s'.", service_name, instance_id
        )

    def is_beating(self, service_name: str, instance_id: str) -> bool:
        """Return whether heartbeats are currently active for an instance."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._heartbeats.get(key)
            return bool(record and record.get("started"))

    def get_heartbeat_info(
        self, service_name: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return heartbeat tracking info for an instance, if present."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._heartbeats.get(key)
            if record is None:
                return None
            return dict(record)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the heartbeat service."""
        with self._lock:
            active = sum(
                1 for r in self._heartbeats.values() if r.get("started")
            )
            total_latency = sum(
                r.get("latency", 0.0) for r in self._heartbeats.values()
            )
            tracked = len(self._heartbeats)
            avg_latency = (
                total_latency / tracked if tracked else 0.0
            )
            return {
                "interval": self._interval,
                "timeout": self._timeout,
                "tracked_instances": tracked,
                "active_instances": active,
                "total_beats": self._total_beats,
                "total_missed": self._total_missed,
                "total_failures": self._total_failures,
                "avg_latency": avg_latency,
                "lease_manager_attached": self._lease_manager is not None,
            }

    # ── Internal helpers ──

    def _record_success(self, key: str, latency: float) -> Dict[str, Any]:
        now_ts = time.time()
        with self._lock:
            record = self._heartbeats.get(key)
            if record is None:
                record = self._new_record(*key.split(":", 1))
                self._heartbeats[key] = record
            record["last_heartbeat"] = datetime.utcfromtimestamp(
                now_ts
            ).isoformat()
            record["last_heartbeat_ts"] = now_ts
            record["beat_count"] = int(record.get("beat_count", 0)) + 1
            record["latency"] = latency
            total_beats = record["beat_count"]
            prev_avg = float(record.get("avg_latency", 0.0))
            record["avg_latency"] = (
                (prev_avg * (total_beats - 1) + latency) / total_beats
                if total_beats > 0
                else latency
            )
            record["last_error"] = None
            self._total_beats += 1
            return dict(record)

    def _record_failure(
        self, key: str, latency: float, error: str
    ) -> None:
        with self._lock:
            record = self._heartbeats.get(key)
            if record is None:
                record = self._new_record(*key.split(":", 1))
                self._heartbeats[key] = record
            record["missed_count"] = int(record.get("missed_count", 0)) + 1
            record["latency"] = latency
            record["last_error"] = error
            self._total_missed += 1
            self._total_failures += 1
            logger.warning(
                "Heartbeat failure for '%s': %s", key, error
            )

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HeartbeatService(tracked={len(self._heartbeats)}, "
                f"beats={self._total_beats}, missed={self._total_missed})"
            )
