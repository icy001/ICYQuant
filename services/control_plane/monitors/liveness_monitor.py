"""
LivenessMonitor — answers "is the process alive?" through a LivenessProbe.

Sources (unified behind :class:`LivenessProbe`):

    Heartbeat  /  Process Probe  /  Service Probe

The monitor stays a thin wrapper: the actual decision about what to *do* with
a dead component belongs to the Control Plane, not to monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..health.heartbeat import utcnow
from ..health.liveness import LivenessEvaluation, LivenessProbe


@dataclass
class LivenessMonitor:
    """Evaluates liveness for a component using an injected probe."""

    probe: LivenessProbe
    source: str = "probe"

    def check(
        self,
        component_id: str,
        now: Optional[datetime] = None,
    ) -> LivenessEvaluation:
        now = now or utcnow()
        status = self.probe.check(component_id, now=now)
        return LivenessEvaluation(
            component_id=component_id,
            status=status,
            source=self.source,
            evaluated_at=now,
        )
