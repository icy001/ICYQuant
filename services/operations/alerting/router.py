"""Alert routing (Commit 27 Part 1.3, spec sections 16-17).

不同 Severity 需要不同运营路径：

    Severity       Destination
    ────────────────────────────────
    INFO           Dashboard
    WARNING        Operations
    ERROR          Operations On-Call
    CRITICAL       Incident On-Call
    EMERGENCY      Emergency On-Call

本 Part 不绑定具体第三方通知系统（Email / SMS / Webhook / Slack /
Pager / Operator Console 后续扩展）。
"""

from __future__ import annotations

from .severity import AlertSeverity


class AlertRouter:

    def route(
        self,
        severity: AlertSeverity,
    ) -> str:

        if severity == AlertSeverity.INFO:
            return "dashboard"

        if severity == AlertSeverity.WARNING:
            return "operations"

        if severity == AlertSeverity.ERROR:
            return "operations_oncall"

        if severity == AlertSeverity.CRITICAL:
            return "incident_oncall"

        if severity == AlertSeverity.EMERGENCY:
            return "emergency_oncall"

        return "operations"
