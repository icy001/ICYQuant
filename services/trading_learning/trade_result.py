"""Trade Result Model – core representation of a completed trade for review."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TradeResult:
    """A single completed trade with full lifecycle information.

    Captures everything needed for post-trade analysis: entry/exit prices,
    PnL, timing, execution quality, and contextual metadata.
    """

    trade_id: str
    symbol: str = ""
    side: str = ""  # "LONG" or "SHORT"

    # Prices
    entry_price: float = 0.0
    exit_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0

    # Outcome
    pnl: float = 0.0
    pnl_pct: float = 0.0

    # Timing
    entry_time: str = ""
    exit_time: str = ""
    holding_days: int = 0

    # Execution
    quantity: int = 0
    expected_entry: float = 0.0
    actual_entry: float = 0.0
    expected_exit: float = 0.0
    actual_exit: float = 0.0
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0

    # Context
    strategy_id: str = ""
    strategy_name: str = ""
    decision_reason: str = ""
    market_regime: str = ""  # "trending", "ranging", "volatile", "calm"
    risk_score: float = 0.0
    portfolio_id: str = ""

    # Tags & metadata
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_profitable(self) -> bool:
        return self.pnl > 0

    @property
    def is_loss(self) -> bool:
        return self.pnl < 0

    @property
    def is_breakeven(self) -> bool:
        return self.pnl == 0.0

    @property
    def outcome(self) -> str:
        if self.pnl > 0:
            return "win"
        elif self.pnl < 0:
            return "loss"
        return "breakeven"

    @property
    def execution_quality_entry(self) -> str:
        """Rate entry execution quality."""
        if self.entry_slippage_bps < 1.0:
            return "excellent"
        elif self.entry_slippage_bps < 5.0:
            return "good"
        elif self.entry_slippage_bps < 15.0:
            return "fair"
        return "poor"

    @property
    def execution_quality_exit(self) -> str:
        """Rate exit execution quality."""
        if self.exit_slippage_bps < 1.0:
            return "excellent"
        elif self.exit_slippage_bps < 5.0:
            return "good"
        elif self.exit_slippage_bps < 15.0:
            return "fair"
        return "poor"

    def notional_value(self, reference_price: float) -> float:
        """Compute notional value at a given reference price."""
        return self.quantity * reference_price

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "holding_days": self.holding_days,
            "quantity": self.quantity,
            "outcome": self.outcome,
            "is_profitable": self.is_profitable,
            "strategy_name": self.strategy_name,
            "market_regime": self.market_regime,
            "entry_slippage_bps": self.entry_slippage_bps,
            "exit_slippage_bps": self.exit_slippage_bps,
            "tags": self.tags,
        }
