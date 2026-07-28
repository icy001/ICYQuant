from dataclasses import dataclass


@dataclass
class Alert:

    alert_id: str
    title: str
    level: str
    status: str
