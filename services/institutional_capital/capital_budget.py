"""
Capital Budget — Multi-Period Capital Planning

Capital is not unlimited. The CapitalBudget plans how much capital
each strategy/account can consume over a planning horizon, enforcing
budgetary discipline:

    period_budget = total_capital × allocation_pct
    consumed ≤ budget
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BudgetPeriod(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class BudgetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXCEEDED = "EXCEEDED"
    WARNING = "WARNING"
    CLOSED = "CLOSED"


@dataclass
class BudgetLine:
    budget_id: str
    category: str
    total_budget: float
    consumed: float = 0.0
    reserved: float = 0.0
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    status: BudgetStatus = BudgetStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_budget - self.consumed - self.reserved)

    @property
    def utilization_pct(self) -> float:
        if self.total_budget <= 0:
            return 1.0
        return (self.consumed + self.reserved) / self.total_budget


class CapitalBudget:
    """
    Multi-period capital budget management.

    Enforces: consumed ≤ period_budget for each strategy/account/portfolio.
    Supports reservation of budget capacity before actual consumption.
    """

    def __init__(
        self,
        budget_id: Optional[str] = None,
        total_budget: float = 0.0,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.budget_id = budget_id or f"cb-{uuid.uuid4().hex[:12]}"
        self.total_budget = total_budget
        self.config = config or {}
        self._lines: Dict[str, BudgetLine] = {}
        self._history: List[BudgetLine] = []

    def create_budget(
        self,
        category: str,
        amount: float,
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
    ) -> BudgetLine:
        """Create a budget line for a category (strategy/account/portfolio)."""
        line = BudgetLine(
            budget_id=f"bgl-{uuid.uuid4().hex[:8]}",
            category=category,
            total_budget=amount,
            period=period,
            expires_at=self._compute_expiry(period),
        )
        self._lines[category] = line
        return line

    def consume(self, category: str, amount: float) -> bool:
        """Consume budget for a category. Returns True if within budget."""
        line = self._lines.get(category)
        if not line:
            return False
        if line.remaining < amount:
            line.status = BudgetStatus.EXCEEDED
            return False
        line.consumed += amount
        self._update_status(line)
        return True

    def reserve(self, category: str, amount: float) -> bool:
        """Reserve budget capacity without consuming it."""
        line = self._lines.get(category)
        if not line:
            return False
        if line.remaining < amount:
            return False
        line.reserved += amount
        return True

    def release_reservation(self, category: str, amount: float) -> None:
        """Release a budget reservation."""
        line = self._lines.get(category)
        if line:
            line.reserved = max(0.0, line.reserved - amount)

    def set_allocation_pcts(self, allocations: Dict[str, float]) -> None:
        """Set budgets as percentages of total."""
        for category, pct in allocations.items():
            if category not in self._lines:
                self.create_budget(category, self.total_budget * pct)
            else:
                self._lines[category].total_budget = self.total_budget * pct

    def get_category_remaining(self, category: str) -> float:
        line = self._lines.get(category)
        return line.remaining if line else 0.0

    def get_total_remaining(self) -> float:
        return sum(line.remaining for line in self._lines.values())

    def _update_status(self, line: BudgetLine) -> None:
        if line.utilization_pct >= 0.90:
            line.status = BudgetStatus.WARNING
        if line.utilization_pct >= 1.0:
            line.status = BudgetStatus.EXCEEDED

    def _compute_expiry(self, period: BudgetPeriod) -> datetime:
        now = datetime.utcnow()
        if period == BudgetPeriod.DAILY:
            return now + timedelta(days=1)
        elif period == BudgetPeriod.WEEKLY:
            return now + timedelta(weeks=1)
        elif period == BudgetPeriod.QUARTERLY:
            return now + timedelta(days=90)
        return now + timedelta(days=30)  # MONTHLY

    def get_summary(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "total_budget": self.total_budget,
            "lines": {
                cat: {
                    "total": l.total_budget,
                    "consumed": l.consumed,
                    "reserved": l.reserved,
                    "remaining": l.remaining,
                    "status": l.status.value,
                }
                for cat, l in self._lines.items()
            },
        }
