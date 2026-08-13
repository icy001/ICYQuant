"""Alert severity (Commit 27 Part 1.3, spec sections 3-4).

不同异常不能全部标 CRITICAL：

    Execution latency = 80ms          -> WARNING
    Position != Ledger                -> CRITICAL
    Global Risk Limit breached        -> EMERGENCY

Severity 决定运营路径（Router）与升级（Escalation）策略。
"""

from enum import IntEnum


class AlertSeverity(IntEnum):

    INFO = 1

    WARNING = 2

    ERROR = 3

    CRITICAL = 4

    EMERGENCY = 5
