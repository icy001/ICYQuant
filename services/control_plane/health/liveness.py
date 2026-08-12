"""
Liveness — "is the process/service alive?".

Liveness answers a much weaker question than health:

    Liveness = ALIVE     →  the process has not died
    Readiness = NOT_READY →  it is still not safe to trade with it

Sources are unified behind the :class:`LivenessProbe` abstraction:

    Heartbeat  /  Process Probe  /  Service Probe
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from .heartbeat import Heartbeat, utcnow


class LivenessStatus(str, Enum):
    """Whether a process/service is alive."""

    ALIVE = "ALIVE"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"

    @property
    def is_alive(self) -> bool:
        return self is LivenessStatus.ALIVE


@dataclass
class LivenessEvaluation:
    """Result of evaluating a component's liveness."""

    component_id: str
    status: LivenessStatus
    source: str = "probe"
    detail: str = ""
    evaluated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "source": self.source,
            "detail": self.detail,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class LivenessProbe(ABC):
    """Abstraction over every liveness source (heartbeat / process / service)."""

    @abstractmethod
    def check(self, component_id: str, now: Optional[datetime] = None) -> LivenessStatus:
        """Return the liveness of ``component_id`` at ``now``."""


class HeartbeatLivenessProbe(LivenessProbe):
    """Liveness derived from heartbeat freshness.

    A heartbeat received within ``timeout`` seconds means the process is
    alive; older heartbeats or the absence of any heartbeat means it is not.
    """

    def __init__(
        self,
        last_heartbeat: Callable[[str], Optional[Heartbeat]],
        timeout: float = 5.0,
    ) -> None:
        self._last_heartbeat = last_heartbeat
        self.timeout = timeout

    def check(self, component_id: str, now: Optional[datetime] = None) -> LivenessStatus:
        now = now or utcnow()
        heartbeat = self._last_heartbeat(component_id)
        if heartbeat is None:
            return LivenessStatus.UNKNOWN
        age = (now - heartbeat.timestamp).total_seconds()
        return LivenessStatus.ALIVE if age <= self.timeout else LivenessStatus.DEAD


class StaticLivenessProbe(LivenessProbe):
    """Liveness probe backed by a mapping (used for tests and adapters)."""

    def __init__(
        self,
        statuses: Optional[dict] = None,
        default: LivenessStatus = LivenessStatus.UNKNOWN,
    ) -> None:
        self._statuses = dict(statuses or {})
        self.default = default

    def check(self, component_id: str, now: Optional[datetime] = None) -> LivenessStatus:
        return self._statuses.get(component_id, self.default)


class FunctionLivenessProbe(LivenessProbe):
    """Wrap an arbitrary ``callable`` as a liveness probe."""

    def __init__(self, fn: Callable[[str], LivenessStatus]) -> None:
        self._fn = fn

    def check(self, component_id: str, now: Optional[datetime] = None) -> LivenessStatus:
        return self._fn(component_id)
