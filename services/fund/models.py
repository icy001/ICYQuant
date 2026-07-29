"""Fund Operation Layer — Core Domain Models.

Defines the fund-level domain objects that power the institutional
asset management operation layer.

Objects
-------
Fund
    The core fund aggregate: fund_id, name, nav, aum, shares, cash, fees.
InvestorAccount
    Tracks an individual investor's holdings within a fund.
SubscriptionOrder / RedemptionOrder
    Fund inflow / outflow lifecycle objects.
FeeSchedule
    Management fee + performance fee configuration.
CashReserve
    Fund cash breakdown: available / frozen / pending redemption.
RebalancePlan
    Target weights + order list for automated rebalancing.
NAVRecord
    Immutable daily NAV snapshot for audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubscriptionStatus(str, Enum):
    """Subscription / redemption lifecycle status."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class RedemptionType(str, Enum):
    """Redemption settlement schedule."""

    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    TN = "TN"


class FeeType(str, Enum):
    """Fee category."""

    MANAGEMENT = "MANAGEMENT"
    PERFORMANCE = "PERFORMANCE"
    ADMINISTRATION = "ADMINISTRATION"
    CUSTODY = "CUSTODY"
    SUBSCRIPTION = "SUBSCRIPTION"
    REDEMPTION = "REDEMPTION"


class CrystallizationMode(str, Enum):
    """When performance fees are realised."""

    DAILY = "DAILY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    ON_REDEMPTION = "ON_REDEMPTION"


class RebalanceTrigger(str, Enum):
    """What triggered the rebalance."""

    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    DRIFT = "DRIFT"
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class CashReserveCategory(str, Enum):
    """Category of reserved cash."""

    AVAILABLE = "AVAILABLE"
    FROZEN = "FROZEN"
    PENDING_REDEMPTION = "PENDING_REDEMPTION"
    FEE_RESERVE = "FEE_RESERVE"
    MARGIN = "MARGIN"


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------


