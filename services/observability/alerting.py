from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from datetime import datetime


class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class AlertStatus(Enum):
    TRIGGERED = "TRIGGERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class NotificationChannel(Enum):
    EMAIL = "EMAIL"
    WECHAT_WORK = "WECHAT_WORK"
    SLACK = "SLACK"
    PAGERDUTY = "PAGERDUTY"
    WEBHOOK = "WEBHOOK"


@dataclass
class AlertRule:
    rule_id: str
    name: str
    metric_name: str
    condition: str
    threshold: float
    severity: str
    duration_seconds: int = 0
    cooldown_seconds: int = 300
    enabled: bool = True


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str
    status: str
    message: str
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class NotificationConfig:
    channel: str
    target: str
    enabled: bool = True


class AlertEvaluator:
    def evaluate(self, metric_value: float, rule: AlertRule) -> bool:
        if rule.condition == "GT":
            return metric_value > rule.threshold
        elif rule.condition == "LT":
            return metric_value < rule.threshold
        elif rule.condition == "GTE":
            return metric_value >= rule.threshold
        elif rule.condition == "LTE":
            return metric_value <= rule.threshold
        return False


class AlertEngine:
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._history: List[Alert] = []
        self._evaluator = AlertEvaluator()
        self._notification_callbacks: Dict[str, List[Callable]] = {
            channel.value: [] for channel in NotificationChannel
        }

    def add_rule(self, rule: AlertRule):
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str):
        self._rules.pop(rule_id, None)

    def list_rules(self) -> List[AlertRule]:
        return list(self._rules.values())

    def evaluate_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> List[Alert]:
        triggered = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.metric_name != metric_name:
                continue
            if self._evaluator.evaluate(value, rule):
                alert = self._create_alert(rule, value, tags)
                triggered.append(alert)
        return triggered

    def _create_alert(self, rule: AlertRule, current_value: float, tags: Optional[Dict[str, str]]) -> Alert:
        import uuid
        alert = Alert(
            alert_id=uuid.uuid4().hex[:12],
            rule_id=rule.rule_id,
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=current_value,
            threshold=rule.threshold,
            severity=rule.severity,
            status=AlertStatus.TRIGGERED.value,
            message=f"{rule.name}: {rule.metric_name} = {current_value:.2f} (threshold: {rule.threshold})",
            timestamp=datetime.now(),
            tags=tags or {},
        )
        self._alerts[alert.alert_id] = alert
        self._history.append(alert)
        return alert

    def acknowledge_alert(self, alert_id: str):
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED.value
            alert.acknowledged_at = datetime.now()

    def resolve_alert(self, alert_id: str):
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.RESOLVED.value
            alert.resolved_at = datetime.now()

    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        alerts = [a for a in self._alerts.values() if a.status == AlertStatus.TRIGGERED.value]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_history(self, limit: int = 50) -> List[Alert]:
        return sorted(self._history, key=lambda a: a.timestamp, reverse=True)[:limit]

    def clear(self):
        self._alerts.clear()
        self._history.clear()


class NotificationDispatcher:
    def __init__(self):
        self._configs: Dict[str, List[NotificationConfig]] = {
            channel.value: [] for channel in NotificationChannel
        }
        self._sent: List[Dict] = []

    def configure_channel(self, channel: str, config: NotificationConfig):
        if channel not in self._configs:
            self._configs[channel] = []
        self._configs[channel].append(config)

    def send(self, alert: Alert, channels: Optional[List[str]] = None):
        target_channels = channels or list(self._configs.keys())
        for channel in target_channels:
            if channel in self._configs:
                for config in self._configs[channel]:
                    if config.enabled:
                        self._sent.append({
                            "alert_id": alert.alert_id,
                            "channel": channel,
                            "target": config.target,
                            "timestamp": datetime.now(),
                            "severity": alert.severity,
                        })

    def get_sent_notifications(self, limit: int = 20) -> List[Dict]:
        return sorted(self._sent, key=lambda n: n["timestamp"], reverse=True)[:limit]
