"""Operational snapshot model (Commit 27 Part 1.1, spec section 13).

运营人员真正需要的不是 100 个独立 API，而是：
"现在整个系统到底是什么状态？"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .service import ServiceState


@dataclass(frozen=True)
class OperationalSnapshot:

    generated_at: datetime

    overall_state: ServiceState

    total_services: int

    healthy_services: int

    degraded_services: int

    unhealthy_services: int

    stopped_services: int
