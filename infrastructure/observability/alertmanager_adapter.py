from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AlertManagerAlert:
    alert_id: str
    name: str
    severity: str
    status: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class AlertManagerAdapter:
    def __init__(self, url: str = "http://localhost:9093"):
        self.url = url
        self._alerts: Dict[str, AlertManagerAlert] = {}

    def fire_alert(
        self,
        alert_id: str,
        name: str,
        severity: str = "warning",
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
    ):
        alert = AlertManagerAlert(
            alert_id=alert_id,
            name=name,
            severity=severity,
            status="firing",
            labels=labels or {},
            annotations=annotations or {},
            starts_at=datetime.now().isoformat(),
        )
        self._alerts[alert_id] = alert

    def resolve_alert(self, alert_id: str):
        if alert_id in self._alerts:
            self._alerts[alert_id].status = "resolved"
            self._alerts[alert_id].ends_at = datetime.now().isoformat()

    def get_active_alerts(self) -> List[AlertManagerAlert]:
        return [a for a in self._alerts.values() if a.status == "firing"]

    def get_all_alerts(self) -> List[AlertManagerAlert]:
        return list(self._alerts.values())

    def get_alert(self, alert_id: str) -> Optional[AlertManagerAlert]:
        return self._alerts.get(alert_id)

    def get_alerts_by_severity(self, severity: str) -> List[AlertManagerAlert]:
        return [a for a in self._alerts.values() if a.severity == severity]

    def send_webhook(self, alert: AlertManagerAlert, webhook_url: str):
        return {
            "webhook_url": webhook_url,
            "alert_id": alert.alert_id,
            "status": "sent",
        }

    def clear(self):
        self._alerts.clear()
