"""Alert model (Commit 27 Part 1.3, spec section 6).

Alert 是"发现异常"，不是"执行交易控制"（spec section 29）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import AlertState
from .severity import AlertSeverity


@dataclass(frozen=True)
class Alert:

    alert_id: str

    rule_id: str

    severity: AlertSeverity

    state: AlertState

    title: str

    message: str

    service_id: str | None

    labels: dict[str, str]

    fired_at: datetime

    resolved_at: datetime | None = None

    incident_id: str | None = None
