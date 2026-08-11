"""
Virtual Account
===============
Simulated trading account with multi-currency support, transaction
history, and account-level metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AccountCurrency(str, Enum):
    USD = "USD"
    CNY = "CNY"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    HKD = "HKD"


@dataclass
class VirtualTransaction:
    """A single account transaction."""
    txn_id: str = field(default_factory=lambda: f"vtxn_{uuid4().hex[:12]}")
    account_id: str = ""
    type: str = ""          # deposit / withdrawal / trade / commission / dividend
    amount: float = 0.0
    currency: str = "USD"
    balance_after: float = 0.0
    description: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VirtualAccount:
    """Simulated trading account.

    Tracks balances, transactions, and account-level metrics.
    """

    def __init__(self, account_id: str = ""):
        self._account_id = account_id or f"va_{uuid4().hex[:12]}"
        self._balances: Dict[str, float] = {}
        self._initial_balances: Dict[str, float] = {}
        self._transactions: List[VirtualTransaction] = []
        self._base_currency: str = AccountCurrency.USD.value
        self.is_initialized = False

    async def initialize(self, initial_capital: float = 100_000.0,
                         currency: str = "USD") -> None:
        """Initialize account with starting capital."""
        self._base_currency = currency
        self._balances[currency] = initial_capital
        self._initial_balances[currency] = initial_capital

        self._transactions.append(VirtualTransaction(
            account_id=self._account_id,
            type="deposit",
            amount=initial_capital,
            currency=currency,
            balance_after=initial_capital,
            description="Initial deposit",
        ))
        self.is_initialized = True
        logger.info("VirtualAccount %s initialized with %s %s",
                     self._account_id, initial_capital, currency)

    # ------------------------------------------------------------------
    # Balance Operations
    # ------------------------------------------------------------------

    def get_balance(self, currency: Optional[str] = None) -> float:
        """Get balance for a currency (defaults to base currency)."""
        return self._balances.get(currency or self._base_currency, 0.0)

    async def deposit(self, amount: float, currency: Optional[str] = None,
                      description: str = "") -> VirtualTransaction:
        """Deposit funds."""
        cur = currency or self._base_currency
        self._balances[cur] = self._balances.get(cur, 0.0) + amount
        txn = VirtualTransaction(
            account_id=self._account_id,
            type="deposit",
            amount=amount,
            currency=cur,
            balance_after=self._balances[cur],
            description=description,
        )
        self._transactions.append(txn)
        return txn

    async def withdraw(self, amount: float, currency: Optional[str] = None,
                       description: str = "") -> VirtualTransaction:
        """Withdraw funds."""
        cur = currency or self._base_currency
        current = self._balances.get(cur, 0.0)
        if amount > current:
            raise ValueError(f"Insufficient {cur} balance: {current} < {amount}")
        self._balances[cur] = current - amount
        txn = VirtualTransaction(
            account_id=self._account_id,
            type="withdrawal",
            amount=-amount,
            currency=cur,
            balance_after=self._balances[cur],
            description=description,
        )
        self._transactions.append(txn)
        return txn

    async def record_trade_settlement(self, amount: float,
                                      currency: Optional[str] = None,
                                      description: str = "") -> VirtualTransaction:
        """Record a trade settlement (P&L impact on cash)."""
        cur = currency or self._base_currency
        self._balances[cur] = self._balances.get(cur, 0.0) + amount
        txn = VirtualTransaction(
            account_id=self._account_id,
            type="trade",
            amount=amount,
            currency=cur,
            balance_after=self._balances[cur],
            description=description,
        )
        self._transactions.append(txn)
        return txn

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def total_equity(self) -> float:
        """Total account equity (simplified: sum of all currency balances)."""
        return sum(self._balances.values())

    def total_pnl(self) -> float:
        """Total P&L since account creation."""
        initial = sum(self._initial_balances.values())
        return self.total_equity() - initial

    def total_pnl_pct(self) -> float:
        initial = sum(self._initial_balances.values())
        if initial <= 0:
            return 0.0
        return (self.total_pnl() / initial) * 100

    def transaction_count(self) -> int:
        return len(self._transactions)

    def recent_transactions(self, limit: int = 50) -> List[VirtualTransaction]:
        return self._transactions[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "account_id": self._account_id,
            "base_currency": self._base_currency,
            "total_equity": round(self.total_equity(), 2),
            "total_pnl": round(self.total_pnl(), 2),
            "total_pnl_pct": round(self.total_pnl_pct(), 4),
            "transaction_count": self.transaction_count(),
            "balances": {k: round(v, 2) for k, v in self._balances.items()},
        }
