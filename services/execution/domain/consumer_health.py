from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConsumerHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ConsumerHealth:

    consumer_id: str

    status: ConsumerHealthStatus

    last_sequence: int

    failed_sequence: int | None = None

    error: str | None = None
