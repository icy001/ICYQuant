"""
Urgency Controller — maps alpha decay to execution urgency.

Connects the Alpha Engine to the Execution Engine:
    Fast-decaying alpha → HIGH urgency → aggressive execution
    Slow-decaying alpha → LOW urgency → patient execution

This is the key bridge: Alpha → Execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class UrgencyLevel(Enum):
    """Execution urgency levels."""
    CRITICAL = 0  # Execute immediately, minutes matter
    HIGH = 1  # Complete within 15-30 minutes
    MEDIUM = 2  # Complete within 30-60 minutes
    LOW = 3  # Patient execution, hours
    PASSIVE = 4  # Opportunistic, days


@dataclass
class UrgencyProfile:
    """Urgency profile for an alpha signal."""
    alpha_id: str = ""
    half_life_minutes: float = 60.0
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    max_time_to_complete_minutes: int = 60
    max_participation: float = 0.15
    allow_passive_execution: bool = True
    ice_berg_eligible: bool = False


class UrgencyController:
    """
    Controls execution urgency based on alpha decay.

    Mapping: Alpha Half-Life → Urgency

    < 10 min:   CRITICAL — alpha decays fast, must execute NOW
    10-30 min:  HIGH — complete quickly
    30-120 min: MEDIUM — standard execution
    2-8 hours:  LOW — patient execution
    > 8 hours:  PASSIVE — opportunistic execution
    """

    URGENCY_THRESHOLDS = [
        (10, UrgencyLevel.CRITICAL),
        (30, UrgencyLevel.HIGH),
        (120, UrgencyLevel.MEDIUM),
        (480, UrgencyLevel.LOW),
        (float("inf"), UrgencyLevel.PASSIVE),
    ]

    EXECUTION_PARAMS = {
        UrgencyLevel.CRITICAL: {"max_minutes": 10, "max_participation": 0.25},
        UrgencyLevel.HIGH: {"max_minutes": 30, "max_participation": 0.20},
        UrgencyLevel.MEDIUM: {"max_minutes": 60, "max_participation": 0.15},
        UrgencyLevel.LOW: {"max_minutes": 120, "max_participation": 0.10},
        UrgencyLevel.PASSIVE: {"max_minutes": 480, "max_participation": 0.05},
    }

    def __init__(self) -> None:
        self._profiles: dict[str, UrgencyProfile] = {}

    def compute_urgency(
        self,
        alpha_id: str,
        alpha_half_life_minutes: float,
        alpha_decay_rate: Optional[float] = None,
    ) -> UrgencyProfile:
        """Compute urgency profile from alpha decay characteristics."""
        # Determine urgency level
        urgency = UrgencyLevel.MEDIUM
        for threshold, level in self.URGENCY_THRESHOLDS:
            if alpha_half_life_minutes <= threshold:
                urgency = level
                break

        params = self.EXECUTION_PARAMS[urgency]

        profile = UrgencyProfile(
            alpha_id=alpha_id,
            half_life_minutes=alpha_half_life_minutes,
            urgency=urgency,
            max_time_to_complete_minutes=params["max_minutes"],
            max_participation=params["max_participation"],
            allow_passive_execution=urgency in (UrgencyLevel.LOW, UrgencyLevel.PASSIVE),
            ice_berg_eligible=urgency in (UrgencyLevel.LOW, UrgencyLevel.PASSIVE),
        )

        self._profiles[alpha_id] = profile

        logger.debug(
            "Urgency: alpha=%s half_life=%.0fmin → %s (max_time=%dmin, part=%.0f%%)",
            alpha_id, alpha_half_life_minutes, urgency.name,
            profile.max_time_to_complete_minutes, profile.max_participation * 100,
        )
        return profile

    def get_urgency(self, alpha_id: str) -> UrgencyProfile:
        """Get urgency profile for an alpha."""
        return self._profiles.get(
            alpha_id,
            UrgencyProfile(alpha_id=alpha_id),
        )

    def get_max_execution_time(self, alpha_id: str) -> int:
        """Get max allowable execution time in minutes."""
        profile = self.get_urgency(alpha_id)
        return profile.max_time_to_complete_minutes

    def should_expedite(self, alpha_id: str) -> bool:
        """Check if execution should be expedited."""
        profile = self.get_urgency(alpha_id)
        return profile.urgency in (UrgencyLevel.CRITICAL, UrgencyLevel.HIGH)

    def get_slice_config(self, alpha_id: str) -> dict:
        """Get slicing configuration optimized for urgency."""
        profile = self.get_urgency(alpha_id)
        configs = {
            UrgencyLevel.CRITICAL: {"slices": 3, "interval_sec": 15},
            UrgencyLevel.HIGH: {"slices": 5, "interval_sec": 60},
            UrgencyLevel.MEDIUM: {"slices": 10, "interval_sec": 180},
            UrgencyLevel.LOW: {"slices": 15, "interval_sec": 300},
            UrgencyLevel.PASSIVE: {"slices": 20, "interval_sec": 600},
        }
        return configs.get(profile.urgency, {"slices": 10, "interval_sec": 180})
