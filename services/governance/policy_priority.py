"""
Policy Priority — priority levels for policy evaluation ordering.

Priority determines evaluation order (higher priority first) and resolution
behavior when policies conflict.
"""

from __future__ import annotations

from enum import IntEnum
from typing import List


class PolicyPriorityLevel(IntEnum):
    """
    Priority levels for institutional policies.

    Higher numeric values = higher priority = evaluated first.
    When policies conflict, higher priority policies take precedence.

    Levels:
        EMERGENCY (100):  Immediate action required. Overrides all other policies.
                          e.g., circuit breaker, market halt, black-swan response.

        CRITICAL (80):    Must-pass for any decision. Blocks execution on failure.
                          e.g., capital limits, regulatory compliance.

        HIGH (60):        Important institutional safeguards. Triggers review on breach.
                          e.g., concentration limits, leverage caps.

        NORMAL (40):      Standard operating policies. Warnings on breach.
                          e.g., diversification targets, liquidity preferences.

        LOW (20):         Advisory policies. Informational only.
                          e.g., best practices, style guidelines.
    """

    EMERGENCY = 100
    CRITICAL = 80
    HIGH = 60
    NORMAL = 40
    LOW = 20

    @property
    def is_blocking(self) -> bool:
        """Whether policies at this level block execution on breach."""
        return self in (PolicyPriorityLevel.EMERGENCY, PolicyPriorityLevel.CRITICAL)

    @property
    def requires_review(self) -> bool:
        """Whether policies at this level require review on breach."""
        return self == PolicyPriorityLevel.HIGH

    @property
    def is_advisory(self) -> bool:
        """Whether this level is advisory only (warnings, no blocking)."""
        return self == PolicyPriorityLevel.LOW

    @property
    def display_name(self) -> str:
        names = {
            PolicyPriorityLevel.EMERGENCY: "Emergency",
            PolicyPriorityLevel.CRITICAL: "Critical",
            PolicyPriorityLevel.HIGH: "High",
            PolicyPriorityLevel.NORMAL: "Normal",
            PolicyPriorityLevel.LOW: "Low",
        }
        return names.get(self, self.name)

    @classmethod
    def from_string(cls, value: str) -> "PolicyPriorityLevel":
        """Parse from string, case-insensitive."""
        upper = value.upper()
        for level in cls:
            if level.name == upper:
                return level
        raise ValueError(f"Unknown policy priority level: {value}")

    @classmethod
    def sorted_ascending(cls) -> List["PolicyPriorityLevel"]:
        """Return all levels sorted from lowest to highest priority."""
        return sorted(cls, key=lambda x: x.value)

    @classmethod
    def sorted_descending(cls) -> List["PolicyPriorityLevel"]:
        """Return all levels sorted from highest to lowest priority."""
        return sorted(cls, key=lambda x: x.value, reverse=True)
