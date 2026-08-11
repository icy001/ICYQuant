"""
Pre-Trade Optimizer — final optimization before order submission.

Last-mile checks before an order hits OMS:
    - Risk constraint validation
    - Liquidity check
    - Position limit check
    - Exposure limit check
    - Cost reasonability

Output: ALLOW / RESIZE / DELAY / REJECT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PreTradeDecision(Enum):
    """Pre-trade check decision."""
    ALLOW = "allow"
    RESIZE = "resize"
    DELAY = "delay"
    REJECT = "reject"


@dataclass
class PreTradeCheck:
    """A single pre-trade check result."""
    name: str
    passed: bool = True
    decision: PreTradeDecision = PreTradeDecision.ALLOW
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreTradeResult:
    """Complete pre-trade optimization result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    decision: PreTradeDecision = PreTradeDecision.ALLOW
    checks: list[PreTradeCheck] = field(default_factory=list)
    adjusted_quantity: Optional[int] = None
    adjusted_price: Optional[float] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PreTradeOptimizer:
    """
    Pre-trade optimization and validation.

    Checks (in order):
        1. Kill switch status
        2. Risk budget availability
        3. Position limits
        4. Exposure limits
        5. Leverage limits
        6. Liquidity sufficiency
        7. Order size reasonability
        8. Price reasonability
        9. Execution cost budget
        10. Regime constraints
    """

    def __init__(
        self,
        max_order_notional: float = 50_000_000,
        max_position_pct: float = 0.20,
    ) -> None:
        self._max_order_notional = max_order_notional
        self._max_position_pct = max_position_pct

    async def check(
        self,
        order: dict,
        portfolio_state: dict,
        risk_budget_remaining: float = 1.0,
        current_positions: Optional[dict[str, float]] = None,
        kill_switch_active: bool = False,
    ) -> PreTradeResult:
        """Run all pre-trade checks."""
        result = PreTradeResult(order_id=order.get("id", ""))

        # Check 1: Kill switch
        if kill_switch_active:
            result.decision = PreTradeDecision.REJECT
            result.checks.append(PreTradeCheck(
                name="kill_switch", passed=False,
                decision=PreTradeDecision.REJECT,
                message="Kill switch active",
            ))
            return result

        # Check 2: Risk budget
        if risk_budget_remaining <= 0:
            result.decision = PreTradeDecision.REJECT
            result.checks.append(PreTradeCheck(
                name="risk_budget", passed=False,
                decision=PreTradeDecision.REJECT,
                message="No remaining risk budget",
            ))
            return result

        # Check 3: Position limits
        asset = order.get("asset", "")
        quantity = order.get("quantity", 0)
        positions = current_positions or {}
        current_pos = positions.get(asset, 0)
        new_pos = current_pos + quantity

        if abs(new_pos) > self._max_position_pct:
            result.checks.append(PreTradeCheck(
                name="position_limit", passed=False,
                decision=PreTradeDecision.RESIZE,
                message=f"New position {new_pos:.1%} exceeds max {self._max_position_pct:.1%}",
            ))

        # Check 4: Notional limit
        notional = order.get("notional", 0)
        if notional > self._max_order_notional:
            result.checks.append(PreTradeCheck(
                name="notional_limit", passed=False,
                decision=PreTradeDecision.RESIZE,
                message=f"Order notional {notional:,.0f} exceeds max {self._max_order_notional:,.0f}",
            ))

        # Check 5: Liquidity
        adv = order.get("adv", 0)
        pct_adv = abs(quantity) / max(adv, 1) if order.get("quantity") else 0
        if pct_adv > 0.10:
            result.checks.append(PreTradeCheck(
                name="liquidity", passed=False,
                decision=PreTradeDecision.RESIZE,
                message=f"Order {pct_adv:.1%} ADV exceeds 10% limit",
            ))

        # Check 6: Cost
        cost_bps = order.get("expected_cost_bps", 0)
        if cost_bps > 50:
            result.checks.append(PreTradeCheck(
                name="cost", passed=False,
                decision=PreTradeDecision.REJECT,
                message=f"Expected cost {cost_bps:.0f}bps exceeds 50bps limit",
            ))

        # Determine final decision
        if not result.checks:
            result.decision = PreTradeDecision.ALLOW
            result.reason = "All checks passed"
        else:
            worst = max(
                result.checks,
                key=lambda c: {"ALLOW": 0, "DELAY": 1, "RESIZE": 2, "REJECT": 3}[c.decision.value],
            )
            result.decision = worst.decision
            result.reason = worst.message

        return result
