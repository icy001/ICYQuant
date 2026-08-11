"""
Trading Transition — domain-level transition for order lifecycle stages.

Commit 21 Part 1.1: captures the trading-specific transition record
complementing the control-level transition with order details.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class TradingTransitionType(Enum):
    """Types of trading-specific transitions."""
    SIGNAL_GENERATED = auto()
    DECISION_CREATED = auto()
    ORDER_CREATED = auto()
    ORDER_SUBMITTED = auto()
    ORDER_ACKED = auto()
    ORDER_PARTIAL_FILL = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    ORDER_EXPIRED = auto()


@dataclass
class TradingTransition:
    """Domain-level transition record for trading lifecycle."""

    # ── Identity ───────────────────────────────────────────────
    transition_id: str = field(default_factory=lambda: f"TT-{uuid.uuid4().hex[:12].upper()}")

    # ── State ──────────────────────────────────────────────────
    transition_type: TradingTransitionType = TradingTransitionType.SIGNAL_GENERATED

    # ── Correlation ────────────────────────────────────────────
    flow_id: str = ""
    order_id: Optional[str] = None
    decision_id: str = ""

    # ── Data ───────────────────────────────────────────────────
    quantity: float = 0.0
    price: Optional[float] = None
    notional: float = 0.0

    # ── Meta ───────────────────────────────────────────────────
    reason: str = ""
    actor: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "transition_type": self.transition_type.name,
            "flow_id": self.flow_id,
            "order_id": self.order_id,
            "decision_id": self.decision_id,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "reason": self.reason,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
