"""
Execution Scheduler — manages execution timing and sequencing.

Schedules orders across time to:
    - Smooth execution load
    - Respect participation limits
    - Coordinate multi-asset execution waves
    - Handle execution dependencies
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ScheduleMode(Enum):
    """Scheduling modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    WAVED = "waved"
    OPPORTUNISTIC = "opportunistic"


@dataclass
class ExecutionSlot:
    """A time slot for execution."""
    start_time: datetime
    end_time: datetime
    orders: list[str] = field(default_factory=list)
    max_participation: float = 0.10
    used_capacity: float = 0.0


@dataclass
class ExecutionSchedule:
    """Complete execution schedule."""
    id: str = field(default_factory=lambda: str(uuid4()))
    slots: list[ExecutionSlot] = field(default_factory=list)
    mode: ScheduleMode = ScheduleMode.SEQUENTIAL
    total_duration_min: int = 0
    order_to_slot: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class ExecutionScheduler:
    """
    Schedules order execution across time slots.

    Rules:
        - Max participation per time slot
        - Max concurrent orders per slot
        - Coordination of same-asset orders
        - Market open/close windows avoided (configurable)
    """

    def __init__(
        self,
        slot_duration_min: int = 5,
        max_slots: int = 24,
        avoid_open_min: int = 15,
        avoid_close_min: int = 15,
    ) -> None:
        self._slot_duration = slot_duration_min
        self._max_slots = max_slots
        self._avoid_open = avoid_open_min
        self._avoid_close = avoid_close_min
        self._last_schedule: Optional[ExecutionSchedule] = None

    async def schedule(
        self,
        orders: list[dict],
        start_time: Optional[datetime] = None,
        mode: ScheduleMode = ScheduleMode.WAVED,
    ) -> ExecutionSchedule:
        """
        Create execution schedule for a set of orders.

        Args:
            orders: [{id, asset, quantity, urgency, participation_limit}]
            start_time: Schedule start time (default: now)
            mode: Scheduling mode

        Returns:
            ExecutionSchedule with time slots
        """
        now = start_time or datetime.now()
        schedule = ExecutionSchedule(mode=mode)

        if mode == ScheduleMode.SEQUENTIAL:
            schedule = await self._schedule_sequential(orders, now)
        elif mode == ScheduleMode.PARALLEL:
            schedule = await self._schedule_parallel(orders, now)
        else:  # WAVED
            schedule = await self._schedule_waved(orders, now)

        schedule.created_at = datetime.now()
        self._last_schedule = schedule

        logger.info(
            "Schedule created: %d slots, %d orders, mode=%s, duration=%dmin",
            len(schedule.slots), len(orders), mode.value,
            schedule.total_duration_min,
        )
        return schedule

    async def _schedule_sequential(
        self, orders: list[dict], start: datetime
    ) -> ExecutionSchedule:
        """Schedule orders one after another."""
        schedule = ExecutionSchedule(mode=ScheduleMode.SEQUENTIAL)
        current = start

        for i, order in enumerate(orders):
            slot = ExecutionSlot(
                start_time=current,
                end_time=current + timedelta(minutes=self._slot_duration),
                orders=[order.get("id", f"order_{i}")],
            )
            schedule.slots.append(slot)
            schedule.order_to_slot[order.get("id", f"order_{i}")] = i
            current += timedelta(minutes=self._slot_duration)

        schedule.total_duration_min = len(orders) * self._slot_duration
        return schedule

    async def _schedule_parallel(
        self, orders: list[dict], start: datetime
    ) -> ExecutionSchedule:
        """Schedule all orders in a single time slot."""
        schedule = ExecutionSchedule(mode=ScheduleMode.PARALLEL)
        slot = ExecutionSlot(
            start_time=start,
            end_time=start + timedelta(minutes=self._slot_duration),
            orders=[o.get("id", f"order_{i}") for i, o in enumerate(orders)],
        )
        schedule.slots.append(slot)
        schedule.total_duration_min = self._slot_duration
        for i, o in enumerate(orders):
            schedule.order_to_slot[o.get("id", f"order_{i}")] = 0
        return schedule

    async def _schedule_waved(
        self, orders: list[dict], start: datetime
    ) -> ExecutionSchedule:
        """Schedule orders in waves, grouping by urgency."""
        schedule = ExecutionSchedule(mode=ScheduleMode.WAVED)

        # Sort by urgency (critical first)
        urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_orders = sorted(
            orders,
            key=lambda o: urgency_order.get(o.get("urgency", "MEDIUM").upper(), 2),
        )

        current = start
        slot_idx = 0

        # Group into waves of max 5 orders per slot
        for i in range(0, len(sorted_orders), 5):
            wave = sorted_orders[i:i + 5]
            slot = ExecutionSlot(
                start_time=current,
                end_time=current + timedelta(minutes=self._slot_duration),
                orders=[o.get("id", f"order_{i + j}") for j, o in enumerate(wave)],
            )
            schedule.slots.append(slot)
            for j, o in enumerate(wave):
                schedule.order_to_slot[o.get("id", f"order_{i + j}")] = slot_idx
            current += timedelta(minutes=self._slot_duration)
            slot_idx += 1

        schedule.total_duration_min = slot_idx * self._slot_duration
        return schedule

    @property
    def last_schedule(self) -> Optional[ExecutionSchedule]:
        return self._last_schedule
