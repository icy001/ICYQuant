"""Incident context (Commit 27 Part 1.4, spec section 8).

IncidentContext 把 Alert / Metric / Trace / Incident 串起来。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IncidentContext:

    incident_id: str

    created_at: datetime

    detected_at: datetime

    environment: str

    source_alert_ids: tuple[str, ...]

    trace_ids: tuple[str, ...]

    correlation_key: str | None = None
