"""Health check registry for ICYQuant runtime services."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from shared.constants import APP_NAME, APP_VERSION

HealthCheckFn = Callable[[], Optional[str]]


@dataclass
class ServiceHealth:
    """Health state of a single logical service."""

    name: str
    check: Optional[HealthCheckFn] = None
    status: str = "UNKNOWN"  # UP / DOWN / UNKNOWN
    detail: str = ""
    last_checked: float = 0.0

    def check_now(self) -> "ServiceHealth":
        try:
            detail = self.check() if self.check else None
            self.status = "UP" if detail is None else "DOWN"
            self.detail = detail or "ok"
        except Exception as exc:  # noqa: BLE001
            self.status = "DOWN"
            self.detail = f"error: {exc}"
        self.last_checked = time.time()
        return self


@dataclass
class HealthRegistry:
    """Aggregated health of all runtime services."""

    services: dict[str, ServiceHealth] = field(default_factory=dict)

    def register(self, name: str, check: HealthCheckFn = None) -> None:
        self.services[name] = ServiceHealth(name=name, check=check)

    def check_all(self) -> dict[str, ServiceHealth]:
        for service in self.services.values():
            service.check_now()
        return self.services

    def snapshot(self) -> dict:
        services = self.check_all()
        return {
            "status": "READY" if all(s.status == "UP" for s in services.values()) else "DEGRADED",
            "app": APP_NAME,
            "version": APP_VERSION,
            "checked_at": time.time(),
            "services": {
                name: {
                    "status": s.status,
                    "detail": s.detail,
                }
                for name, s in services.items()
            },
        }
