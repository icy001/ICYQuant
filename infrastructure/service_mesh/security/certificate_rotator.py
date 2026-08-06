"""Certificate rotation for ICYQuant Service Mesh.

Provides ``CertificateRotator`` for automatic scheduled rotation,
emergency rotation, and rolling rotation of certificates.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .certificate_manager import CertificateManager

logger = logging.getLogger(__name__)


class RotationType(str):
    """Certificate rotation types."""

    SCHEDULED = "scheduled"
    EMERGENCY = "emergency"
    ROLLING = "rolling"


class CertificateRotator:
    """Automatic certificate rotation manager."""

    def __init__(
        self,
        cert_manager: CertificateManager,
        rotation_interval_s: float = 3600,
        renewal_threshold_hours: int = 6,
    ) -> None:
        self._cert_manager = cert_manager
        self._rotation_interval_s = rotation_interval_s
        self._renewal_threshold_hours = renewal_threshold_hours
        self._lock = threading.RLock()
        self._rotation_count = 0
        self._emergency_count = 0
        self._rolling_count = 0
        self._last_rotation: Optional[float] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def scheduled_rotation(self) -> Dict[str, Any]:
        """Perform scheduled rotation of expiring certificates."""
        expiring = self._cert_manager.get_expiring_soon(
            hours=self._renewal_threshold_hours
        )
        rotated = []
        for cert in expiring:
            try:
                new_cert = await self._cert_manager.rotate(cert.cert_id)
                rotated.append(new_cert.cert_id)
                with self._lock:
                    self._rotation_count += 1
            except Exception as exc:
                logger.warning("Failed to rotate %s: %s", cert.cert_id, exc)

        self._last_rotation = time.monotonic()
        logger.info("Scheduled rotation: %d certificates rotated", len(rotated))
        return {
            "type": RotationType.SCHEDULED,
            "rotated": rotated,
            "count": len(rotated),
        }

    async def emergency_rotation(self, cert_id: str, reason: str = "") -> Dict[str, Any]:
        """Perform emergency rotation of a specific certificate."""
        result = await self._cert_manager.rotate(cert_id)
        with self._lock:
            self._emergency_count += 1
            self._rotation_count += 1
        logger.warning("Emergency rotation: %s (reason: %s)", cert_id, reason)
        return {
            "type": RotationType.EMERGENCY,
            "old_cert_id": cert_id,
            "new_cert_id": result.cert_id,
            "reason": reason,
        }

    async def rolling_rotation(self, cert_ids: List[str]) -> Dict[str, Any]:
        """Perform rolling rotation of multiple certificates."""
        rotated = []
        for cert_id in cert_ids:
            try:
                new_cert = await self._cert_manager.rotate(cert_id)
                rotated.append({
                    "old": cert_id,
                    "new": new_cert.cert_id,
                })
                with self._lock:
                    self._rolling_count += 1
                    self._rotation_count += 1
                await asyncio.sleep(0.01)
            except Exception as exc:
                logger.warning("Rolling rotation failed for %s: %s", cert_id, exc)

        return {
            "type": RotationType.ROLLING,
            "rotated": rotated,
            "count": len(rotated),
        }

    async def start(self) -> None:
        """Start the automatic rotation loop."""
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._rotation_loop())

    async def stop(self) -> None:
        """Stop the automatic rotation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _rotation_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._rotation_interval_s)
                if self._running:
                    await self.scheduled_rotation()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Rotation loop error: %s", exc)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "rotation_count": self._rotation_count,
                "emergency_count": self._emergency_count,
                "rolling_count": self._rolling_count,
                "last_rotation": self._last_rotation,
                "interval_s": self._rotation_interval_s,
            }
