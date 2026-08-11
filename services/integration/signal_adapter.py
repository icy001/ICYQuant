"""
Signal Adapter — bridges Strategy signals into the integration control flow.

Commit 21 Part 1.1: translates raw strategy signals into a normalized
format the integration layer can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_context import TradingControlContext


@dataclass
class SignalInput:
    """Raw signal from a strategy."""
    signal_id: str
    strategy_id: str
    portfolio_id: str = ""
    symbol: str = ""
    side: str = ""            # BUY / SELL
    quantity: float = 0.0
    price: Optional[float] = None
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SignalAdapter:
    """Bridges strategy signals into the integration layer.

    Domain → Adapter → Integration Layer
    """

    def adapt(self, signal: SignalInput) -> TradingControlContext:
        """Create a control context from a strategy signal."""
        ctx = TradingControlContext(
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            portfolio_id=signal.portfolio_id,
            actor="STRATEGY",
            decision_type="ORDER_SUBMIT",
            reason=signal.reason,
            metadata={
                "symbol": signal.symbol,
                "side": signal.side,
                "quantity": signal.quantity,
                "price": signal.price,
                "score": signal.score,
                "confidence": signal.confidence,
                **signal.metadata,
            },
        )
        return ctx

    def extract_decision_params(self, signal: SignalInput) -> Dict[str, Any]:
        """Extract parameters for a DecisionRequest."""
        return {
            "actor": "STRATEGY",
            "decision_type": "ORDER_SUBMIT",
            "strategy_id": signal.strategy_id,
            "portfolio_id": signal.portfolio_id,
            "asset_id": signal.symbol,
            "requested_amount": signal.quantity * (signal.price or 0),
            "requested_quantity": signal.quantity,
            "direction": "INCREASE" if signal.side.upper() == "BUY" else "DECREASE",
            "reason": signal.reason,
            "metadata": {"score": signal.score, "confidence": signal.confidence},
        }
