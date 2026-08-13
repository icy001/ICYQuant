"""Service health monitor (Commit 27 Part 1.1, spec sections 7, 12)."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.health import ServiceHealth
from ..models.service import ServiceState


class ServiceHealthMonitor:

    def __init__(self) -> None:

        self._health: dict[
            str,
            ServiceHealth,
        ] = {}

    def update(
        self,
        service_id: str,
        state: ServiceState,
        *,
        latency_ms: float | None = None,
        message: str = "",
        healthy: bool = True,
    ) -> ServiceHealth:

        health = ServiceHealth(
            service_id=service_id,
            state=state,
            checked_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            message=message,
            healthy=healthy,
        )

        self._health[service_id] = health

        return health

    def get(
        self,
        service_id: str,
    ) -> ServiceHealth | None:

        return self._health.get(service_id)
