from dataclasses import dataclass


@dataclass
class Alert:
    alert_id: str
    alert_type: str
    severity: str
    message: str