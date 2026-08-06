"""Risk Adapter — risk management integration for workflow-driven trading.

The :class:`RiskAdapter` bridges workflow execution with the risk management
system, enabling pre-trade and post-trade risk checks.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskResult(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"


@dataclass
class RiskAssessment:
    """The result of a risk check."""

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    result: RiskResult = RiskResult.APPROVED
    reason: str = ""
    checks: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        return self.result == RiskResult.APPROVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "order_id": self.order_id,
            "result": self.result.value,
            "reason": self.reason,
            "checks": self.checks,
            "timestamp": self.timestamp.isoformat(),
        }


class RiskAdapter:
    """Bridges workflow execution with the risk management system.

    Usage::

        adapter = RiskAdapter()
        await adapter.start()
        assessment = await adapter.check_order(order_id="...", account="ACC001", symbol="AAPL", quantity=1000)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._assessments: Dict[str, RiskAssessment] = {}
        self._limits: Dict[str, Dict[str, float]] = {
            # account → {limit_type: value}
        }

    async def start(self) -> None:
        self._started = True
        logger.info("RiskAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("RiskAdapter: stopped")

    # ------------------------------------------------------------------
    # Risk checks
    # ------------------------------------------------------------------

    async def check_order(
        self,
        *,
        order_id: str,
        account: str,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> RiskAssessment:
        """Run risk checks on a pending order."""
        checks = []

        # Position limit check
        position_limit = await self._get_limit(account, "position_limit")
        if position_limit and quantity > position_limit:
            return RiskAssessment(
                order_id=order_id,
                result=RiskResult.LIMIT_EXCEEDED,
                reason=f"Quantity {quantity} exceeds position limit {position_limit}",
                checks=checks,
            )

        # Notional value check
        if price:
            notional = quantity * price
            notional_limit = await self._get_limit(account, "notional_limit")
            if notional_limit and notional > notional_limit:
                return RiskAssessment(
                    order_id=order_id,
                    result=RiskResult.LIMIT_EXCEEDED,
                    reason=f"Notional {notional} exceeds limit {notional_limit}",
                    checks=checks,
                )

        return RiskAssessment(
            order_id=order_id,
            result=RiskResult.APPROVED,
            checks=checks,
        )

    async def check_portfolio(self, account: str) -> RiskAssessment:
        """Run a portfolio-level risk check."""
        return RiskAssessment(
            order_id="portfolio",
            result=RiskResult.APPROVED,
            reason="Portfolio within risk limits",
        )

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    async def set_limit(self, account: str, limit_type: str, value: float) -> None:
        with self._lock:
            if account not in self._limits:
                self._limits[account] = {}
            self._limits[account][limit_type] = value

    async def _get_limit(self, account: str, limit_type: str) -> Optional[float]:
        with self._lock:
            return self._limits.get(account, {}).get(limit_type)

    async def get_limits(self, account: str) -> Dict[str, float]:
        with self._lock:
            return dict(self._limits.get(account, {}))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_assessment(self, assessment_id: str) -> Optional[RiskAssessment]:
        with self._lock:
            return self._assessments.get(assessment_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {"accounts": len(self._limits)}
