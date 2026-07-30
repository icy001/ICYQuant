"""Fund Manager — Fund of Funds (FoF) management and sub-fund allocation."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FundType(Enum):
    EQUITY_LONG = "equity_long"
    EQUITY_LONG_SHORT = "equity_long_short"
    MARKET_NEUTRAL = "market_neutral"
    CTA = "cta"
    MACRO = "macro"
    MULTI_STRATEGY = "multi_strategy"
    FIXED_INCOME = "fixed_income"
    BALANCED = "balanced"
    AI_DRIVEN = "ai_driven"
    CUSTOM = "custom"


class FundStatus(Enum):
    INCUBATION = "incubation"
    ACTIVE = "active"
    SOFT_CLOSED = "soft_closed"  # accepting limited capital
    HARD_CLOSED = "hard_closed"  # no new capital
    WIND_DOWN = "wind_down"
    CLOSED = "closed"


@dataclass
class SubFund:
    """A sub-fund within a FoF structure."""

    fund_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    fund_type: FundType = FundType.MULTI_STRATEGY
    status: FundStatus = FundStatus.ACTIVE
    manager: str = ""
    aum: float = 0.0
    capacity: float = 0.0
    allocated_capital: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0
    inception_date: str = ""
    annual_return: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    management_fee_pct: float = 1.0
    performance_fee_pct: float = 20.0
    hurdle_rate: float = 0.0
    lockup_period_months: int = 0
    redemption_notice_days: int = 30
    liquidity_profile: str = "monthly"  # daily | weekly | monthly | quarterly
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in (FundStatus.ACTIVE, FundStatus.SOFT_CLOSED)

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.capacity - self.allocated_capital)

    @property
    def utilization_pct(self) -> float:
        return (self.allocated_capital / self.capacity * 100) if self.capacity > 0 else 0.0


@dataclass
class FoFAllocation:
    """FoF-level allocation across sub-funds."""

    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    fof_id: str = ""
    sub_fund_id: str = ""
    allocated_capital: float = 0.0
    target_weight: float = 0.0
    current_value: float = 0.0
    current_weight: float = 0.0
    return_since_allocation: float = 0.0
    fees_paid: float = 0.0
    last_rebalanced: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FoFPerformance:
    """FoF-level performance metrics."""

    fof_id: str = ""
    period: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    alpha_to_benchmark: float = 0.0
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    sub_fund_contributions: Dict[str, float] = field(default_factory=dict)
    net_of_fees: bool = True
    calculated_at: float = field(default_factory=time.time)


@dataclass
class FoFRebalance:
    """FoF rebalance record."""

    rebalance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    fof_id: str = ""
    before_weights: Dict[str, float] = field(default_factory=dict)
    after_weights: Dict[str, float] = field(default_factory=dict)
    inflows: Dict[str, float] = field(default_factory=dict)  # fund_id -> amount
    outflows: Dict[str, float] = field(default_factory=dict)
    total_rebalanced: float = 0.0
    reason: str = ""
    executed_at: float = field(default_factory=time.time)


@dataclass
class FoFConfig:
    """Fund of Funds configuration."""

    name: str = ""
    total_capital: float = 0.0
    target_return: float = 0.12
    risk_budget: float = 0.15
    max_sub_fund_weight: float = 0.30
    min_sub_fund_weight: float = 0.02
    max_sub_funds: int = 15
    rebalance_frequency_months: int = 3
    drift_threshold_pct: float = 5.0
    cash_reserve_pct: float = 2.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FundOfFunds:
    """A Fund of Funds (FoF) — meta-portfolio investing in sub-funds."""

    fof_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: FoFConfig = field(default_factory=FoFConfig)
    sub_funds: Dict[str, SubFund] = field(default_factory=dict)
    allocations: List[FoFAllocation] = field(default_factory=list)
    performance_history: List[FoFPerformance] = field(default_factory=list)
    rebalance_history: List[FoFRebalance] = field(default_factory=list)
    total_nav: float = 0.0
    total_fees_accrued: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def sub_fund_count(self) -> int:
        return len(self.sub_funds)

    def get_sub_fund(self, fund_id: str) -> Optional[SubFund]:
        return self.sub_funds.get(fund_id)


class FundManager:
    """Manages Fund of Funds (FoF) structures and sub-fund allocation.

    Handles:
    - FoF creation and configuration
    - Sub-fund onboarding and due diligence tracking
    - Capital allocation across sub-funds
    - Performance monitoring and fee calculation
    - FoF-level rebalancing
    """

    def __init__(self):
        self._fofs: Dict[str, FundOfFunds] = {}
        self._sub_funds: Dict[str, SubFund] = {}  # master registry

    def create_fof(self, config: FoFConfig) -> FundOfFunds:
        fof = FundOfFunds(config=config)
        fof.total_nav = config.total_capital
        self._fofs[fof.fof_id] = fof
        logger.info("FoF created: %s (capital=%.2f)", config.name, config.total_capital)
        return fof

    def register_sub_fund(self, sub_fund: SubFund) -> SubFund:
        self._sub_funds[sub_fund.fund_id] = sub_fund
        logger.info("Sub-fund registered: %s (%s)", sub_fund.name, sub_fund.fund_type.value)
        return sub_fund

    def add_sub_fund_to_fof(self, fof_id: str, fund_id: str, target_weight: float) -> bool:
        fof = self._fofs.get(fof_id)
        sub_fund = self._sub_funds.get(fund_id)
        if not fof or not sub_fund:
            return False

        if fof.sub_fund_count >= fof.config.max_sub_funds:
            logger.warning("FoF %s reached max sub-funds (%d)", fof_id, fof.config.max_sub_funds)
            return False

        if target_weight > fof.config.max_sub_fund_weight:
            target_weight = fof.config.max_sub_fund_weight

        fof.sub_funds[fund_id] = sub_fund
        allocated = fof.config.total_capital * target_weight / 100.0

        allocation = FoFAllocation(
            fof_id=fof_id,
            sub_fund_id=fund_id,
            allocated_capital=allocated,
            target_weight=target_weight,
            current_value=allocated,
            current_weight=target_weight,
        )
        fof.allocations.append(allocation)
        sub_fund.allocated_capital += allocated
        fof.updated_at = time.time()
        return True

    def get_fof(self, fof_id: str) -> Optional[FundOfFunds]:
        return self._fofs.get(fof_id)

    def list_fofs(self) -> List[FundOfFunds]:
        return list(self._fofs.values())

    def get_sub_fund(self, fund_id: str) -> Optional[SubFund]:
        return self._sub_funds.get(fund_id)

    def list_sub_funds(
        self,
        fund_type: Optional[FundType] = None,
        status: Optional[FundStatus] = None,
    ) -> List[SubFund]:
        results = list(self._sub_funds.values())
        if fund_type:
            results = [f for f in results if f.fund_type == fund_type]
        if status:
            results = [f for f in results if f.status == status]
        return results

    def calculate_fof_nav(self, fof_id: str) -> float:
        """Calculate current total NAV for a FoF."""
        fof = self._fofs.get(fof_id)
        if not fof:
            return 0.0

        total = 0.0
        for alloc in fof.allocations:
            sub = fof.sub_funds.get(alloc.sub_fund_id)
            if sub:
                # Update current value based on sub-fund return
                current = alloc.allocated_capital * (1 + sub.annual_return / 252)
                alloc.current_value = current
                alloc.return_since_allocation = (
                    (current - alloc.allocated_capital) / alloc.allocated_capital
                    if alloc.allocated_capital > 0 else 0.0
                )
                total += current

        fof.total_nav = total
        # Recalculate current weights
        if total > 0:
            for alloc in fof.allocations:
                alloc.current_weight = alloc.current_value / total * 100

        fof.updated_at = time.time()
        return total

    def calculate_fees(self, fof_id: str) -> Dict[str, float]:
        """Calculate management and performance fees for all sub-funds."""
        fof = self._fofs.get(fof_id)
        if not fof:
            return {}

        fees = {}
        total = 0.0
        for alloc in fof.allocations:
            sub = fof.sub_funds.get(alloc.sub_fund_id)
            if not sub:
                continue

            mgmt_fee = alloc.allocated_capital * sub.management_fee_pct / 100.0
            perf_fee = 0.0
            profit = alloc.current_value - alloc.allocated_capital
            if profit > 0 and sub.performance_fee_pct > 0:
                # Performance fee above hurdle rate
                hurdle_amount = alloc.allocated_capital * sub.hurdle_rate
                if profit > hurdle_amount:
                    perf_fee = (profit - hurdle_amount) * sub.performance_fee_pct / 100.0

            total_fee = mgmt_fee + perf_fee
            fees[sub.name] = {
                "management_fee": mgmt_fee,
                "performance_fee": perf_fee,
                "total_fee": total_fee,
            }
            alloc.fees_paid += total_fee
            total += total_fee

        fof.total_fees_accrued += total
        return fees

    def get_summary(self) -> Dict[str, Any]:
        fofs = list(self._fofs.values())
        total_aum = sum(f.total_nav for f in fofs)
        total_sub_funds = sum(f.sub_fund_count for f in fofs)
        total_fees = sum(f.total_fees_accrued for f in fofs)

        sub_by_type: Dict[str, int] = {}
        for sf in self._sub_funds.values():
            t = sf.fund_type.value
            sub_by_type[t] = sub_by_type.get(t, 0) + 1

        return {
            "total_fofs": len(fofs),
            "total_aum": total_aum,
            "total_sub_funds": total_sub_funds,
            "master_registry_size": len(self._sub_funds),
            "total_fees_accrued": total_fees,
            "sub_funds_by_type": sub_by_type,
        }
