"""
Commission Simulator
====================
Simulates trading commissions and fees based on configurable schedules.

Supports:
    - Fixed per-trade fee
    - Per-share fee
    - BPS-based (percentage of notional)
    - Tiered structures
    - Exchange + regulatory fees
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommissionTier:
    """A commission tier for volume-based pricing."""
    min_monthly_volume: float = 0.0
    per_share: float = 0.0
    per_trade: float = 0.0
    bps: float = 0.0


@dataclass
class CommissionSchedule:
    """Commission fee schedule."""
    name: str = "default"
    per_share: float = 0.0      # Per-share/contract fee
    per_trade: float = 0.0      # Fixed per-trade fee
    bps: float = 0.0            # Basis points of notional
    min_commission: float = 0.0
    max_commission: float = 0.0
    exchange_fee_bps: float = 0.0
    regulatory_fee_bps: float = 0.0
    tiers: List[CommissionTier] = field(default_factory=list)


@dataclass
class CommissionResult:
    """Commission calculation result."""
    total_commission: float = 0.0
    commission: float = 0.0
    exchange_fee: float = 0.0
    regulatory_fee: float = 0.0
    notional: float = 0.0
    effective_bps: float = 0.0
    schedule: str = "default"


class CommissionSimulator:
    """Simulates trading commissions for paper trading."""

    # Pre-built schedules
    SCHEDULES: Dict[str, CommissionSchedule] = {
        "default": CommissionSchedule(
            name="default", per_share=0.005, per_trade=1.0, bps=0.0,
            min_commission=1.0, max_commission=0.0,
        ),
        "zero": CommissionSchedule(name="zero"),
        "retail_us": CommissionSchedule(
            name="retail_us", per_share=0.0, per_trade=0.0, bps=0.0,
            exchange_fee_bps=0.03, regulatory_fee_bps=0.01,
        ),
        "institutional": CommissionSchedule(
            name="institutional", per_share=0.003, per_trade=0.0, bps=0.5,
            min_commission=1.0, max_commission=50.0,
            exchange_fee_bps=0.02, regulatory_fee_bps=0.005,
        ),
        "futures": CommissionSchedule(
            name="futures", per_share=0.85, per_trade=0.0, bps=0.0,
            exchange_fee_bps=0.0, regulatory_fee_bps=0.02,
        ),
    }

    def __init__(self, schedule: str = "default"):
        self._schedule_name = schedule
        self._schedule = self.SCHEDULES.get(schedule, self.SCHEDULES["default"])
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("CommissionSimulator initialized (schedule=%s)", self._schedule_name)

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    async def calculate(self, price: float, quantity: float,
                        instrument_type: str = "EQUITY") -> CommissionResult:
        """Calculate commission for a trade."""
        sched = self._schedule
        notional = abs(price * quantity)

        # Base commission
        commission = (
            sched.per_share * abs(quantity) +
            sched.per_trade +
            sched.bps / 10000.0 * notional
        )

        # Min/max caps
        if sched.min_commission > 0:
            commission = max(commission, sched.min_commission)
        if sched.max_commission > 0:
            commission = min(commission, sched.max_commission)

        # Exchange & regulatory fees
        exchange_fee = sched.exchange_fee_bps / 10000.0 * notional
        regulatory_fee = sched.regulatory_fee_bps / 10000.0 * notional

        total = commission + exchange_fee + regulatory_fee
        effective_bps = (total / notional * 10000) if notional > 0 else 0.0

        return CommissionResult(
            total_commission=total,
            commission=commission,
            exchange_fee=exchange_fee,
            regulatory_fee=regulatory_fee,
            notional=notional,
            effective_bps=effective_bps,
            schedule=self._schedule_name,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_schedule(self, name: str) -> None:
        if name in self.SCHEDULES:
            self._schedule_name = name
            self._schedule = self.SCHEDULES[name]
        else:
            logger.warning("Unknown schedule: %s, using default", name)

    def register_schedule(self, schedule: CommissionSchedule) -> None:
        self.SCHEDULES[schedule.name] = schedule

    def available_schedules(self) -> List[str]:
        return list(self.SCHEDULES.keys())

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "schedule": self._schedule_name,
            "per_share": self._schedule.per_share,
            "per_trade": self._schedule.per_trade,
            "bps": self._schedule.bps,
        }
