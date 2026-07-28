from dataclasses import dataclass


@dataclass
class AlertRule:

    metric: str
    threshold: float
    operator: str