@dataclass
class Fund:
    """Fund aggregate root.

    Example
    -------
    >>> fund = Fund(fund_id="AI_GROWTH", fund_name="AI Growth Fund", nav=1.258, aum=523_000_000)
    >>> fund.total_shares
    415_738_473...
    """

    fund_id: str
    fund_name: str

    # Net Asset Value per share
    nav: float = 1.0

    # Assets Under Management (total notional)
    aum: float = 0.0

    # Total outstanding shares
    total_shares: float = 0.0

    # Cash holdings (liquid + reserved)
    cash_balance: float = 0.0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    nav_date: date = field(default_factory=date.today)

    # Config
    currency: str = "USD"
    management_fee_rate: float = 0.015  # 1.5% per annum
    performance_fee_rate: float = 0.20  # 20% above HWM
    high_water_mark: float = 1.0
    hurdle_rate: float = 0.0  # 0% hurdle (absolute return)
    crystallization: CrystallizationMode = CrystallizationMode.QUARTERLY

    # Metadata
    metadata: Dict[str, object] = field(default_factory=dict)

    # -- Computed properties --------------------------------------------------

    @property
    def nav_per_share(self) -> float:
        """Return NAV per share.  Equivalent to ``nav``."""
        return self.nav

    @property
    def total_net_asset(self) -> float:
        """Return total net asset = AUM."""
        return self.aum

    def shares_from_amount(self, amount: float) -> float:
        """Convert subscription amount to shares at current NAV."""
        if self.nav <= 0:
            raise ValueError("NAV must be positive")
        return amount / self.nav

    def amount_from_shares(self, shares: float) -> float:
        """Convert shares to redemption amount at current NAV."""
        return shares * self.nav

    def update_nav(self, new_nav: float, new_aum: Optional[float] = None) -> None:
        """Update NAV and optionally AUM."""
        self.nav = new_nav
        if new_aum is not None:
            self.aum = new_aum
        self.updated_at = datetime.utcnow()
        self.nav_date = date.today()

        # Track high-water mark
        if self.nav > self.high_water_mark:
            self.high_water_mark = self.nav

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "fund_name": self.fund_name,
            "nav": self.nav,
            "aum": self.aum,
            "total_shares": self.total_shares,
            "cash_balance": self.cash_balance,
            "currency": self.currency,
            "management_fee_rate": self.management_fee_rate,
            "performance_fee_rate": self.performance_fee_rate,
            "high_water_mark": self.high_water_mark,
            "hurdle_rate": self.hurdle_rate,
            "crystallization": self.crystallization.value,
            "nav_date": self.nav_date.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class InvestorAccount:
    """Tracks an investor's position within a fund.

    Example
    -------
    >>> acct = InvestorAccount(account_id="INV_001", fund_id="AI_GROWTH", shares=100_000.0, cost_basis=125_000.0)
    >>> acct.current_value(nav=1.30)
    130000.0
    """

    account_id: str = field(default_factory=lambda: f"INV_{uuid4().hex[:8].upper()}")
    fund_id: str = ""
    investor_name: str = ""

    shares: float = 0.0
    cost_basis: float = 0.0  # total invested

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # -- Computed -------------------------------------------------------------

    @property
    def avg_cost_per_share(self) -> float:
        if self.shares == 0:
            return 0.0
        return self.cost_basis / self.shares

    def current_value(self, nav: float) -> float:
        """Market value at given NAV."""
        return self.shares * nav

    def unrealized_pnl(self, nav: float) -> float:
        return self.current_value(nav) - self.cost_basis

    def add_shares(self, shares: float, cost: float) -> None:
        """Add shares via subscription."""
        self.shares += shares
        self.cost_basis += cost
        self.updated_at = datetime.utcnow()

    def remove_shares(self, shares: float) -> float:
        """Remove shares via redemption; return redeemed cost."""
        if shares > self.shares:
            raise ValueError(f"Insufficient shares: {self.shares} < {shares}")
        redeemed_cost = (shares / self.shares) * self.cost_basis if self.shares > 0 else 0.0
        self.shares -= shares
        self.cost_basis -= redeemed_cost
        self.updated_at = datetime.utcnow()
        return redeemed_cost

    def to_dict(self) -> Dict[str, object]:
        return {
            "account_id": self.account_id,
            "fund_id": self.fund_id,
            "investor_name": self.investor_name,
            "shares": self.shares,
            "cost_basis": self.cost_basis,
            "avg_cost_per_share": self.avg_cost_per_share,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SubscriptionOrder:
    """A subscription (inflow) order lifecycle object.

    Example
    -------
    >>> order = SubscriptionOrder(fund_id="AI_GROWTH", account_id="INV_001", amount=1_000_000, nav=1.25)
    >>> order.shares_allocated
    800000.0
    """

    order_id: str = field(default_factory=lambda: f"SUB_{uuid4().hex[:12].upper()}")
    fund_id: str = ""
    account_id: str = ""

    amount: float = 0.0
    nav: float = 1.0
    status: SubscriptionStatus = SubscriptionStatus.PENDING

    shares_allocated: float = 0.0
    settlement_date: date = field(default_factory=date.today)

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.shares_allocated == 0.0 and self.nav > 0:
            self.shares_allocated = self.amount / self.nav

    def confirm(self) -> None:
        if self.status != SubscriptionStatus.PENDING:
            raise ValueError(f"Cannot confirm order in status {self.status}")
        self.status = SubscriptionStatus.CONFIRMED
        self.updated_at = datetime.utcnow()

    def settle(self) -> None:
        if self.status != SubscriptionStatus.CONFIRMED:
            raise ValueError(f"Cannot settle order in status {self.status}")
        self.status = SubscriptionStatus.SETTLED
        self.updated_at = datetime.utcnow()

    def reject(self, reason: str = "") -> None:
        self.status = SubscriptionStatus.REJECTED
        self.metadata["reject_reason"] = reason
        self.updated_at = datetime.utcnow()

    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "order_id": self.order_id,
            "fund_id": self.fund_id,
            "account_id": self.account_id,
            "amount": self.amount,
            "nav": self.nav,
            "status": self.status.value,
            "shares_allocated": self.shares_allocated,
            "settlement_date": self.settlement_date.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RedemptionOrder:
    """A redemption (outflow) order lifecycle object.

    Example
    -------
    >>> order = RedemptionOrder(fund_id="AI_GROWTH", account_id="INV_001", shares=500_000, nav=1.25)
    >>> order.redemption_amount
    625000.0
    """

    order_id: str = field(default_factory=lambda: f"RED_{uuid4().hex[:12].upper()}")
    fund_id: str = ""
    account_id: str = ""

    shares: float = 0.0
    nav: float = 1.0
    redemption_type: RedemptionType = RedemptionType.T1
    status: SubscriptionStatus = SubscriptionStatus.PENDING

    settlement_date: date = field(default_factory=date.today)

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def redemption_amount(self) -> float:
        return self.shares * self.nav

    def confirm(self) -> None:
        if self.status != SubscriptionStatus.PENDING:
            raise ValueError(f"Cannot confirm order in status {self.status}")
        self.status = SubscriptionStatus.CONFIRMED
        self.updated_at = datetime.utcnow()

    def settle(self) -> None:
        if self.status != SubscriptionStatus.CONFIRMED:
            raise ValueError(f"Cannot settle order in status {self.status}")
        self.status = SubscriptionStatus.SETTLED
        self.updated_at = datetime.utcnow()

    def reject(self, reason: str = "") -> None:
        self.status = SubscriptionStatus.REJECTED
        self.metadata["reject_reason"] = reason
        self.updated_at = datetime.utcnow()

    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "order_id": self.order_id,
            "fund_id": self.fund_id,
            "account_id": self.account_id,
            "shares": self.shares,
            "nav": self.nav,
            "redemption_amount": self.redemption_amount,
            "redemption_type": self.redemption_type.value,
            "status": self.status.value,
            "settlement_date": self.settlement_date.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FeeSchedule:
    """Configuration for fund fees.

    Example
    -------
    >>> schedule = FeeSchedule(management_fee_pct=1.5, performance_fee_pct=20.0)
    >>> schedule.annual_management_fee(aum=100_000_000)
    1500000.0
    """

    management_fee_pct: float = 1.5  # annual, %
    performance_fee_pct: float = 20.0  # above HWM / hurdle, %
    administration_fee_pct: float = 0.0
    custody_fee_pct: float = 0.0
    subscription_fee_pct: float = 0.0
    redemption_fee_pct: float = 0.0

    hurdle_rate: float = 0.0  # annualised %
    high_water_mark: float = 1.0
    crystallization: CrystallizationMode = CrystallizationMode.QUARTERLY

    def annual_management_fee(self, aum: float) -> float:
        return aum * self.management_fee_pct / 100.0

    def daily_management_fee(self, aum: float) -> float:
        return self.annual_management_fee(aum) / 365.0

    def performance_fee(
        self,
        nav: float,
        previous_hwm: float,
        shares: float,
        hurdle_return: Optional[float] = None,
    ) -> float:
        """Calculate performance fee above high-water mark.

        Fee = max(0, (nav - max(hwm, nav_0 * (1 + hurdle))) * shares * fee_rate
        """
        effective_hwm = previous_hwm
        if hurdle_return is not None and hurdle_return > 0:
            hurdle_nav = previous_hwm * (1.0 + hurdle_return)
            effective_hwm = max(previous_hwm, hurdle_nav)

        excess = nav - effective_hwm
        if excess <= 0:
            return 0.0
        return excess * shares * self.performance_fee_pct / 100.0

    def subscription_fee(self, amount: float) -> float:
        return amount * self.subscription_fee_pct / 100.0

    def redemption_fee(self, amount: float) -> float:
        return amount * self.redemption_fee_pct / 100.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "management_fee_pct": self.management_fee_pct,
            "performance_fee_pct": self.performance_fee_pct,
            "administration_fee_pct": self.administration_fee_pct,
            "custody_fee_pct": self.custody_fee_pct,
            "subscription_fee_pct": self.subscription_fee_pct,
            "redemption_fee_pct": self.redemption_fee_pct,
            "hurdle_rate": self.hurdle_rate,
            "high_water_mark": self.high_water_mark,
            "crystallization": self.crystallization.value,
        }


