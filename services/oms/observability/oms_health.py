"""OMSHealth — overall OMS health monitoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List

from .order_metrics import OrderMetrics
from .execution_metrics import ExecutionMetrics
from .recovery_metrics import RecoveryMetrics
from .reconciliation_metrics import ReconciliationMetrics


class HealthStatus(Enum):
    """Overall OMS health status."""

    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()

    @property
    def label(self) -> str:
        return self.name.title()

    @property
    def is_healthy(self) -> bool:
        return self == HealthStatus.HEALTHY


@dataclass
class ComponentHealth:
    """Health of a single OMS component."""

    name: str = ""
    healthy: bool = True
    degraded: bool = False
    message: str = ""

    @property
    def status(self) -> str:
        if self.healthy and not self.degraded:
            return "HEALTHY"
        if self.degraded:
            return "DEGRADED"
        return "UNHEALTHY"


class OMSHealth:
    """Monitors the overall health of the OMS.

    Checks:
      - Event Store
      - Command Processor
      - Execution Gateway
      - Recovery Manager
      - Reconciliation Engine
      - Dead Letter Queue
      - Projection
    """

    def __init__(self) -> None:
        self._components: Dict[str, ComponentHealth] = {}
        self._init_components()
        self.order_metrics = OrderMetrics()
        self.execution_metrics = ExecutionMetrics()
        self.recovery_metrics = RecoveryMetrics()
        self.reconciliation_metrics = ReconciliationMetrics()
        self._degraded_mode: bool = False

    def _init_components(self) -> None:
        for name in [
            "event_store", "command_processor", "execution_gateway",
            "recovery_manager", "reconciliation_engine",
            "dead_letter_queue", "projection",
        ]:
            self._components[name] = ComponentHealth(
                name=name, healthy=True, degraded=False,
            )

    def set_component_healthy(self, name: str) -> None:
        if name in self._components:
            self._components[name].healthy = True
            self._components[name].degraded = False

    def set_component_degraded(self, name: str,
                               message: str = "") -> None:
        if name in self._components:
            self._components[name].healthy = True
            self._components[name].degraded = True
            self._components[name].message = message

    def set_component_unhealthy(self, name: str,
                                message: str = "") -> None:
        if name in self._components:
            self._components[name].healthy = False
            self._components[name].degraded = False
            self._components[name].message = message
            if name == "execution_gateway":
                self._degraded_mode = True

    @property
    def overall_status(self) -> HealthStatus:
        any_unhealthy = any(not c.healthy for c in self._components.values())
        any_degraded = any(c.degraded for c in self._components.values())

        if any_unhealthy:
            # Critical components being down = unhealthy
            for name in ("event_store", "command_processor"):
                if not self._components[name].healthy:
                    return HealthStatus.UNHEALTHY
            return HealthStatus.DEGRADED

        if any_degraded:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        return self.overall_status != HealthStatus.HEALTHY

    @property
    def is_degraded_mode(self) -> bool:
        """Whether the OMS is in degraded mode (blocking new orders)."""
        return self._degraded_mode

    def get_components(self) -> List[ComponentHealth]:
        return list(self._components.values())

    def to_dict(self) -> Dict:
        return {
            "overall_status": self.overall_status.label,
            "degraded_mode": self._degraded_mode,
            "components": {
                name: {
                    "status": c.status,
                    "message": c.message,
                }
                for name, c in self._components.items()
            },
            "metrics": {
                "orders": self.order_metrics.to_dict(),
                "execution": self.execution_metrics.to_dict(),
                "recovery": self.recovery_metrics.to_dict(),
                "reconciliation": self.reconciliation_metrics.to_dict(),
            },
        }
