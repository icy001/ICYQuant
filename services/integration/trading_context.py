"""
Trading Context — domain-level context for a specific trading decision.

Commit 21 Part 1.1: carries the actual trade parameters (symbol, side, quantity,
price, order type) alongside the control context for flow orchestration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TradingContext:
    """Domain context for a trading decision within the institutional flow.

    Contains the concrete trade parameters that will eventually become an order.
    Paired with TradingControlContext for the governance metadata.
    """

    # ── Instrument ─────────────────────────────────────────────
    symbol: str = ""
    asset_type: str = ""       # EQUITY / FUTURE / OPTION / FX / CRYPTO
    exchange: str = ""

    # ── Order Parameters ───────────────────────────────────────
    side: str = ""             # BUY / SELL
    quantity: float = 0.0
    price: Optional[float] = None
    order_type: str = "LIMIT"  # LIMIT / MARKET / STOP / STOP_LIMIT
    time_in_force: str = "DAY" # DAY / GTC / IOC / FOK

    # ── Notional ───────────────────────────────────────────────
    notional: float = 0.0
    leverage: float = 1.0

    # ── Risk Parameters ────────────────────────────────────────
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_bps: float = 10.0

    # ── Strategy ───────────────────────────────────────────────
    strategy_name: str = ""
    signal_score: float = 0.0
    confidence: float = 0.0

    # ── Metadata ───────────────────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type,
            "exchange": self.exchange,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "notional": self.notional,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_slippage_bps": self.max_slippage_bps,
            "strategy_name": self.strategy_name,
            "signal_score": self.signal_score,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
