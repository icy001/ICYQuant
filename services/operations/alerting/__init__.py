"""Production Alerting Engine (Commit 27 Part 1.3).

    Metrics -> Rule Evaluation -> Alert -> Deduplication ->
    Severity -> Escalation -> Incident

架构边界（spec section 29）：

    Alert 是"发现异常"，不是"执行交易控制"。

    Kill / Pause / Freeze / Failover / Recovery 仍由 Commit 26 的
    Control Plane 执行。Alert Engine 只负责 Detect / Classify /
    Deduplicate / Route / Correlate，绝不直接控制交易。
"""

from .alert import Alert
from .condition import ConditionEvaluator
from .dedup import (
    AlertDeduplicator,
    AlertFingerprint,
    AlertStormProtector,
)
from .evaluator import AlertRuleEvaluator
from .manager import AlertManager, FlappingDetector
from .models import AlertState
from .router import AlertRouter
from .rule import AlertRule, standard_rules
from .severity import AlertSeverity

__all__ = [
    "Alert",
    "AlertDeduplicator",
    "AlertFingerprint",
    "AlertManager",
    "AlertRule",
    "AlertRuleEvaluator",
    "AlertRouter",
    "AlertSeverity",
    "AlertState",
    "AlertStormProtector",
    "ConditionEvaluator",
    "FlappingDetector",
    "standard_rules",
]
