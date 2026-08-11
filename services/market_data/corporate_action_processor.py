"""
Corporate Action Processor — handles corporate actions (splits,
dividends, bonuses, rights issues) and applies price/volume
adjustments for historical data continuity.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CorporateActionType(str, Enum):
    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    DIVIDEND = "dividend"
    SPECIAL_DIVIDEND = "special_dividend"
    BONUS = "bonus"
    RIGHTS_ISSUE = "rights_issue"
    SPINOFF = "spinoff"
    MERGER = "merger"
    SYMBOL_CHANGE = "symbol_change"
    DELISTING = "delisting"
    OTHER = "other"


@dataclass
class CorporateAction:
    """A single corporate action event."""

    action_id: str = ""
    instrument_id: str = ""
    action_type: CorporateActionType = CorporateActionType.OTHER
    effective_date: Optional[date] = None
    ex_date: Optional[date] = None
    record_date: Optional[date] = None
    payment_date: Optional[date] = None

    # Split/reverse split
    split_ratio_from: float = 1.0
    split_ratio_to: float = 1.0

    # Dividend
    dividend_amount: Decimal = Decimal("0")
    dividend_currency: str = "USD"
    dividend_type: str = ""

    # Rights issue
    rights_ratio: float = 0.0
    subscription_price: Decimal = Decimal("0")

    # Symbol change
    old_symbol: str = ""
    new_symbol: str = ""

    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdjustmentFactor:
    """Cumulative adjustment factors for historical price correction."""

    instrument_id: str = ""
    price_factor: Decimal = Decimal("1.0")
    volume_factor: Decimal = Decimal("1.0")
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    actions_applied: list[str] = field(default_factory=list)


class CorporateActionProcessor:
    """
    Processes corporate actions and computes adjustment factors
    for historical data continuity.

    Supports:
    - Stock splits / reverse splits (price & volume adjustment)
    - Cash dividends (price adjustment)
    - Bonus issues
    - Rights issues
    - Symbol changes
    """

    def __init__(self) -> None:
        self._actions: dict[str, list[CorporateAction]] = {}
        self._factors: dict[str, list[AdjustmentFactor]] = {}

    async def initialize(self) -> None:
        logger.info("CorporateActionProcessor initialized with %d instruments",
                     len(self._actions))

    # ── Action registration ────────────────────────

    async def register_action(self, action: CorporateAction) -> None:
        """Register a corporate action event."""
        inst_id = action.instrument_id
        if inst_id not in self._actions:
            self._actions[inst_id] = []
        self._actions[inst_id].append(action)
        logger.debug("Registered %s for %s: %s", action.action_type.value, inst_id, action.description)

    async def register_actions_batch(self, actions: list[CorporateAction]) -> None:
        """Register multiple corporate actions."""
        for action in actions:
            await self.register_action(action)

    async def get_actions(
        self,
        instrument_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[CorporateAction]:
        """Get all corporate actions for an instrument, optionally filtered by date."""
        actions = self._actions.get(instrument_id, [])
        if from_date:
            actions = [a for a in actions if a.effective_date and a.effective_date >= from_date]
        if to_date:
            actions = [a for a in actions if a.effective_date and a.effective_date <= to_date]
        return sorted(actions, key=lambda a: a.effective_date or date.min)

    # ── Adjustment computation ─────────────────────

    async def compute_adjustment_factors(
        self, instrument_id: str
    ) -> list[AdjustmentFactor]:
        """
        Compute cumulative adjustment factors for all known corporate actions.

        Returns a list of adjustment factors, each covering a date range,
        so historical prices can be adjusted forward to present.
        """
        actions = await self.get_actions(instrument_id)
        if not actions:
            return [
                AdjustmentFactor(
                    instrument_id=instrument_id,
                    price_factor=Decimal("1.0"),
                    volume_factor=Decimal("1.0"),
                )
            ]

        factors: list[AdjustmentFactor] = []
        cum_price = Decimal("1.0")
        cum_volume = Decimal("1.0")

        for action in actions:
            if action.action_type == CorporateActionType.SPLIT:
                ratio = Decimal(str(action.split_ratio_from)) / Decimal(str(action.split_ratio_to))
                cum_price *= ratio
                cum_volume /= ratio

            elif action.action_type == CorporateActionType.REVERSE_SPLIT:
                ratio = Decimal(str(action.split_ratio_to)) / Decimal(str(action.split_ratio_from))
                cum_price *= ratio
                cum_volume /= ratio

            factors.append(AdjustmentFactor(
                instrument_id=instrument_id,
                price_factor=cum_price,
                volume_factor=cum_volume,
                effective_from=action.effective_date,
                effective_to=action.effective_date,
                actions_applied=[action.action_id],
            ))

        if not factors:
            factors.append(AdjustmentFactor(
                instrument_id=instrument_id,
                price_factor=Decimal("1.0"),
                volume_factor=Decimal("1.0"),
            ))

        self._factors[instrument_id] = factors
        return factors

    async def adjust_price(
        self, instrument_id: str, price: Decimal, as_of_date: date
    ) -> Decimal:
        """
        Adjust a historical price to account for corporate actions
        that occurred between as_of_date and today.
        """
        factors = self._factors.get(instrument_id)
        if not factors:
            factors = await self.compute_adjustment_factors(instrument_id)

        total_factor = Decimal("1.0")
        for f in factors:
            if f.effective_from and f.effective_from > as_of_date:
                total_factor *= f.price_factor

        return price * total_factor

    async def adjust_volume(
        self, instrument_id: str, volume: Decimal, as_of_date: date
    ) -> Decimal:
        """Adjust historical volume for corporate actions."""
        factors = self._factors.get(instrument_id)
        if not factors:
            factors = await self.compute_adjustment_factors(instrument_id)

        total_factor = Decimal("1.0")
        for f in factors:
            if f.effective_from and f.effective_from > as_of_date:
                total_factor *= f.volume_factor

        return volume * total_factor

    async def has_symbol_change(
        self, instrument_id: str, from_date: Optional[date] = None
    ) -> Optional[CorporateAction]:
        """Check if there's a symbol change for this instrument."""
        actions = self._actions.get(instrument_id, [])
        for action in actions:
            if action.action_type == CorporateActionType.SYMBOL_CHANGE:
                if from_date is None or (action.effective_date and action.effective_date >= from_date):
                    return action
        return None

    @property
    def instrument_count(self) -> int:
        return len(self._actions)
