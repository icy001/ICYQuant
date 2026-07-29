"""Order Slicer — TWAP, VWAP, POV slice generation.

Splits large orders into smaller execution slices to minimize
market impact while balancing timing risk and information leakage.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Optional

from .models import (
    ExecutionAlgorithm,
    ExecutionSlice,
    ExecutionTask,
    MarketState,
    OrderSide,
    SliceStatus,
)


class OrderSlicer:
    """Generates execution slices using TWAP, VWAP, or POV algorithms.

    Each algorithm distributes the total order quantity differently:

    - TWAP: Equal-sized slices at fixed time intervals.
    - VWAP: Slices weighted by historical volume profile.
    - POV: Slices sized as a percentage of expected market volume.
    """

    # Default historical volume profile (hourly distribution, 6.5 trading hours)
    DEFAULT_VOLUME_PROFILE: List[float] = [
        0.08, 0.06, 0.05, 0.04, 0.04,  # 9:30–10:30
        0.05, 0.06, 0.07, 0.08, 0.09,  # 10:30–11:30
        0.10, 0.09, 0.08, 0.07, 0.06,  # 11:30–12:30
        0.05, 0.05, 0.06, 0.07, 0.08,  # 12:30–13:30
        0.09, 0.10, 0.11, 0.10, 0.08,  # 13:30–14:30
        0.07, 0.06, 0.05, 0.04, 0.03,  # 14:30–15:30
        0.02,                           # 15:30–16:00
    ]

    def __init__(
        self,
        default_slices: int = 20,
        volume_profile: Optional[List[float]] = None,
    ):
        """Initialize the order slicer.

        Args:
            default_slices: Default number of slices for TWAP.
            volume_profile: Custom volume profile for VWAP (must sum to 1.0).
        """
        self.default_slices = default_slices
        self.volume_profile = volume_profile or self.DEFAULT_VOLUME_PROFILE

    def slice(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
        num_slices: Optional[int] = None,
        start_time: Optional[datetime] = None,
    ) -> List[ExecutionSlice]:
        """Generate slices based on the task's algorithm.

        Args:
            task: The execution task to slice.
            market_state: Current market state (required for VWAP/POV).
            num_slices: Override number of slices.
            start_time: Override start time.

        Returns:
            List of ExecutionSlice objects.
        """
        if task.algorithm == ExecutionAlgorithm.TWAP:
            return self._twap(task, num_slices, start_time)
        elif task.algorithm == ExecutionAlgorithm.VWAP:
            return self._vwap(task, market_state, num_slices, start_time)
        elif task.algorithm == ExecutionAlgorithm.POV:
            return self._pov(task, market_state, start_time)
        else:
            # Default to TWAP for ADAPTIVE/SMART
            return self._twap(task, num_slices, start_time)

    def _twap(
        self,
        task: ExecutionTask,
        num_slices: Optional[int] = None,
        start_time: Optional[datetime] = None,
    ) -> List[ExecutionSlice]:
        """Generate TWAP (Time-Weighted Average Price) slices.

        Equal quantities distributed evenly over the execution duration.
        """
        slices = num_slices or self.default_slices
        if slices <= 0:
            slices = 1

        start = start_time or datetime.utcnow()
        duration = task.max_duration_minutes
        interval_seconds = (duration * 60) / slices

        slice_quantity = task.quantity / slices
        slice_quantity = max(slice_quantity, task.min_slice_size)

        # Recalculate actual slices if min size constrains
        actual_slices = min(slices, int(task.quantity / task.min_slice_size))
        if actual_slices <= 0:
            actual_slices = 1

        result: List[ExecutionSlice] = []
        remaining = task.quantity

        for i in range(actual_slices):
            qty = min(slice_quantity, remaining)
            if qty <= 0:
                break

            scheduled = start + timedelta(seconds=int(i * interval_seconds))
            result.append(ExecutionSlice(
                slice_id=f"{task.order_id}_TWAP_{i:04d}",
                order_id=task.order_id,
                symbol=task.symbol,
                quantity=qty,
                side=task.side,
                scheduled_time=scheduled,
            ))
            remaining -= qty

        return result

    def _vwap(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
        num_slices: Optional[int] = None,
        start_time: Optional[datetime] = None,
    ) -> List[ExecutionSlice]:
        """Generate VWAP (Volume-Weighted Average Price) slices.

        Distributes quantity according to historical volume profile,
        executing more when the market is typically more liquid.
        """
        profile = self.volume_profile
        profile_len = len(profile)

        slices = num_slices or self.default_slices
        if slices <= 0:
            slices = 1

        # Map slices to volume profile buckets
        start = start_time or datetime.utcnow()
        duration = task.max_duration_minutes
        interval_seconds = (duration * 60) / slices

        result: List[ExecutionSlice] = []
        remaining = task.quantity

        # Collect weights for all slices first
        slice_weights: List[float] = []
        for i in range(slices):
            profile_idx = int(i * profile_len / slices)
            if profile_idx >= profile_len:
                profile_idx = profile_len - 1
            slice_weights.append(profile[profile_idx])

        # Normalize weights so they sum to 1.0
        total_weight = sum(slice_weights)
        if total_weight <= 0:
            total_weight = 1.0
        normalized_weights = [w / total_weight for w in slice_weights]

        result: List[ExecutionSlice] = []
        remaining = task.quantity

        for i in range(slices):
            qty = task.quantity * normalized_weights[i]
            qty = min(qty, remaining)
            qty = max(qty, task.min_slice_size)

            if qty <= 0 or remaining <= 0:
                break

            scheduled = start + timedelta(seconds=int(i * interval_seconds))
            result.append(ExecutionSlice(
                slice_id=f"{task.order_id}_VWAP_{i:04d}",
                order_id=task.order_id,
                symbol=task.symbol,
                quantity=qty,
                side=task.side,
                scheduled_time=scheduled,
            ))
            remaining -= qty

        # Distribute any remaining quantity to the last slice
        if remaining > 0 and result:
            result[-1].quantity += remaining

        return result

    def _pov(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
        start_time: Optional[datetime] = None,
    ) -> List[ExecutionSlice]:
        """Generate POV (Percentage Of Volume) slices.

        Each slice is sized as a percentage of expected market volume
        during that time window, maintaining a target participation rate.
        """
        participation_rate = task.max_participation_rate
        daily_vol = market_state.daily_volume if market_state else 1_000_000.0

        start = start_time or datetime.utcnow()
        duration = task.max_duration_minutes

        # Estimate per-minute market volume
        trading_minutes = 390  # 6.5 hours
        vol_per_minute = daily_vol / trading_minutes

        # Number of slices based on duration
        slices = max(1, duration)
        interval_seconds = 60  # 1 minute per POV slice

        result: List[ExecutionSlice] = []
        remaining = task.quantity

        for i in range(slices):
            # Expected market volume in this slice window
            expected_market_vol = vol_per_minute

            # Our participation: X% of market volume
            qty = expected_market_vol * participation_rate
            qty = min(qty, remaining)
            qty = max(qty, task.min_slice_size)

            if qty <= 0 or remaining <= 0:
                break

            scheduled = start + timedelta(seconds=int(i * interval_seconds))
            result.append(ExecutionSlice(
                slice_id=f"{task.order_id}_POV_{i:04d}",
                order_id=task.order_id,
                symbol=task.symbol,
                quantity=qty,
                side=task.side,
                scheduled_time=scheduled,
            ))
            remaining -= qty

        return result

    def compute_slice_statistics(self, slices: List[ExecutionSlice]) -> dict:
        """Compute statistics about a set of slices.

        Args:
            slices: List of execution slices.

        Returns:
            Dict with slice statistics.
        """
        if not slices:
            return {
                "total_slices": 0,
                "total_quantity": 0.0,
                "avg_slice_size": 0.0,
                "min_slice_size": 0.0,
                "max_slice_size": 0.0,
                "duration_minutes": 0,
            }

        quantities = [s.quantity for s in slices]
        total = sum(quantities)

        # Calculate duration
        times = [s.scheduled_time for s in slices]
        duration = 0
        if len(times) > 1:
            delta = times[-1] - times[0]
            duration = delta.total_seconds() / 60

        return {
            "total_slices": len(slices),
            "total_quantity": total,
            "avg_slice_size": total / len(slices),
            "min_slice_size": min(quantities),
            "max_slice_size": max(quantities),
            "duration_minutes": duration,
        }
