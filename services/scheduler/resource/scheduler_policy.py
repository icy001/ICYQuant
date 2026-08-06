"""Scheduler Policy — pluggable scheduling policy framework.

The :class:`SchedulerPolicy` defines the strategy for ordering and
selecting jobs from the queue.  Policies can be composed and hot-swapped
at runtime.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class PolicyType(str, enum.Enum):
    FIFO = "fifo"
    PRIORITY = "priority"
    FAIR_SHARE = "fair_share"
    DEADLINE = "deadline"
    CUSTOM = "custom"


@dataclass
class SchedulerPolicy:
    """Pluggable scheduling policy configuration.

    Usage::

        policy = SchedulerPolicy(
            policy_type=PolicyType.PRIORITY,
            preemption_enabled=True,
            fair_share_weight=1.0,
        )
    """

    policy_type: PolicyType = PolicyType.PRIORITY
    preemption_enabled: bool = False
    fair_share_weight: float = 1.0
    max_starvation_seconds: float = 300.0  # max time a low-priority job waits
    tenant_weights: Dict[str, float] = field(default_factory=dict)
    custom_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_type": self.policy_type.value,
            "preemption_enabled": self.preemption_enabled,
            "fair_share_weight": self.fair_share_weight,
            "max_starvation_seconds": self.max_starvation_seconds,
            "tenant_weights": self.tenant_weights,
        }

    @classmethod
    def default(cls) -> "SchedulerPolicy":
        return cls(policy_type=PolicyType.PRIORITY)

    @classmethod
    def fair(cls, weights: Optional[Dict[str, float]] = None) -> "SchedulerPolicy":
        return cls(
            policy_type=PolicyType.FAIR_SHARE,
            tenant_weights=weights or {},
        )

    def health_report(self) -> Dict[str, Any]:
        return self.to_dict()
