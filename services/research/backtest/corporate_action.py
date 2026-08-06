"""Corporate Action Processor — handles corporate actions in backtesting.

Automatically adjusts position quantities and prices for corporate
actions like splits, reverse splits, mergers, and spin-offs to
maintain accurate portfolio valuation.

Actions::

    Split → Reverse Split → Merger → Spin-Off
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CorporateActionType(str, Enum):
    """Types of corporate actions."""

    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    SPIN_OFF = "spin_off"
    SYMBOL_CHANGE = "symbol_change"
    DELISTING = "delisting"


@dataclass
class CorporateActionEvent:
    """A corporate action event."""

    action_id: str
    symbol: str
    action_type: CorporateActionType
    effective_date: str
    ratio: float = 1.0  # for splits: 2.0 = 2:1, for reverse: 0.5 = 1:2
    new_symbol: Optional[str] = None
    cash_component: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CorporateActionProcessor:
    """Processes corporate actions during backtesting.

    Responsibilities:
    * Adjust position quantities for splits and reverse splits
    * Handle symbol changes
    * Process merger share conversions
    * Handle spin-off share distributions
    * Mark delisted positions
    """

    def __init__(self) -> None:
        self._actions: Dict[str, List[CorporateActionEvent]] = {}
        self._processed_count = 0

    # ── registration ───────────────────────────────────────────────────────

    def register_action(self, event: CorporateActionEvent) -> None:
        """Register a corporate action event."""
        key = event.effective_date
        if key not in self._actions:
            self._actions[key] = []
        self._actions[key].append(event)
        logger.info(
            "Registered %s for %s on %s (ratio=%.2f)",
            event.action_type.value, event.symbol, event.effective_date, event.ratio,
        )

    def register_split(
        self,
        symbol: str,
        effective_date: str,
        ratio: float,
    ) -> None:
        """Register a stock split (ratio > 1) or reverse split (ratio < 1)."""
        action_type = CorporateActionType.SPLIT if ratio > 1 else CorporateActionType.REVERSE_SPLIT
        event = CorporateActionEvent(
            action_id=f"{symbol}_{effective_date}_{action_type.value}",
            symbol=symbol,
            action_type=action_type,
            effective_date=effective_date,
            ratio=ratio,
        )
        self.register_action(event)

    # ── processing ─────────────────────────────────────────────────────────

    async def process(
        self, market_event: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process corporate actions for a given market event date.

        Args:
            market_event: Market replay event with timestamp.

        Returns:
            List of processed corporate action dicts for portfolio adjustment.
        """
        timestamp = market_event.get("timestamp", "")
        date = timestamp[:10]  # YYYY-MM-DD

        actions = self._actions.get(date, [])
        processed = []
        for ca in actions:
            result = {
                "symbol": ca.symbol,
                "action_type": ca.action_type.value,
                "ratio": ca.ratio,
                "new_symbol": ca.new_symbol,
                "cash_component": ca.cash_component,
                "effective_date": ca.effective_date,
            }
            processed.append(result)
            self._processed_count += 1
            logger.info(
                "Processing %s for %s: ratio=%.2f",
                ca.action_type.value, ca.symbol, ca.ratio,
            )

        return processed

    async def adjust_portfolio(
        self,
        action_data: Dict[str, Any],
        portfolio: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Apply a corporate action to the portfolio.

        Args:
            action_data: Corporate action event data.
            portfolio: Current portfolio positions.

        Returns:
            Adjusted portfolio.
        """
        symbol = action_data.get("symbol", "")
        action_type = action_data.get("action_type", "")
        ratio = action_data.get("ratio", 1.0)
        new_symbol = action_data.get("new_symbol")

        if symbol in portfolio:
            position = portfolio[symbol]
            qty = position.get("quantity", 0)

            if action_type in (CorporateActionType.SPLIT.value, CorporateActionType.REVERSE_SPLIT.value):
                # Adjust quantity and cost basis
                new_qty = qty * ratio
                portfolio[symbol]["quantity"] = new_qty
                portfolio[symbol]["cost_basis"] = position.get("cost_basis", 0) / ratio
                logger.info("Split adjusted %s: %d → %d shares", symbol, qty, new_qty)

            elif action_type == CorporateActionType.MERGER.value and new_symbol:
                # Transfer to new symbol
                portfolio[new_symbol] = {
                    "quantity": qty * ratio,
                    "cost_basis": position.get("cost_basis", 0) / ratio,
                    "market_value": position.get("market_value", 0),
                }
                del portfolio[symbol]
                logger.info("Merger: %s → %s (ratio=%.2f)", symbol, new_symbol, ratio)

            elif action_type == CorporateActionType.SPIN_OFF.value:
                # Add new position (spin-off shares)
                spin_symbol = new_symbol or f"{symbol}_SPIN"
                portfolio[spin_symbol] = {
                    "quantity": qty * ratio,
                    "cost_basis": position.get("cost_basis", 0) * 0.2,  # allocate 20% cost
                    "market_value": 0,
                }
                logger.info("Spin-off: %s created with %.0f shares", spin_symbol, qty * ratio)

            elif action_type == CorporateActionType.DELISTING.value:
                # Mark as delisted
                portfolio[symbol]["delisted"] = True
                portfolio[symbol]["delisting_date"] = action_data.get("effective_date")
                logger.info("Delisted: %s", symbol)

        return portfolio

    # ── query ──────────────────────────────────────────────────────────────

    def get_actions_for_date(self, date: str) -> List[CorporateActionEvent]:
        """Get all corporate actions for a specific date."""
        return self._actions.get(date, [])

    def get_all_symbols(self) -> List[str]:
        """Get all symbols with registered corporate actions."""
        symbols = set()
        for events in self._actions.values():
            for evt in events:
                symbols.add(evt.symbol)
        return sorted(symbols)

    def get_stats(self) -> Dict[str, Any]:
        """Return corporate action statistics."""
        return {
            "total_dates": len(self._actions),
            "total_actions": sum(len(v) for v in self._actions.values()),
            "processed_count": self._processed_count,
            "by_type": self._count_by_type(),
            "symbols": len(self.get_all_symbols()),
        }

    def _count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for events in self._actions.values():
            for evt in events:
                t = evt.action_type.value
                counts[t] = counts.get(t, 0) + 1
        return counts
