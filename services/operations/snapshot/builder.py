"""Operational snapshot builder (Commit 27 Part 1.1, spec sections 14-15).

运营人员需要的是"整个系统现在是什么状态"：

    Overall       HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN

聚合规则：
    unhealthy > 0                -> UNHEALTHY
    stopped   > 0                -> UNHEALTHY
    degraded  > 0                -> DEGRADED
    全部 HEALTHY                 -> HEALTHY
    其他（STARTING/UNKNOWN/空）  -> UNKNOWN
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.service import ServiceState
from ..models.snapshot import OperationalSnapshot


class OperationalSnapshotBuilder:

    def build(
        self,
        health_records,
    ) -> OperationalSnapshot:

        records = list(health_records)

        total = len(records)

        healthy = sum(
            1
            for item in records
            if item.state == ServiceState.HEALTHY
        )

        degraded = sum(
            1
            for item in records
            if item.state == ServiceState.DEGRADED
        )

        unhealthy = sum(
            1
            for item in records
            if item.state == ServiceState.UNHEALTHY
        )

        stopped = sum(
            1
            for item in records
            if item.state == ServiceState.STOPPED
        )

        if unhealthy > 0:
            overall = ServiceState.UNHEALTHY

        elif stopped > 0:
            overall = ServiceState.UNHEALTHY

        elif degraded > 0:
            overall = ServiceState.DEGRADED

        elif total > 0 and healthy == total:
            overall = ServiceState.HEALTHY

        else:
            overall = ServiceState.UNKNOWN

        return OperationalSnapshot(
            generated_at=datetime.now(timezone.utc),
            overall_state=overall,
            total_services=total,
            healthy_services=healthy,
            degraded_services=degraded,
            unhealthy_services=unhealthy,
            stopped_services=stopped,
        )
