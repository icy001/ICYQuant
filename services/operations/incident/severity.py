"""Incident severity (Commit 27 Part 1.4, spec section 3).

Incident 和 Alert 都有 Severity，但两者职责不同:

    Alert Severity      描述单个异常的重要程度
    Incident Severity   描述整个事故对交易系统的影响程度

例如 3 个 WARNING Alerts 组合后可能形成 CRITICAL Incident。
"""

from enum import IntEnum


class IncidentSeverity(IntEnum):

    MINOR = 1

    MODERATE = 2

    MAJOR = 3

    CRITICAL = 4

    CATASTROPHIC = 5
