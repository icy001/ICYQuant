"""
Capital Account — Sub-Account Management Under the Capital Pool

Each CapitalAccount represents a segregated sub-account within the capital pool:
- Trading Account (production capital at risk)
- Research Account (capital for research and paper trading)
- Reserve Account (ring-fenced buffer capital)
- Execution Account (capital allocated to execution engines)

Each account has independent limits: capital, risk, leverage, liquidity, allocation.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AccountType(str, Enum):
    TRADING = "TRADING"
    RESEARCH = "RESEARCH"
    RESERVE = "RESERVE"
    EXECUTION = "EXECUTION"
    BUFFER = "BUFFER"


class AccountState(str, Enum):
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


@dataclass
class AccountLimits:
    capital_limit: float = float("inf")
    risk_limit: float = float("inf")
    leverage_limit: float = 1.0
    liquidity_limit: float = float("inf")
    allocation_limit: float = float("inf")
    max_drawdown_pct: float = 0.20
    max_concentration: float = 0.30


@dataclass
class AccountBalance:
    total: float = 0.0
    allocated: float = 0.0
    reserved: float = 0.0
    available: float = 0.0
    deployed: float = 0.0
    pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalAccount:
    """
    A segregated capital sub-account under the CapitalPool.

    Each account is independent with its own limits and balance tracking.
    The CapitalPool ensures aggregate conservation; accounts provide granularity.
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        account_type: AccountType = AccountType.TRADING,
        name: str = "",
        initial_capital: float = 0.0,
        limits: Optional[AccountLimits] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.account_id = account_id or f"ca-{uuid.uuid4().hex[:12]}"
        self.account_type = account_type
        self.name = name or f"{account_type.value} Account"
        self.limits = limits or AccountLimits()
        self.config = config or {}
        self.state = AccountState.ACTIVE
        self.created_at = datetime.utcnow()

        self._total = initial_capital
        self._allocated = 0.0
        self._reserved = 0.0
        self._deployed = 0.0
        self._pnl = 0.0

        self._strategy_allocations: Dict[str, float] = {}
        self._history: List[AccountBalance] = []

    # ─── Properties ──────────────────────────────────────────

    @property
    def total_capital(self) -> float:
        return self._total

    @property
    def allocated_capital(self) -> float:
        return self._allocated

    @property
    def reserved_capital(self) -> float:
        return self._reserved

    @property
    def available_capital(self) -> float:
        return max(0.0, self._total - self._allocated - self._reserved)

    @property
    def deployed_capital(self) -> float:
        return self._deployed

    @property
    def pnl(self) -> float:
        return self._pnl

    @property
    def equity(self) -> float:
        return self._total + self._pnl

    # ─── Operations ──────────────────────────────────────────

    def allocate(self, amount: float, strategy_id: str) -> float:
        amount = min(amount, self.available_capital, self.limits.allocation_limit)
        if amount <= 0:
            return 0.0
        self._allocated += amount
        self._strategy_allocations[strategy_id] = self._strategy_allocations.get(strategy_id, 0.0) + amount
        return amount

    def deallocate(self, amount: float, strategy_id: str) -> float:
        current = self._strategy_allocations.get(strategy_id, 0.0)
        amount = min(amount, current)
        self._allocated = max(0.0, self._allocated - amount)
        self._strategy_allocations[strategy_id] = current - amount
        return amount

    def deploy(self, amount: float) -> None:
        self._deployed = min(self._deployed + amount, self._allocated)

    def update_pnl(self, pnl_delta: float) -> None:
        self._pnl += pnl_delta
        self._total += pnl_delta
        self._take_snapshot()

    def set_capital(self, new_total: float) -> None:
        self._total = max(0.0, new_total)
        self._take_snapshot()

    # ─── Checks ──────────────────────────────────────────────

    def check_limit(self, requested: float) -> bool:
        return requested <= self.limits.capital_limit

    def check_leverage(self, leverage: float) -> bool:
        return leverage <= self.limits.leverage_limit

    def check_concentration(self, strategy_allocation: float) -> bool:
        if self._total <= 0:
            return True
        return (strategy_allocation / self._total) <= self.limits.max_concentration

    def get_leverage(self) -> float:
        if self._total <= 0:
            return 0.0
        return self._deployed / self._total

    def get_utilization(self) -> float:
        if self._total <= 0:
            return 0.0
        return self._allocated / self._total

    # ─── Internal ────────────────────────────────────────────

    def _take_snapshot(self) -> None:
        self._history.append(AccountBalance(
            total=self._total,
            allocated=self._allocated,
            reserved=self._reserved,
            available=self.available_capital,
            deployed=self._deployed,
            pnl=self._pnl,
        ))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "type": self.account_type.value,
            "name": self.name,
            "state": self.state.value,
            "total": self._total,
            "allocated": self._allocated,
            "available": self.available_capital,
            "deployed": self._deployed,
            "pnl": self._pnl,
            "equity": self.equity,
            "leverage": self.get_leverage(),
            "utilization": self.get_utilization(),
            "limits": {
                "capital": self.limits.capital_limit,
                "risk": self.limits.risk_limit,
                "leverage": self.limits.leverage_limit,
            },
        }
