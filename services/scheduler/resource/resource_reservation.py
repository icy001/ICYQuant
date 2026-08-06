"""Resource Reservation — time-bounded resource holds.

The :class:`ResourceReservation` allows callers to reserve resources for a
future time window.  Useful for scheduled jobs that need guaranteed capacity
at a known start time (e.g., nightly batch, market open).
"""

from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


@dataclass
class ResourceReservation:
    """A time-bounded resource reservation.

    Usage::

        res = ResourceReservation(
            tenant_id="quant-team",
            cpu_cores=8, memory_mb=16384,
            start_at=datetime(...), end_at=datetime(...),
        )
    """

    reservation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tenant_id: str = ""
    job_id: str = ""
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    gpu_units: float = 0.0
    start_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    status: ReservationStatus = ReservationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return (self.end_at - self.start_at).total_seconds()

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.status in (ReservationStatus.PENDING, ReservationStatus.ACTIVE)
            and self.start_at <= now <= self.end_at
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.end_at

    def activate(self) -> None:
        self.status = ReservationStatus.ACTIVE

    def cancel(self) -> None:
        self.status = ReservationStatus.CANCELLED

    def fulfill(self) -> None:
        self.status = ReservationStatus.FULFILLED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "tenant_id": self.tenant_id, "job_id": self.job_id,
            "cpu_cores": self.cpu_cores, "memory_mb": self.memory_mb,
            "gpu_units": self.gpu_units,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "status": self.status.value,
        }


class ReservationManager:
    """Manages resource reservations.

    Usage::

        mgr = ReservationManager()
        mgr.create(tenant="t1", cpu=4, memory_mb=8192,
                   start=now, end=now + timedelta(hours=2))
        conflicts = mgr.find_conflicts(datetime(...), datetime(...))
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reservations: Dict[str, ResourceReservation] = {}

    def create(
        self, tenant_id: str, cpu_cores: float = 0.0, memory_mb: float = 0.0,
        gpu_units: float = 0.0, job_id: str = "",
        start_at: Optional[datetime] = None, end_at: Optional[datetime] = None,
    ) -> ResourceReservation:
        res = ResourceReservation(
            tenant_id=tenant_id, job_id=job_id,
            cpu_cores=cpu_cores, memory_mb=memory_mb, gpu_units=gpu_units,
            start_at=start_at or datetime.now(timezone.utc),
            end_at=end_at or datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with self._lock:
            self._reservations[res.reservation_id] = res
        return res

    def cancel(self, reservation_id: str) -> bool:
        with self._lock:
            res = self._reservations.get(reservation_id)
            if res:
                res.cancel()
                return True
            return False

    def get(self, reservation_id: str) -> Optional[ResourceReservation]:
        with self._lock:
            return self._reservations.get(reservation_id)

    def find_conflicts(
        self, start: datetime, end: datetime,
    ) -> Dict[str, float]:
        """Sum of reserved resources that overlap with [start, end]."""
        cpu_total = mem_total = gpu_total = 0.0
        with self._lock:
            for r in self._reservations.values():
                if r.status in (ReservationStatus.CANCELLED, ReservationStatus.EXPIRED):
                    continue
                if r.start_at < end and r.end_at > start:
                    cpu_total += r.cpu_cores
                    mem_total += r.memory_mb
                    gpu_total += r.gpu_units
        return {"cpu": cpu_total, "memory_mb": mem_total, "gpu": gpu_total}

    def list_active(self) -> List[ResourceReservation]:
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                r for r in self._reservations.values()
                if r.status in (ReservationStatus.PENDING, ReservationStatus.ACTIVE)
                and r.end_at > now
            ]

    def expire_stale(self) -> int:
        """Mark expired reservations and return count."""
        count = 0
        with self._lock:
            for r in self._reservations.values():
                if r.is_expired and r.status not in (ReservationStatus.EXPIRED, ReservationStatus.CANCELLED):
                    r.status = ReservationStatus.EXPIRED
                    count += 1
        return count

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            active = self.list_active()
            return {
                "total_reservations": len(self._reservations),
                "active": len(active),
                "total_cpu_reserved": sum(r.cpu_cores for r in active),
                "total_memory_reserved_mb": sum(r.memory_mb for r in active),
            }