@dataclass
class CashReserve:
    """Fund cash position breakdown.

    Example
    -------
    >>> reserve = CashReserve(total=30_000_000, frozen=5_000_000)
    >>> reserve.available
    25000000.0
    """

    fund_id: str = ""
    total: float = 0.0

    frozen: float = 0.0  # locked for pending orders
    pending_redemption: float = 0.0
    fee_reserve: float = 0.0
    margin: float = 0.0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def available(self) -> float:
        """Investable cash."""
        return self.total - self.frozen - self.pending_redemption - self.fee_reserve - self.margin

    @property
    def locked(self) -> float:
        """Total non-available cash."""
        return self.frozen + self.pending_redemption + self.fee_reserve + self.margin

    def freeze(self, amount: float) -> None:
        """Freeze cash for a pending operation."""
        if amount > self.available:
            raise ValueError(f"Insufficient available cash: {self.available} < {amount}")
        self.frozen += amount
        self.timestamp = datetime.utcnow()

    def unfreeze(self, amount: float) -> None:
        """Release previously frozen cash."""
        self.frozen = max(0.0, self.frozen - amount)
        self.timestamp = datetime.utcnow()

    def reserve_redemption(self, amount: float) -> None:
        if amount > self.available:
            raise ValueError(f"Insufficient available cash for redemption: {self.available} < {amount}")
        self.pending_redemption += amount
        self.timestamp = datetime.utcnow()

    def release_redemption(self, amount: float) -> None:
        self.total -= amount
        self.pending_redemption = max(0.0, self.pending_redemption - amount)
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "total": self.total,
            "available": self.available,
            "frozen": self.frozen,
            "pending_redemption": self.pending_redemption,
            "fee_reserve": self.fee_reserve,
            "margin": self.margin,
            "locked": self.locked,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RebalancePlan:
    """Target weights + orders for automated portfolio rebalancing.

    Example
    -------
    >>> plan = RebalancePlan(fund_id="AI_GROWTH", trigger=RebalanceTrigger.INFLOW, new_cash=50_000_000)
    """

    plan_id: str = field(default_factory=lambda: f"RBL_{uuid4().hex[:8].upper()}")
    fund_id: str = ""
    trigger: RebalanceTrigger = RebalanceTrigger.SCHEDULED

    target_weights: Dict[str, float] = field(default_factory=dict)  # strategy -> weight
    current_weights: Dict[str, float] = field(default_factory=dict)
    orders: List[Dict[str, object]] = field(default_factory=list)  # [{strategy, symbol, side, quantity, ...}]

    new_cash: float = 0.0
    estimated_cost: float = 0.0

    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None

    def add_order(self, strategy: str, symbol: str, side: str, quantity: float, price: Optional[float] = None) -> None:
        self.orders.append({
            "strategy": strategy,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
        })

    def to_dict(self) -> Dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "fund_id": self.fund_id,
            "trigger": self.trigger.value,
            "target_weights": self.target_weights,
            "current_weights": self.current_weights,
            "orders": self.orders,
            "new_cash": self.new_cash,
            "estimated_cost": self.estimated_cost,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


@dataclass(frozen=True)
class NAVRecord:
    """Immutable daily NAV snapshot for audit trail."""

    fund_id: str
    date: date
    nav: float
    aum: float
    total_shares: float
    cash_balance: float
    management_fee_accrued: float = 0.0
    performance_fee_accrued: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "fund_id": self.fund_id,
            "date": self.date.isoformat(),
            "nav": self.nav,
            "aum": self.aum,
            "total_shares": self.total_shares,
            "cash_balance": self.cash_balance,
            "management_fee_accrued": self.management_fee_accrued,
            "performance_fee_accrued": self.performance_fee_accrued,
            "created_at": self.created_at.isoformat(),
        }
