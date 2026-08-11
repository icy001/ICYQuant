"""
Order Adapter — bridges Order domain into the integration control flow.

Commit 21 Part 1.1: translates trading context into order parameters,
and validates that the order retains the originating flow_id.

INVARIANT: Every order must retain the originating flow_id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .trading_context import TradingContext
from .control_context import TradingControlContext


@dataclass
class OrderIntent:
    """Normalized order intent produced by the integration flow."""

    # ── Identity ───────────────────────────────────────────────
    order_id: str = field(default_factory=lambda: f"ORD-{uuid.uuid4().hex[:12].upper()}")
    flow_id: str = ""  # MUST be set — every order retains originating flow_id

    # ── Instrument ─────────────────────────────────────────────
    symbol: str = ""
    exchange: str = ""

    # ── Order Parameters ───────────────────────────────────────
    side: str = ""             # BUY / SELL
    quantity: float = 0.0
    price: Optional[float] = None
    order_type: str = "LIMIT"  # LIMIT / MARKET
    time_in_force: str = "DAY"

    # ── Correlation ────────────────────────────────────────────
    decision_id: str = ""
    strategy_id: str = ""
    portfolio_id: str = ""

    # ── Governance ─────────────────────────────────────────────
    authority_id: str = ""
    approval_id: str = ""

    # ── Metadata ───────────────────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "flow_id": self.flow_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "authority_id": self.authority_id,
            "approval_id": self.approval_id,
            "metadata": self.metadata,
        }


class OrderAdapter:
    """Bridges integration flow to Order domain.

    Integration Layer → Adapter → Domain (Order)

    KEY INVARIANT: Every order MUST retain the originating flow_id.
    """

    @staticmethod
    def build_order_intent(
        trading_ctx: TradingContext,
        control_ctx: TradingControlContext,
        authority_id: str = "",
        approval_id: str = "",
    ) -> OrderIntent:
        """Build an OrderIntent from trading and control contexts."""
        return OrderIntent(
            flow_id=control_ctx.flow_id,
            symbol=trading_ctx.symbol,
            exchange=trading_ctx.exchange,
            side=trading_ctx.side,
            quantity=trading_ctx.quantity,
            price=trading_ctx.price,
            order_type=trading_ctx.order_type,
            time_in_force=trading_ctx.time_in_force,
            decision_id=control_ctx.decision_id or "",
            strategy_id=control_ctx.strategy_id or "",
            portfolio_id=control_ctx.portfolio_id or "",
            authority_id=authority_id,
            approval_id=approval_id,
        )

    @staticmethod
    def validate_order_retains_flow_id(order: Any, expected_flow_id: str) -> bool:
        """Check that an order retains the originating flow_id."""
        actual = getattr(order, "flow_id", getattr(order, "metadata", {}).get("flow_id", ""))
        return actual == expected_flow_id

    @staticmethod
    def extract_order_params(order_intent: OrderIntent) -> Dict[str, Any]:
        """Extract params suitable for creating an OMS Order."""
        return {
            "symbol": order_intent.symbol,
            "side": order_intent.side,
            "quantity": order_intent.quantity,
            "price": order_intent.price,
            "order_type": order_intent.order_type,
            "time_in_force": order_intent.time_in_force,
            "metadata": {
                "flow_id": order_intent.flow_id,
                "decision_id": order_intent.decision_id,
                "strategy_id": order_intent.strategy_id,
                "portfolio_id": order_intent.portfolio_id,
                "authority_id": order_intent.authority_id,
                "approval_id": order_intent.approval_id,
            },
        }
