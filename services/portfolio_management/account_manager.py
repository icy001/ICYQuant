"""Account Manager — trading account, cash, and collateral management."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AccountType(Enum):
    INDIVIDUAL = "individual"
    INSTITUTIONAL = "institutional"
    FUND = "fund"
    SEPARATE_MANAGED = "sma"
    PROPRIETARY = "proprietary"
    MARGIN = "margin"


class AccountStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    RESTRICTED = "restricted"
    CLOSED = "closed"


@dataclass
class AccountConfig:
    """Configuration for a trading account."""

    account_type: AccountType = AccountType.INSTITUTIONAL
    currency: str = "CNY"
    min_cash_balance: float = 100000.0
    margin_rate: float = 0.0
    commission_rate_bps: float = 3.0
    financing_rate_annual: float = 0.0
    max_order_value: float = float("inf")
    max_positions: int = 200
    allow_short: bool = False
    allow_margin: bool = False


@dataclass
class CashManagement:
    """Cash flow and balance management."""

    account_id: str = ""
    current_balance: float = 0.0
    available_balance: float = 0.0
    frozen_balance: float = 0.0
    unsettled_balance: float = 0.0
    interest_accrued: float = 0.0
    dividend_accrued: float = 0.0
    last_settlement_date: str = ""

    @property
    def total_cash(self) -> float:
        return self.current_balance + self.interest_accrued + self.dividend_accrued

    @property
    def utilization_pct(self) -> float:
        return ((self.current_balance - self.available_balance) / self.current_balance * 100
                if self.current_balance > 0 else 0.0)

    def can_withdraw(self, amount: float) -> bool:
        return amount <= self.available_balance

    def freeze(self, amount: float) -> bool:
        if amount > self.available_balance:
            return False
        self.available_balance -= amount
        self.frozen_balance += amount
        return True

    def unfreeze(self, amount: float) -> bool:
        if amount > self.frozen_balance:
            return False
        self.frozen_balance -= amount
        self.available_balance += amount
        return True

    def deposit(self, amount: float) -> None:
        self.current_balance += amount
        self.available_balance += amount

    def withdraw(self, amount: float) -> bool:
        if not self.can_withdraw(amount):
            return False
        self.current_balance -= amount
        self.available_balance -= amount
        return True


@dataclass
class CollateralManager:
    """Collateral and margin management."""

    account_id: str = ""
    total_collateral_value: float = 0.0
    loan_amount: float = 0.0
    maintenance_margin_pct: float = 0.25  # 25% maintenance margin
    initial_margin_pct: float = 0.50  # 50% initial margin
    margin_call_threshold: float = 0.30  # trigger at 30%
    margin_call_issued: bool = False
    margin_call_amount: float = 0.0

    @property
    def equity(self) -> float:
        return self.total_collateral_value - self.loan_amount

    @property
    def margin_level(self) -> float:
        return (self.equity / self.total_collateral_value) if self.total_collateral_value > 0 else 0.0

    @property
    def margin_deficit(self) -> float:
        required = self.total_collateral_value * self.maintenance_margin_pct
        return max(0.0, required - self.equity)

    @property
    def borrowing_power(self) -> float:
        return self.total_collateral_value * self.initial_margin_pct - self.loan_amount


@dataclass
class TradingAccount:
    """Trading account with portfolio links, cash, and collateral."""

    account_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    account_name: str = ""
    account_type: AccountType = AccountType.INSTITUTIONAL
    status: AccountStatus = AccountStatus.INACTIVE
    config: AccountConfig = field(default_factory=AccountConfig)
    cash: CashManagement = field(default_factory=CashManagement)
    collateral: Optional[CollateralManager] = None
    portfolio_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == AccountStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": self.account_type.value,
            "status": self.status.value,
            "balance": self.cash.current_balance,
            "available": self.cash.available_balance,
            "frozen": self.cash.frozen_balance,
            "portfolio_count": len(self.portfolio_ids),
            "margin_level": self.collateral.margin_level if self.collateral else None,
        }


class AccountManager:
    """Manages trading accounts, cash flows, and collateral.

    Handles:
    - Account creation and lifecycle
    - Cash deposits, withdrawals, freezes
    - Collateral and margin management
    - Account-portfolio linking
    """

    def __init__(self):
        self._accounts: Dict[str, TradingAccount] = {}

    def create_account(
        self,
        name: str,
        account_type: AccountType = AccountType.INSTITUTIONAL,
        config: Optional[AccountConfig] = None,
    ) -> TradingAccount:
        config = config or AccountConfig(account_type=account_type)
        account = TradingAccount(
            account_name=name,
            account_type=account_type,
            config=config,
            status=AccountStatus.ACTIVE,
            cash=CashManagement(),
            collateral=CollateralManager() if config.allow_margin else None,
        )
        account.cash.account_id = account.account_id
        if account.collateral:
            account.collateral.account_id = account.account_id
        self._accounts[account.account_id] = account
        logger.info("Account created: %s (%s)", name, account.account_id)
        return account

    def get_account(self, account_id: str) -> Optional[TradingAccount]:
        return self._accounts.get(account_id)

    def list_accounts(
        self,
        account_type: Optional[AccountType] = None,
        status: Optional[AccountStatus] = None,
    ) -> List[TradingAccount]:
        results = list(self._accounts.values())
        if account_type:
            results = [a for a in results if a.account_type == account_type]
        if status:
            results = [a for a in results if a.status == status]
        return results

    def deposit(self, account_id: str, amount: float) -> bool:
        account = self._accounts.get(account_id)
        if not account or not account.is_active:
            return False
        account.cash.deposit(amount)
        account.updated_at = time.time()
        logger.info("Deposit %.2f to account %s", amount, account_id)
        return True

    def withdraw(self, account_id: str, amount: float) -> bool:
        account = self._accounts.get(account_id)
        if not account or not account.is_active:
            return False
        if account.cash.withdraw(amount):
            account.updated_at = time.time()
            logger.info("Withdrawal %.2f from account %s", amount, account_id)
            return True
        return False

    def freeze_cash(self, account_id: str, amount: float) -> bool:
        account = self._accounts.get(account_id)
        if not account:
            return False
        return account.cash.freeze(amount)

    def unfreeze_cash(self, account_id: str, amount: float) -> bool:
        account = self._accounts.get(account_id)
        if not account:
            return False
        return account.cash.unfreeze(amount)

    def link_portfolio(self, account_id: str, portfolio_id: str) -> bool:
        account = self._accounts.get(account_id)
        if not account:
            return False
        if portfolio_id not in account.portfolio_ids:
            account.portfolio_ids.append(portfolio_id)
            account.updated_at = time.time()
        return True

    def unlink_portfolio(self, account_id: str, portfolio_id: str) -> bool:
        account = self._accounts.get(account_id)
        if not account:
            return False
        if portfolio_id in account.portfolio_ids:
            account.portfolio_ids.remove(portfolio_id)
            account.updated_at = time.time()
            return True
        return False

    def check_margin_call(self, account_id: str) -> Optional[float]:
        """Check if account has a margin call and return required amount."""
        account = self._accounts.get(account_id)
        if not account or not account.collateral:
            return None

        deficit = account.collateral.margin_deficit
        if deficit > 0:
            account.collateral.margin_call_issued = True
            account.collateral.margin_call_amount = deficit
            logger.warning("Margin call for account %s: %.2f", account_id, deficit)
            return deficit
        return None

    def suspend_account(self, account_id: str) -> bool:
        account = self._accounts.get(account_id)
        if account and account.status == AccountStatus.ACTIVE:
            account.status = AccountStatus.SUSPENDED
            account.updated_at = time.time()
            return True
        return False

    def close_account(self, account_id: str) -> bool:
        account = self._accounts.get(account_id)
        if not account:
            return False
        if account.cash.current_balance > 0:
            logger.warning("Account %s still has cash balance: %.2f",
                         account_id, account.cash.current_balance)
        account.status = AccountStatus.CLOSED
        account.updated_at = time.time()
        return True

    def get_total_cash(self) -> float:
        return sum(a.cash.current_balance for a in self._accounts.values())

    def get_total_available(self) -> float:
        return sum(a.cash.available_balance for a in self._accounts.values())

    def get_summary(self) -> Dict[str, Any]:
        accounts = list(self._accounts.values())
        active = sum(1 for a in accounts if a.is_active)
        total_cash = self.get_total_cash()
        total_available = self.get_total_available()
        margin_accounts = sum(1 for a in accounts if a.collateral)
        margin_calls = sum(
            1 for a in accounts
            if a.collateral and a.collateral.margin_call_issued
        )

        by_type: Dict[str, int] = {}
        for a in accounts:
            t = a.account_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_accounts": len(accounts),
            "active_accounts": active,
            "total_cash": total_cash,
            "total_available": total_available,
            "margin_accounts": margin_accounts,
            "active_margin_calls": margin_calls,
            "accounts_by_type": by_type,
        }
