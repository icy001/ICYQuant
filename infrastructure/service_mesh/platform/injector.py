"""Sidecar Injection Framework for the Service Mesh Platform.

Provides ``SidecarInjector`` for manual, automatic, container,
and Kubernetes sidecar injection into business services.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class InjectionMode(str, Enum):
    """Mode of sidecar injection."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    CONTAINER = "container"
    KUBERNETES = "kubernetes"


class InjectionStatus(str, Enum):
    """Status of a sidecar injection."""

    PENDING = "pending"
    INJECTING = "injecting"
    INJECTED = "injected"
    FAILED = "failed"
    REMOVED = "removed"


class InjectionRecord:
    """Record of a sidecar injection."""

    def __init__(
        self,
        injection_id: str,
        service_name: str,
        mode: InjectionMode,
    ) -> None:
        self.injection_id = injection_id
        self.service_name = service_name
        self.mode = mode
        self.status = InjectionStatus.PENDING
        self.sidecar_id: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

    def complete(self, sidecar_id: str) -> None:
        self.status = InjectionStatus.INJECTED
        self.sidecar_id = sidecar_id
        self.completed_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        self.status = InjectionStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()

    def remove(self) -> None:
        self.status = InjectionStatus.REMOVED
        self.completed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "injection_id": self.injection_id,
            "service_name": self.service_name,
            "mode": self.mode.value,
            "status": self.status.value,
            "sidecar_id": self.sidecar_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            "error": self.error,
            "metadata": self.metadata,
        }


class SidecarInjector:
    """Framework for injecting sidecar proxies into services."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._records: Dict[str, InjectionRecord] = {}
        self._service_index: Dict[str, str] = {}
        self._next_id = 0
        self._injection_handlers: Dict[InjectionMode, Callable] = {}
        self._gray_scale_enabled = False
        self._gray_scale_percentage = 0
        self._register_default_handlers()

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"inj-{self._next_id}"

    def _register_default_handlers(self) -> None:
        self._injection_handlers[InjectionMode.MANUAL] = (
            self._inject_manual
        )
        self._injection_handlers[InjectionMode.AUTOMATIC] = (
            self._inject_automatic
        )
        self._injection_handlers[InjectionMode.CONTAINER] = (
            self._inject_container
        )
        self._injection_handlers[InjectionMode.KUBERNETES] = (
            self._inject_kubernetes
        )

    def register_handler(
        self,
        mode: InjectionMode,
        handler: Callable,
    ) -> None:
        self._injection_handlers[mode] = handler

    def enable_gray_scale(
        self, percentage: int = 10
    ) -> None:
        self._gray_scale_enabled = True
        self._gray_scale_percentage = max(0, min(100, percentage))

    def disable_gray_scale(self) -> None:
        self._gray_scale_enabled = False
        self._gray_scale_percentage = 0

    def _should_inject(self, service_name: str) -> bool:
        if not self._gray_scale_enabled:
            return True
        hash_val = hash(service_name) % 100
        return hash_val < self._gray_scale_percentage

    async def inject(
        self,
        service_name: str,
        mode: InjectionMode = InjectionMode.MANUAL,
        sidecar_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Inject a sidecar into a service."""
        if not self._should_inject(service_name):
            return {
                "success": True,
                "injected": False,
                "reason": "gray_scale_skipped",
                "service": service_name,
            }

        injection_id = self._generate_id()
        record = InjectionRecord(injection_id, service_name, mode)

        handler = self._injection_handlers.get(mode)
        if handler is None:
            record.fail(f"No handler for mode: {mode.value}")
            self._add_record(record)
            return {
                "success": False,
                "error": f"No handler for mode: {mode.value}",
                "injection_id": injection_id,
            }

        record.status = InjectionStatus.INJECTING
        self._telemetry.log_injection(
            service_name, mode.value, "started",
            {"injection_id": injection_id},
        )

        try:
            result = handler(service_name, sidecar_config)
            if asyncio.iscoroutine(result):
                result = await result

            if result.get("success"):
                sidecar_id = result.get("sidecar_id", "")
                record.complete(sidecar_id)
                self._metrics.increment_injection_total(
                    {"mode": mode.value, "service": service_name}
                )
                self._telemetry.log_injection(
                    service_name, mode.value, "completed",
                    {"injection_id": injection_id,
                     "sidecar_id": sidecar_id},
                )
            else:
                record.fail(result.get("error", "Unknown error"))
                self._telemetry.log_injection(
                    service_name, mode.value, "failed",
                    {"injection_id": injection_id,
                     "error": record.error},
                )

        except Exception as exc:
            record.fail(str(exc))
            self._telemetry.log_injection(
                service_name, mode.value, "failed",
                {"injection_id": injection_id, "error": str(exc)},
            )

        self._add_record(record)

        return {
            "success": record.status == InjectionStatus.INJECTED,
            "injection_id": injection_id,
            "sidecar_id": record.sidecar_id,
            "status": record.status.value,
        }

    async def remove(
        self, injection_id: str
    ) -> Dict[str, Any]:
        """Remove an injected sidecar."""
        record = self._records.get(injection_id)
        if record is None:
            return {"success": False, "error": "Injection not found"}

        record.remove()
        self._telemetry.log_injection(
            record.service_name, record.mode.value, "removed",
            {"injection_id": injection_id},
        )
        return {"success": True, "injection_id": injection_id}

    def _add_record(self, record: InjectionRecord) -> None:
        with self._lock:
            self._records[record.injection_id] = record
            self._service_index[record.service_name] = (
                record.injection_id
            )

    def get_record(self, injection_id: str) -> Optional[InjectionRecord]:
        return self._records.get(injection_id)

    def get_record_by_service(
        self, service_name: str
    ) -> Optional[InjectionRecord]:
        injection_id = self._service_index.get(service_name)
        if injection_id:
            return self._records.get(injection_id)
        return None

    def list_records(
        self, status: Optional[InjectionStatus] = None
    ) -> List[Dict[str, Any]]:
        records = list(self._records.values())
        if status:
            records = [r for r in records if r.status == status]
        return [r.to_dict() for r in records]

    # Default injection handlers
    def _inject_manual(
        self,
        service_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sidecar_id = f"sidecar-{service_name}-{int(time.monotonic())}"
        return {
            "success": True,
            "sidecar_id": sidecar_id,
            "mode": "manual",
        }

    def _inject_automatic(
        self,
        service_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sidecar_id = f"sidecar-auto-{service_name}-{int(time.monotonic())}"
        return {
            "success": True,
            "sidecar_id": sidecar_id,
            "mode": "automatic",
        }

    def _inject_container(
        self,
        service_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sidecar_id = f"sidecar-ctr-{service_name}-{int(time.monotonic())}"
        return {
            "success": True,
            "sidecar_id": sidecar_id,
            "mode": "container",
        }

    def _inject_kubernetes(
        self,
        service_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Reserved for future Kubernetes integration
        return {
            "success": True,
            "sidecar_id": f"sidecar-k8s-{service_name}",
            "mode": "kubernetes",
            "note": "Kubernetes injection is reserved for future use",
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_injections": len(self._records),
                "by_status": self._count_by_status(),
                "by_mode": self._count_by_mode(),
                "gray_scale_enabled": self._gray_scale_enabled,
                "gray_scale_percentage": self._gray_scale_percentage,
            }

    def _count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._records.values():
            status = r.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _count_by_mode(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._records.values():
            mode = r.mode.value
            counts[mode] = counts.get(mode, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"SidecarInjector(records={len(self._records)}, "
                f"gray_scale={self._gray_scale_enabled})"
            )
