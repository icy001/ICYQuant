"""Incident manager (Commit 27 Part 1.4, spec sections 11-17, 23-25, 30-31).

核心链路:

    Metric -> Alert -> Incident -> Impact Assessment -> Escalation
             -> Control Plane -> Recovery -> Resolution -> Post-Incident Audit

关键原则:

1. 不是 1 Alert = 1 Incident（spec section 13）：
   只有 CRITICAL / EMERGENCY（默认）才打开 Incident，
   普通 WARNING 只进 Dashboard / Operations。

2. Incident -> Control Request，而不是直接执行 Kill（spec sections 23-25）：
   Incident Engine 不拥有全局交易终止权限，
   GLOBAL_KILL 必须经过 Explicit Authorization。

3. Root Cause 不允许随意自动写入（spec section 17）：
   root_cause = None 直到人工或确定性诊断逻辑确认。

4. Alert Resolved 不等于 Incident Closed（spec section 30）：
   必须经过 Recovery Gate 全部门禁校验（spec section 31）。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from ..alerting import Alert, AlertSeverity
from .audit import IncidentAuditEvent, IncidentAuditLog
from .context import IncidentContext
from .escalation import IncidentEscalator
from .impact import ImpactCalculator, IncidentImpact
from .incident import Incident
from .models import IncidentControlRequest, RecoveryGate
from .severity import IncidentSeverity
from .state import IncidentState, transition as apply_transition

#: 用于构建 correlation_key 的标签维度 (spec section 15)。
CORRELATION_DIMENSIONS = ("venue", "service", "strategy")


def should_open_incident(
    alert_severity: AlertSeverity,
    min_severity: AlertSeverity = AlertSeverity.CRITICAL,
) -> bool:
    """spec section 13: 并非所有 Alert 都打开 Incident。

        INFO      -> Dashboard
        WARNING   -> Operations
        ERROR     -> Maybe Incident
        CRITICAL  -> Incident
        EMERGENCY -> Immediate Incident
    """

    return alert_severity >= min_severity


_ALERT_TO_INCIDENT_SEVERITY = {
    AlertSeverity.INFO: IncidentSeverity.MINOR,
    AlertSeverity.WARNING: IncidentSeverity.MODERATE,
    AlertSeverity.ERROR: IncidentSeverity.MAJOR,
    AlertSeverity.CRITICAL: IncidentSeverity.CRITICAL,
    AlertSeverity.EMERGENCY: IncidentSeverity.CATASTROPHIC,
}


def map_alert_severity(
    alert_severity: AlertSeverity,
) -> IncidentSeverity:
    """把单个 Alert 的严重级别映射为 Incident 初始严重级别。"""

    return _ALERT_TO_INCIDENT_SEVERITY[alert_severity]


def build_correlation_key(
    labels: dict[str, str],
) -> str | None:
    """spec section 15: venue/service/strategy 组合为 correlation_key。

    相同 correlation key + 相同活跃 Incident 可以合并。
    """

    parts = []

    for dimension in CORRELATION_DIMENSIONS:
        value = labels.get(dimension)
        if value:
            parts.append(f"{dimension}:{value}")

    return ",".join(parts) if parts else None


class IncidentManager:

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
    ):

        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self._incidents = {}

        self._audit_log = IncidentAuditLog()

        self._control_requests = []

        self._active_by_correlation = {}

        self._escalator = IncidentEscalator()

    # ---------------------------------------------------------
    # Creation
    # ---------------------------------------------------------

    def create(
        self,
        title,
        description,
        severity,
        impact,
        source_alert_ids=(),
        environment="production",
        correlation_key=None,
        trace_ids=(),
    ):

        now = self._clock()

        incident_id = (
            f"INC-{uuid4().hex[:12]}"
        )

        context = IncidentContext(
            incident_id=incident_id,
            created_at=now,
            detected_at=now,
            environment=environment,
            source_alert_ids=tuple(
                source_alert_ids
            ),
            trace_ids=tuple(trace_ids),
            correlation_key=correlation_key,
        )

        incident = Incident(
            context=context,
            title=title,
            description=description,
            severity=severity,
            state=IncidentState.DETECTED,
            impact=impact,
        )

        self._incidents[
            incident_id
        ] = incident

        self._record(
            incident_id=incident_id,
            event_type="INCIDENT_CREATED",
            actor="incident-engine",
            previous_state=None,
            new_state=IncidentState.DETECTED.value,
            reason="incident created",
            metadata={
                "title": title,
                "severity": severity.name,
            },
        )

        if correlation_key:
            self._active_by_correlation[
                correlation_key
            ] = incident_id

        return incident

    def get(
        self,
        incident_id,
    ):

        return self._incidents.get(
            incident_id
        )

    def all_incidents(self) -> tuple[Incident, ...]:

        return tuple(
            self._incidents.values()
        )

    # ---------------------------------------------------------
    # Alert correlation (spec sections 12-15)
    # ---------------------------------------------------------

    def find_active_by_correlation(
        self,
        correlation_key: str | None,
    ) -> Incident | None:
        """返回同一 correlation key 下仍处于活跃状态的 Incident。"""

        if not correlation_key:
            return None

        incident_id = self._active_by_correlation.get(
            correlation_key
        )

        if incident_id is None:
            return None

        incident = self._incidents.get(
            incident_id
        )

        if incident is None or incident.state in (
            IncidentState.RESOLVED,
            IncidentState.CLOSED,
        ):
            return None

        return incident

    def create_from_alert(
        self,
        alert: Alert,
        impact: IncidentImpact | None = None,
        environment="production",
    ) -> Incident:
        """Alert -> Incident (spec sections 12-15)。

        相同 correlation key 且存在活跃 Incident 时，把 Alert
        关联到已有 Incident，而不是创建新 Incident。
        """

        if not should_open_incident(
            alert.severity
        ):
            raise ValueError(
                f"alert severity {alert.severity.name} "
                f"is below incident threshold: "
                f"{AlertSeverity.CRITICAL.name}"
            )

        correlation_key = build_correlation_key(
            alert.labels
        )

        existing = self.find_active_by_correlation(
            correlation_key
        )

        if existing is not None:
            self.attach_alert(
                existing,
                alert,
            )
            return existing

        if impact is None:
            impact = ImpactCalculator().calculate(
                affected_services=(
                    (alert.service_id,)
                    if alert.service_id
                    else ()
                ),
            )

        return self.create(
            title=alert.title,
            description=alert.message,
            severity=map_alert_severity(
                alert.severity
            ),
            impact=impact,
            source_alert_ids=(alert.alert_id,),
            environment=environment,
            correlation_key=correlation_key,
        )

    def attach_alert(
        self,
        incident: Incident,
        alert: Alert,
    ) -> Incident:
        """把 Alert 关联到已有 Incident（Incident Correlation）。"""

        alert_ids = incident.context.source_alert_ids

        if alert.alert_id in alert_ids:
            return incident

        incident.context = replace(
            incident.context,
            source_alert_ids=alert_ids + (
                alert.alert_id,
            ),
        )

        self._record(
            incident_id=incident.context.incident_id,
            event_type="ALERT_ATTACHED",
            actor="incident-engine",
            previous_state=None,
            new_state=None,
            reason="alert correlated to incident",
            metadata={
                "alert_id": alert.alert_id,
                "correlation_key": (
                    incident.context.correlation_key
                    or ""
                ),
            },
        )

        return incident

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------

    def transition(
        self,
        incident,
        target_state: IncidentState,
        actor="incident-engine",
        reason="",
    ) -> IncidentState:
        """执行合法状态迁移并记录审计（spec sections 28-29）。

        非法迁移抛出 ValueError，且不产生审计事件。
        """

        previous = apply_transition(
            incident,
            target_state,
        )

        now = self._clock()

        if target_state is IncidentState.RESOLVED:
            incident.resolved_at = now

        if target_state is IncidentState.CLOSED:
            incident.closed_at = now

        self._record(
            incident_id=incident.context.incident_id,
            event_type="STATE_CHANGED",
            actor=actor,
            previous_state=previous.value,
            new_state=target_state.value,
            reason=reason,
            metadata={},
        )

        return previous

    def escalate(
        self,
        incident,
        target: IncidentSeverity,
        actor="incident-engine",
        reason="",
    ) -> IncidentSeverity:
        """Severity 只能单向升级，不能反向降级（spec section 21）。"""

        current = incident.severity

        new_severity = self._escalator.escalate(
            current,
            target,
        )

        if new_severity != current:
            incident.severity = new_severity

            self._record(
                incident_id=incident.context.incident_id,
                event_type="SEVERITY_ESCALATED",
                actor=actor,
                previous_state=current.name,
                new_state=new_severity.name,
                reason=reason,
                metadata={
                    "target": target.name,
                },
            )

        return new_severity

    def identify_root_cause(
        self,
        incident,
        root_cause: str,
        actor="incident-engine",
        reason="root cause identified",
    ):
        """Root Cause 只能由人工或确定性诊断逻辑写入（spec section 17）。"""

        incident.root_cause = root_cause

        self._record(
            incident_id=incident.context.incident_id,
            event_type="ROOT_CAUSE_IDENTIFIED",
            actor=actor,
            previous_state=None,
            new_state=None,
            reason=reason,
            metadata={
                "root_cause": root_cause,
            },
        )

    def assign(
        self,
        incident,
        assignee: str,
        actor="incident-engine",
        reason="operator assigned",
    ):
        incident.assigned_to = assignee

        self._record(
            incident_id=incident.context.incident_id,
            event_type="ASSIGNED",
            actor=actor,
            previous_state=None,
            new_state=None,
            reason=reason,
            metadata={
                "assignee": assignee,
            },
        )

    # ---------------------------------------------------------
    # Control Plane linkage (spec sections 23-25)
    # ---------------------------------------------------------

    def request_control(
        self,
        incident,
        action: str,
        reason: str,
        requested_by="incident-engine",
    ) -> IncidentControlRequest:
        """Incident -> Control Request（不直接执行任何控制动作）。"""

        request = IncidentControlRequest(
            incident_id=incident.context.incident_id,
            action=action,
            reason=reason,
            requested_by=requested_by,
        )

        self._control_requests.append(request)

        self._record(
            incident_id=incident.context.incident_id,
            event_type="CONTROL_REQUESTED",
            actor=requested_by,
            previous_state=None,
            new_state=None,
            reason=reason,
            metadata={
                "action": action,
                "requires_confirmation": (
                    str(request.requires_confirmation)
                ),
            },
        )

        return request

    def approve_control(
        self,
        request: IncidentControlRequest,
        actor="operator",
        reason="control approved",
    ):
        """Control Request 必须经过显式授权（spec section 25）。"""

        self._record(
            incident_id=request.incident_id,
            event_type="CONTROL_APPROVED",
            actor=actor,
            previous_state=None,
            new_state=None,
            reason=reason,
            metadata={
                "action": request.action,
            },
        )

    def control_requests(
        self,
        incident_id: str | None = None,
    ) -> tuple[IncidentControlRequest, ...]:

        if incident_id is None:
            return tuple(
                self._control_requests
            )

        return tuple(
            request
            for request in self._control_requests
            if request.incident_id == incident_id
        )

    # ---------------------------------------------------------
    # Recovery gate (spec sections 30-31)
    # ---------------------------------------------------------

    def validate_recovery(
        self,
        incident,
        results: dict[str, bool],
        actor="recovery-engine",
    ) -> bool:
        """Recovery Gate：任何一项检查 FAIL -> Incident != RESOLVED。

        全部通过且当前处于 MONITORING 时进入 RESOLVED；
        处于 RECOVERING 时先进入 MONITORING。
        """

        gate = RecoveryGate()

        passed = gate.evaluate(results)

        checks = gate.checks(results)

        self._record(
            incident_id=incident.context.incident_id,
            event_type="RECOVERY_VALIDATION",
            actor=actor,
            previous_state=incident.state.value,
            new_state=incident.state.value,
            reason=(
                "recovery gate passed"
                if passed
                else "recovery gate failed"
            ),
            metadata={
                check.name: str(check.passed)
                for check in checks
            },
        )

        if passed:
            if incident.state is IncidentState.RECOVERING:
                self.transition(
                    incident,
                    IncidentState.MONITORING,
                    actor=actor,
                    reason="recovery gate passed",
                )
            elif incident.state is IncidentState.MONITORING:
                self.transition(
                    incident,
                    IncidentState.RESOLVED,
                    actor=actor,
                    reason="recovery gate passed",
                )

        return passed

    # ---------------------------------------------------------
    # Audit
    # ---------------------------------------------------------

    def _record(
        self,
        incident_id,
        event_type,
        actor,
        previous_state,
        new_state,
        reason,
        metadata,
    ):

        self._audit_log.record(
            IncidentAuditEvent(
                incident_id=incident_id,
                event_type=event_type,
                timestamp=self._clock(),
                actor=actor,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
                metadata=dict(metadata),
            )
        )

    def timeline(
        self,
        incident_id: str,
    ) -> tuple[IncidentAuditEvent, ...]:
        """按时间顺序返回 Incident 的完整审计链（spec sections 27, 33）。"""

        return self._audit_log.timeline(
            incident_id
        )

    def audit_events(
        self,
        incident_id: str,
    ) -> tuple[IncidentAuditEvent, ...]:

        return self._audit_log.events_for(
            incident_id
        )
