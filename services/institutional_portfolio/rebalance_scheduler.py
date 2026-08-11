"""
Rebalance Scheduler — Intelligent Rebalance Timing

Not every drift requires immediate trading. The scheduler decides:
    NOW, LATER, SCHEDULED, or SKIP

based on: urgency, expected benefit, execution cost, alpha decay,
and market liquidity conditions.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ScheduleDecision(str, Enum):
    NOW = "NOW"
    LATER = "LATER"
    SCHEDULED = "SCHEDULED"
    SKIP = "SKIP"


class RebalanceScheduler:
    """
    Decides optimal timing for rebalancing operations.

    Factors:
    - Urgency (drift magnitude)
    - Expected benefit vs cost
    - Alpha decay time sensitivity
    - Market liquidity windows
    """

    def __init__(
        self,
        scheduler_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.scheduler_id = scheduler_id or f"rs-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._urgency_threshold = self.config.get("urgency_threshold", 0.05)
        self._benefit_threshold = self.config.get("benefit_threshold", 0.001)
        self._schedule_window = self.config.get("schedule_window_minutes", 60)

    def decide(
        self,
        drift_pct: float,
        expected_benefit: float,
        expected_cost: float,
        urgency: float = 0.0,
    ) -> ScheduleDecision:
        """
        Decide when to execute rebalance.

        Args:
            drift_pct: Percentage of total drift
            expected_benefit: Benefit from rebalancing
            expected_cost: Cost of rebalancing
            urgency: 0-1 urgency score
        """
        net_benefit = expected_benefit - expected_cost

        if urgency > self._urgency_threshold * 2:
            return ScheduleDecision.NOW

        if net_benefit > self._benefit_threshold * 10 and drift_pct > self._urgency_threshold:
            return ScheduleDecision.NOW

        if net_benefit > self._benefit_threshold and drift_pct > self._urgency_threshold * 0.5:
            return ScheduleDecision.SCHEDULED

        if net_benefit > 0:
            return ScheduleDecision.LATER

        return ScheduleDecision.SKIP

    def schedule_time(self) -> datetime:
        """Return the scheduled rebalance time."""
        return datetime.utcnow() + timedelta(minutes=self._schedule_window)
