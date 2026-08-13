"""Incident severity escalation (Commit 27 Part 1.4, spec sections 21-22, 37-38).

Severity 只能单向:

    MAJOR
      ↓
    CRITICAL

不能反向:

    CRITICAL
      ↓
    MAJOR

除非 Incident 已进入恢复阶段，并且明确重新评估。

时间型升级规则 (spec section 22):

    MAJOR 持续 5 minutes 没有缓解 -> CRITICAL
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .severity import IncidentSeverity
from .state import IncidentState


@dataclass(frozen=True)
class EscalationPolicy:
    """持续 duration_seconds 未缓解则升级到 escalate_to。"""

    escalate_to: IncidentSeverity

    duration_seconds: int


class IncidentEscalator:

    def escalate(
        self,
        current: IncidentSeverity,
        target: IncidentSeverity,
    ) -> IncidentSeverity:

        if target > current:
            return target

        return current

    def evaluate(
        self,
        incident,
        policies=(),
        now: datetime | None = None,
    ) -> IncidentSeverity:
        """时间型升级评估。

        仅当 Incident 尚未进入 MITIGATING（没有缓解）时，
        超过 policy 时长才触发升级；一旦开始缓解即停止自动升级。
        """

        if incident.state in (
            IncidentState.MITIGATING,
            IncidentState.RECOVERING,
            IncidentState.MONITORING,
            IncidentState.RESOLVED,
            IncidentState.CLOSED,
        ):
            return incident.severity

        now = now or datetime.now(timezone.utc)

        elapsed = (
            now - incident.context.detected_at
        ).total_seconds()

        target = incident.severity

        for policy in policies:
            if (
                elapsed >= policy.duration_seconds
                and policy.escalate_to > target
            ):
                target = policy.escalate_to

        return self.escalate(
            incident.severity,
            target,
        )
