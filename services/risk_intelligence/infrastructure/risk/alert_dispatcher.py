import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Alert:
    alert_id: str
    level: str
    title: str
    message: str
    timestamp: int
    acknowledged: bool = False


class AlertDispatcher:
    def __init__(self):
        self.alerts: List[Alert] = []
        self.handlers: Dict[str, List[Callable]] = {
            "WARNING": [],
            "CRITICAL": [],
            "EMERGENCY": [],
        }
        self.alert_counter = 0

    def _generate_alert_id(self) -> str:
        self.alert_counter += 1
        return f"ALT{self.alert_counter:04d}"

    def register_handler(self, level: str, handler: Callable):
        if level in self.handlers:
            self.handlers[level].append(handler)

    def dispatch_alert(
        self,
        level: str,
        title: str,
        message: str,
    ) -> Alert:
        alert = Alert(
            alert_id=self._generate_alert_id(),
            level=level,
            title=title,
            message=message,
            timestamp=int(time.time()),
        )

        self.alerts.append(alert)

        handlers = self.handlers.get(level, [])
        for handler in handlers:
            try:
                handler(alert)
            except Exception:
                pass

        return alert

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_active_alerts(self, level: str = None) -> List[Alert]:
        active = [a for a in self.alerts if not a.acknowledged]
        if level:
            active = [a for a in active if a.level == level]
        return active

    def get_alert_history(
        self, count: int = 50, level: str = None
    ) -> List[Alert]:
        alerts = self.alerts[-count:]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def clear_old_alerts(self, max_age_seconds: int = 86400):
        cutoff = int(time.time()) - max_age_seconds
        self.alerts = [a for a in self.alerts if a.timestamp >= cutoff]
