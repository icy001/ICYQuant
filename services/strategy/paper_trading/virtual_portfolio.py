"""
Virtual Portfolio
=================
Tracks simulated portfolio holdings, positions, and P&L during paper trading.

Maintains a real-time view of the virtual portfolio state as trades are executed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class VirtualPosition:
    """A single virtual position in the portfolio."""
    instrument: str = ""
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VirtualBalance:
    """Virtual account balances."""
    cash: float = 0.0
    initial_capital: float = 0.0
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    total_commission: float = 0.0


class VirtualPortfolio:
    """Tracks simulated portfolio holdings during paper trading."""

    def __init__(self):
        self._positions: Dict[str, VirtualPosition] = {}
        self._balance = VirtualBalance()
        self._trade_history: List[Dict[str, Any]] = []
        self._snapshots: List[Dict[str, Any]] = []
        self.is_initialized = False

    async def initialize(self, initial_capital: float = 100_000.0) -> None:
        """Initialize portfolio with starting capital."""
        self._balance = VirtualBalance(
            cash=initial_capital,
            initial_capital=initial_capital,
            total_deposits=initial_capital,
        )
        self.is_initialized = True
        logger.info("VirtualPortfolio initialized with capital=%s", initial_capital)

    # ------------------------------------------------------------------
    # Trade Application
    # ------------------------------------------------------------------

    async def apply_trade(self, trade: Any) -> VirtualPosition:
        """Apply a paper trade to the portfolio."""
        instrument = getattr(trade, 'instrument', '')
        side = getattr(trade, 'side', 'BUY')
        quantity = getattr(trade, 'quantity', 0.0)
        price = getattr(trade, 'price', 0.0)
        commission = getattr(trade, 'commission', 0.0)

        if instrument not in self._positions:
            self._positions[instrument] = VirtualPosition(instrument=instrument)

        pos = self._positions[instrument]
        cost = quantity * price

        if side == "BUY":
            new_qty = pos.quantity + quantity
            pos.avg_cost = (
                ((pos.avg_cost * pos.quantity) + cost) / new_qty
                if new_qty > 0 else price
            )
            pos.quantity = new_qty
            self._balance.cash -= (cost + commission)
        elif side == "SELL":
            realized_pnl = (price - pos.avg_cost) * quantity
            pos.realized_pnl += realized_pnl
            pos.quantity -= quantity
            self._balance.cash += (cost - commission)

            if pos.quantity <= 0:
                pos.quantity = 0.0
                pos.avg_cost = 0.0

        self._balance.total_commission += commission
        pos.current_price = price
        pos.market_value = pos.quantity * price
        pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity if pos.quantity > 0 else 0.0
        pos.unrealized_pnl_pct = (
            (price / pos.avg_cost - 1) * 100 if pos.avg_cost > 0 and pos.quantity > 0 else 0.0
        )
        pos.updated_at = datetime.now(timezone.utc)

        self._trade_history.append({
            "instrument": instrument, "side": side, "quantity": quantity,
            "price": price, "commission": commission,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.debug("Trade applied: %s %s %s @ %s", side, quantity, instrument, price)
        return pos

    # ------------------------------------------------------------------
    # Valuation
    # ------------------------------------------------------------------

    async def update_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices for all positions."""
        for instrument, price in prices.items():
            if instrument in self._positions:
                pos = self._positions[instrument]
                pos.current_price = price
                pos.market_value = pos.quantity * price
                pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity if pos.quantity > 0 else 0.0
                pos.unrealized_pnl_pct = (
                    (price / pos.avg_cost - 1) * 100 if pos.avg_cost > 0 and pos.quantity > 0 else 0.0
                )
                pos.updated_at = datetime.now(timezone.utc)

    def total_value(self) -> float:
        """Total portfolio value (cash + positions)."""
        positions_value = sum(p.market_value for p in self._positions.values())
        return self._balance.cash + positions_value

    def total_pnl(self) -> float:
        """Total P&L since inception."""
        return self.total_value() - self._balance.initial_capital

    def total_pnl_pct(self) -> float:
        """Total P&L percentage."""
        if self._balance.initial_capital <= 0:
            return 0.0
        return (self.total_pnl() / self._balance.initial_capital) * 100

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    async def take_snapshot(self) -> Dict[str, Any]:
        """Take a portfolio snapshot."""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_value": self.total_value(),
            "cash": self._balance.cash,
            "positions_value": sum(p.market_value for p in self._positions.values()),
            "total_pnl": self.total_pnl(),
            "total_pnl_pct": self.total_pnl_pct(),
            "position_count": len(self._positions),
        }
        self._snapshots.append(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_position(self, instrument: str) -> Optional[VirtualPosition]:
        return self._positions.get(instrument)

    def all_positions(self) -> List[VirtualPosition]:
        return [p for p in self._positions.values() if p.quantity != 0]

    def position_count(self) -> int:
        return len(self.all_positions())

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_value": round(self.total_value(), 2),
            "cash": round(self._balance.cash, 2),
            "total_pnl": round(self.total_pnl(), 2),
            "total_pnl_pct": round(self.total_pnl_pct(), 4),
            "position_count": self.position_count(),
            "total_commission": round(self._balance.total_commission, 2),
            "trade_count": len(self._trade_history),
            "snapshot_count": len(self._snapshots),
        }
