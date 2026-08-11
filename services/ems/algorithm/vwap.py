"""VWAP Strategy — Volume-Weighted Average Price execution.

Splits the parent order based on historical volume distribution.
Follows the market volume curve to minimize market impact.

Algorithm::

    Volume Curve → Expected Volume per bucket → Proportional qty → Child Orders

Parameters:
    - duration_seconds: Total execution duration
    - volume_profile: Historical volume distribution (optional, uses default curve)

Usage::

    strategy = VWAPStrategy()
    await strategy.initialize(context)
    child = await strategy.next_child_order(metadata)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata

logger = logging.getLogger(__name__)


class VWAPStrategy(ExecutionStrategy):
    """Volume-Weighted Average Price execution strategy.

    Splits the parent order proportionally to expected market volume
    distribution. This minimizes market impact by trading more when
    the market is more liquid.

    Uses a default U-shaped intraday volume curve if no custom profile
    is provided:
        - Open: high volume (15%)
        - Mid-morning: declining (10%)
        - Midday: low volume (5%)
        - Afternoon: rising (15%)
        - Close: high volume (20%)
    """

    # Default U-shaped volume profile (10 buckets)
    DEFAULT_VOLUME_PROFILE = [
        0.15, 0.12, 0.10, 0.08, 0.06,  # Morning
        0.05, 0.05, 0.06, 0.08, 0.10,  # Midday
        0.12, 0.14, 0.16, 0.18, 0.20,  # Afternoon
        0.18, 0.15, 0.12, 0.10, 0.08,  # Late
    ]

    def __init__(self) -> None:
        super().__init__()
        self._total_slices: int = 0
        self._current_slice: int = 0
        self._slice_quantities: list[float] = []
        self._remaining_qty: float = 0.0
        self._volume_profile: list[float] = []

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize VWAP slicing with volume profile.

        Calculates per-slice quantities based on the volume profile.

        Args:
            context: Execution context
        """
        self.context = context

        # Determine number of slices
        if context.slice_count > 0:
            self._total_slices = context.slice_count
        else:
            interval = context.slice_interval_seconds
            if interval <= 0:
                interval = 60.0
            self._total_slices = max(1, int(context.effective_duration / interval))

        # Get volume profile from context or use default
        custom_profile = context.strategy_params.get("volume_profile", None)
        if custom_profile and len(custom_profile) > 0:
            self._volume_profile = self._normalize_profile(custom_profile, self._total_slices)
        else:
            self._volume_profile = self._get_default_profile(self._total_slices)

        # Calculate quantity per slice
        total_qty = context.total_quantity
        self._slice_quantities = [
            round(total_qty * pct, 2) for pct in self._volume_profile
        ]

        # Adjust for rounding errors (add remainder to last slice)
        allocated = sum(self._slice_quantities)
        diff = round(total_qty - allocated, 2)
        if diff != 0 and self._slice_quantities:
            self._slice_quantities[-1] += diff

        self._remaining_qty = total_qty
        self._current_slice = 0

        logger.info(
            "VWAP initialized: slices=%d total_qty=%.0f profile=%s",
            self._total_slices,
            total_qty,
            [f"{p:.1%}" for p in self._volume_profile[:5]] + ["..."],
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next VWAP child order based on volume profile.

        Args:
            metadata: Current execution metadata

        Returns:
            ChildOrder or None
        """
        if self._is_paused or self._is_complete:
            return None

        if self._current_slice >= self._total_slices:
            self._is_complete = True
            return None

        if self._remaining_qty <= 0:
            self._is_complete = True
            return None

        # Get planned quantity for this slice
        slice_qty = self._slice_quantities[self._current_slice]

        # Scale by remaining quantity ratio
        if metadata.target_quantity > 0:
            remaining_ratio = self._remaining_qty / metadata.target_quantity
            slice_qty = min(slice_qty, self._remaining_qty * remaining_ratio * 1.1)

        slice_qty = min(slice_qty, self._remaining_qty)
        slice_qty = max(slice_qty, self.context.min_slice_quantity)

        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)

        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            self._current_slice += 1
            return None

        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=0.0,
            slice_index=self._current_slice,
        )

        self._remaining_qty -= slice_qty
        self._current_slice += 1

        logger.debug(
            "VWAP slice %d/%d: qty=%.2f (%.1f%% of profile)",
            self._current_slice,
            self._total_slices,
            slice_qty,
            self._volume_profile[self._current_slice - 1] * 100,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update VWAP state with latest metadata.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity
        if self._remaining_qty <= 0:
            self._is_complete = True

    async def complete(self) -> None:
        """Complete the VWAP strategy."""
        self._is_complete = True
        logger.info("VWAP strategy completed: slices=%d/%d", self._current_slice, self._total_slices)

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_profile(profile: list[float], target_slices: int) -> list[float]:
        """Normalize a volume profile to sum to 1.0 and match target slices.

        Args:
            profile: Raw volume profile
            target_slices: Desired number of slices

        Returns:
            Normalized profile
        """
        if not profile:
            return VWAPStrategy.DEFAULT_VOLUME_PROFILE[:target_slices]

        # Resample to target_slices
        total = sum(profile)
        if total <= 0:
            return [1.0 / target_slices] * target_slices

        normalized = [p / total for p in profile]

        if len(normalized) == target_slices:
            return normalized

        # Simple resampling (linear interpolation)
        result = []
        for i in range(target_slices):
            src_idx = i * len(normalized) / target_slices
            idx_low = int(src_idx)
            idx_high = min(idx_low + 1, len(normalized) - 1)
            frac = src_idx - idx_low
            val = normalized[idx_low] * (1 - frac) + normalized[idx_high] * frac
            result.append(val)

        # Re-normalize
        total_result = sum(result)
        return [v / total_result for v in result]

    @staticmethod
    def _get_default_profile(slices: int) -> list[float]:
        """Get default volume profile for the given number of slices.

        Args:
            slices: Number of slices

        Returns:
            Normalized volume profile
        """
        if slices <= 0:
            return [1.0]

        default = VWAPStrategy.DEFAULT_VOLUME_PROFILE
        if slices <= len(default):
            profile = default[:slices]
        else:
            # Repeat and smooth
            profile = []
            for i in range(slices):
                idx = (i / slices) * len(default)
                idx_low = int(idx)
                idx_high = min(idx_low + 1, len(default) - 1)
                frac = idx - idx_low
                val = default[idx_low] * (1 - frac) + default[idx_high] * frac
                profile.append(val)

        # Normalize
        total = sum(profile)
        return [p / total for p in profile]
