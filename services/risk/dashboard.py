from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RiskDashboard:
    metrics: Dict = field(default_factory=dict)
    violations: list = field(default_factory=list)
    status: str = "OK"

    def update(self, monitor) -> None:
        self.metrics = {
            "drawdown": monitor.metrics.drawdown,
            "exposure": monitor.metrics.exposure,
            "daily_pnl": monitor.metrics.daily_pnl,
            "max_position": monitor.metrics.max_position,
            "open_orders": monitor.metrics.open_orders,
        }

        self.violations = []
        if monitor.metrics.drawdown > monitor.limits.max_drawdown:
            self.violations.append(f"Drawdown {monitor.metrics.drawdown:.2%} exceeds limit {monitor.limits.max_drawdown:.2%}")

        if monitor.metrics.exposure > monitor.limits.max_exposure:
            self.violations.append(f"Exposure {monitor.metrics.exposure:.2%} exceeds limit {monitor.limits.max_exposure:.2%}")

        self.status = "VIOLATION" if self.violations else "OK"

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "metrics": self.metrics,
            "violations": self.violations,
        }