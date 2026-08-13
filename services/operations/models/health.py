"""Service health model (Commit 27 Part 1.1, spec section 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .service import ServiceState


@dataclass(frozen=True)
class ServiceHealth:

    service_id: str

    state: ServiceState

    checked_at: datetime

    latency_ms: float | None = None

    message: str = ""

    healthy: bool = True
