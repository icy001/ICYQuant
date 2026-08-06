"""Platform Diagnostics for the Service Mesh Platform.

Provides ``PlatformDiagnostics`` for runtime diagnostics, issue
detection, and mesh platform status reporting.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformDiagnostics:
    """Runtime diagnostics for the service mesh platform."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._issues: List[Dict[str, Any]] = []
        self._max_issues = 500
        self._start_time = time.monotonic()
        self._check_count = 0

    def report_issue(
        self,
        severity: str,
        component: str,
        issue_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._issues.append({
                "severity": severity,
                "component": component,
                "issue_type": issue_type,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })
            if len(self._issues) > self._max_issues:
                self._issues = self._issues[-self._max_issues:]

        log_fn = logger.error if severity == "critical" else (
            logger.warning if severity == "warning" else logger.info
        )
        log_fn(
            "[%s] %s/%s: %s",
            severity,
            component,
            issue_type,
            message,
        )

    def check(
        self,
        components: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self._check_count += 1
            issues = list(self._issues)

        if components:
            issues = [
                i for i in issues if i["component"] in components
            ]

        critical = [i for i in issues if i["severity"] == "critical"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        return {
            "check_id": self._check_count,
            "timestamp": datetime.utcnow().isoformat(),
            "total_issues": len(issues),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "critical_issues": critical[-10:],
            "warning_issues": warnings[-10:],
            "uptime_s": time.monotonic() - self._start_time,
        }

    def get_issues(
        self,
        severity: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            issues = list(self._issues)
        if severity:
            issues = [i for i in issues if i["severity"] == severity]
        if component:
            issues = [i for i in issues if i["component"] == component]
        return issues[-limit:]

    def clear_issues(self) -> int:
        with self._lock:
            count = len(self._issues)
            self._issues.clear()
            return count

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_issues": len(self._issues),
                "check_count": self._check_count,
                "uptime_s": time.monotonic() - self._start_time,
                "by_severity": self._count_by_field("severity"),
                "by_component": self._count_by_field("component"),
            }

    def _count_by_field(self, field: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for issue in self._issues:
            val = issue.get(field, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts
