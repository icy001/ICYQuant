"""
Alpha Decay — Half-life based alpha decay tracking.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Tracks:
    Alpha → Half Life → Decay → Deactivate

Automatically phases out decaying alphas.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaStatus
from services.strategy.signal.alpha_registry import AlphaRegistry

logger = logging.getLogger(__name__)


class AlphaDecay:
    """Manages alpha decay based on half-life models.

    Each alpha has a half-life (in days). The decay factor is computed as:
        decay = 2^(-t / half_life)

    When decay drops below a threshold, the alpha is deactivated.
    """

    DECAY_THRESHOLD = 0.01  # Deactivate when decay < 1%
    DEFAULT_HALF_LIFE_DAYS = 30.0

    def __init__(self, registry: AlphaRegistry):
        self.registry = registry
        self._decay_start: Dict[str, datetime] = {}  # alpha_id → start of decay tracking

    # ------------------------------------------------------------------
    # Decay Computation
    # ------------------------------------------------------------------

    async def get_decay_factor(self, alpha_id: str) -> float:
        """Get the current decay factor for an alpha.

        Returns 1.0 if alpha is fully active, 0.0 if fully decayed.
        """
        alpha_info = self.registry.get_alpha(alpha_id)
        if not alpha_info:
            return 0.0

        if alpha_info.status != AlphaStatus.DECAYING:
            return 1.0 if alpha_info.status == AlphaStatus.ACTIVE else 0.0

        # Compute decay based on elapsed time
        start = self._decay_start.get(alpha_id)
        if not start:
            self._decay_start[alpha_id] = datetime.now(timezone.utc)
            return 1.0

        elapsed_days = (datetime.now(timezone.utc) - start).total_seconds() / 86400.0
        half_life = alpha_info.half_life_days or self.DEFAULT_HALF_LIFE_DAYS

        decay = 2.0 ** (-elapsed_days / half_life)
        return max(0.0, decay)

    async def update_decay(self) -> List[str]:
        """Update decay for all decaying alphas. Returns list of newly deactivated IDs."""
        deactivated = []

        for alpha_info in self.registry.list_all():
            if alpha_info.status != AlphaStatus.DECAYING:
                continue

            decay = await self.get_decay_factor(alpha_info.alpha_id)
            if decay < self.DECAY_THRESHOLD:
                self.registry.set_status(alpha_info.alpha_id, AlphaStatus.INACTIVE)
                deactivated.append(alpha_info.alpha_id)
                logger.info("Alpha %s fully decayed → INACTIVE", alpha_info.alpha_id)

        return deactivated

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    async def start_decay(self, alpha_id: str) -> bool:
        """Mark an alpha as decaying and start the decay clock."""
        alpha_info = self.registry.get_alpha(alpha_id)
        if not alpha_info:
            return False

        alpha_info.status = AlphaStatus.DECAYING
        self._decay_start[alpha_id] = datetime.now(timezone.utc)
        logger.info("Alpha %s decay started (half_life=%.1f days)", alpha_id, alpha_info.half_life_days)
        return True

    async def reset_decay(self, alpha_id: str) -> bool:
        """Reset decay for an alpha, restoring it to active."""
        alpha_info = self.registry.get_alpha(alpha_id)
        if not alpha_info:
            return False

        alpha_info.status = AlphaStatus.ACTIVE
        self._decay_start.pop(alpha_id, None)
        logger.info("Alpha %s decay reset → ACTIVE", alpha_id)
        return True

    async def get_remaining_life(self, alpha_id: str) -> Optional[float]:
        """Estimate remaining days before full decay."""
        alpha_info = self.registry.get_alpha(alpha_id)
        if not alpha_info or alpha_info.status != AlphaStatus.DECAYING:
            return None

        decay = await self.get_decay_factor(alpha_id)
        if decay <= 0:
            return 0.0

        half_life = alpha_info.half_life_days or self.DEFAULT_HALF_LIFE_DAYS
        # days_remaining = half_life * log2(decay / threshold)
        days_remaining = half_life * math.log2(decay / self.DECAY_THRESHOLD)
        return max(0.0, days_remaining)
