"""Incident Operations Engine (Commit 27 Part 1.4).

    Metric -> Alert -> Incident -> Impact Assessment -> Escalation
             -> Control Plane -> Recovery -> Resolution -> Post-Incident Audit

这一层是生产系统真正把"技术异常"变成"运营事故"的关键：

    Metric      = 数值异常
    Alert       = 已确认需要关注的异常
    Incident    = 已经形成运营意义上的系统事故

架构边界（spec sections 17, 23-25, 31）：

1. Incident Engine 不直接执行 Kill / Pause / Failover：
   Incident -> Control Request -> Explicit Authorization -> Control Plane。

2. Root Cause 是审计信息，不允许把推测当事实自动写入：
   root_cause = None 直到人工或确定性诊断逻辑确认。

3. Recovery Gate 全部门禁通过之前，Incident != RESOLVED。
"""

from .audit import IncidentAuditEvent, IncidentAuditLog
from .context import IncidentContext
from .escalation import (
    EscalationPolicy,
    IncidentEscalator,
)
from .impact import (
    IncidentImpact,
    ImpactCalculator,
    assess_severity,
)
from .incident import Incident
from .manager import (
    IncidentManager,
    build_correlation_key,
    map_alert_severity,
    should_open_incident,
)
from .models import (
    RECOVERY_GATE_CHECKS,
    IncidentControlRequest,
    RecoveryCheck,
    RecoveryGate,
)
from .severity import IncidentSeverity
from .state import (
    VALID_TRANSITIONS,
    IncidentState,
    transition,
)

__all__ = [
    "EscalationPolicy",
    "ImpactCalculator",
    "Incident",
    "IncidentAuditEvent",
    "IncidentAuditLog",
    "IncidentContext",
    "IncidentControlRequest",
    "IncidentEscalator",
    "IncidentImpact",
    "IncidentManager",
    "IncidentSeverity",
    "IncidentState",
    "RECOVERY_GATE_CHECKS",
    "RecoveryCheck",
    "RecoveryGate",
    "VALID_TRANSITIONS",
    "assess_severity",
    "build_correlation_key",
    "map_alert_severity",
    "should_open_incident",
    "transition",
]
