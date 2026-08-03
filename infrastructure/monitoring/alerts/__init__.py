"""
Alert system components.

Provides the complete alerting pipeline:
- AlertRule / AlertRuleSet for rule management
- RuleEvaluator for threshold checking
- AlertEngine for coordinated processing
- AlertRouter for notification routing
- AlertSuppression for storm prevention
- EscalationPolicy for severity escalation
- Notification channels (Log, Webhook, Email, Slack, DingTalk, WeChat, PagerDuty)

Usage:
    from infrastructure.monitoring.alerts import (
        AlertEngine,
        AlertRule,
        AlertRuleSet,
        AlertRouter,
        LogChannel,
    )

    engine = AlertEngine()
    engine.add_rule(AlertRule(
        name="high_cpu",
        metric="icyquant_cpu_usage_percent",
        operator=">",
        threshold=90.0,
    ))
    fired = await engine.process(metrics)
"""

from .engine import AlertEngine
from .escalation import EscalationPolicy
from .evaluator import RuleEvaluator
from .notification import (
    BaseChannel,
    DingTalkChannel,
    EmailChannel,
    EnterpriseWeChatChannel,
    LogChannel,
    NotificationChannel,
    PagerDutyChannel,
    SlackChannel,
    WebhookChannel,
)
from .router import AlertRouter
from .rule import AlertRule, AlertRuleSet
from .suppression import AlertSuppression

__all__ = [
    # Engine
    "AlertEngine",
    # Rule
    "AlertRule",
    "AlertRuleSet",
    # Evaluator
    "RuleEvaluator",
    # Router
    "AlertRouter",
    # Suppression
    "AlertSuppression",
    # Escalation
    "EscalationPolicy",
    # Notification Channels
    "NotificationChannel",
    "BaseChannel",
    "LogChannel",
    "WebhookChannel",
    "EmailChannel",
    "SlackChannel",
    "DingTalkChannel",
    "EnterpriseWeChatChannel",
    "PagerDutyChannel",
]
