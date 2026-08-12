"""
HealthProfile — the per-component monitoring contract.

Every component is monitored according to its own profile:

    HealthProfile
    ├── component_id
    ├── criticality                (TRADING_CRITICAL / OPERATIONAL / NON_CRITICAL)
    ├── heartbeat_interval
    ├── warning_timeout
    ├── critical_timeout
    ├── startup_grace_period
    ├── required_dependencies
    ├── freshness_policy           (data freshness thresholds)
    └── consumer_lag thresholds    (event-bus lag thresholds)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from ..domain.component_registry import ComponentCriticality
from .readiness import FreshnessPolicy


@dataclass
class HealthProfile:
    """Configuration that drives monitoring of a single component."""

    component_id: str
    criticality: ComponentCriticality = ComponentCriticality.OPERATIONAL
    heartbeat_interval: float = 5.0
    warning_timeout: float = 10.0
    critical_timeout: float = 15.0
    startup_grace_period: float = 30.0
    required_dependencies: Tuple[str, ...] = ()
    freshness_policy: Optional[FreshnessPolicy] = None
    consumer_lag_warning: Optional[int] = None
    consumer_lag_critical: Optional[int] = None

    @property
    def is_trading_critical(self) -> bool:
        return self.criticality is ComponentCriticality.TRADING_CRITICAL

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "criticality": self.criticality.value,
            "heartbeat_interval": self.heartbeat_interval,
            "warning_timeout": self.warning_timeout,
            "critical_timeout": self.critical_timeout,
            "startup_grace_period": self.startup_grace_period,
            "required_dependencies": list(self.required_dependencies),
            "freshness_policy": (
                {
                    "fresh_seconds": self.freshness_policy.fresh_seconds,
                    "stale_seconds": self.freshness_policy.stale_seconds,
                }
                if self.freshness_policy
                else None
            ),
            "consumer_lag_warning": self.consumer_lag_warning,
            "consumer_lag_critical": self.consumer_lag_critical,
        }
