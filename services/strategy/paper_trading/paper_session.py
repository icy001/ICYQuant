"""
Paper Session
=============
A single paper trading session representing one complete paper trading run
for a strategy, tracking orders, trades, and performance through time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SessionPhase(str, Enum):
    """Phase of a paper trading session."""
    CREATED = "created"
    INITIALIZED = "initialized"
    WARMING_UP = "warming_up"
    TRADING = "trading"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class SessionSnapshot:
    """Portfolio snapshot at a point in time."""
    timestamp: datetime
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class PaperSession:
    """A single paper trading session."""
    session_id: str = field(default_factory=lambda: f"pts_{uuid4().hex[:12]}")
    strategy_id: str = ""
    portfolio_id: str = ""
    name: str = ""
    phase: SessionPhase = SessionPhase.CREATED
    status: str = "initialized"

    # Config
    config: Dict[str, Any] = field(default_factory=dict)
    initial_capital: float = 100_000.0

    # Orders & Trades
    orders: List[Any] = field(default_factory=list)
    trades: List[Any] = field(default_factory=list)
    snapshots: List[SessionSnapshot] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # Performance
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def order_count(self) -> int:
        return len(self.orders)

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @property
    def filled_orders(self) -> List[Any]:
        from services.strategy.paper_trading.paper_trading_engine import PaperOrderStatus
        return [o for o in self.orders if getattr(o, 'status', None) == PaperOrderStatus.FILLED]

    @property
    def duration_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.ended_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def add_order(self, order: Any) -> None:
        self.orders.append(order)
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc)
        if self.phase in (SessionPhase.CREATED, SessionPhase.INITIALIZED):
            self.phase = SessionPhase.TRADING

    def add_snapshot(self, total_value: float, cash: float,
                     positions_value: float, pnl: float) -> None:
        self.snapshots.append(SessionSnapshot(
            timestamp=datetime.now(timezone.utc),
            total_value=total_value,
            cash=cash,
            positions_value=positions_value,
            pnl=pnl,
            pnl_pct=pnl / self.initial_capital * 100 if self.initial_capital else 0,
        ))

    def complete(self) -> None:
        self.phase = SessionPhase.COMPLETED
        self.status = "completed"
        self.ended_at = datetime.now(timezone.utc)

    def terminate(self, reason: str = "") -> None:
        self.phase = SessionPhase.TERMINATED
        self.status = "terminated"
        self.ended_at = datetime.now(timezone.utc)
        self.metadata["termination_reason"] = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "phase": self.phase.value,
            "status": self.status,
            "initial_capital": self.initial_capital,
            "order_count": self.order_count,
            "trade_count": self.trade_count,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_return": round(self.total_return, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 4),
            "snapshot_count": len(self.snapshots),
        }
