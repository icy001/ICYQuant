"""Risk Budget Manager — risk budgeting, limits, and utilization tracking."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskBudgetType(Enum):
    VOLATILITY = "volatility"
    VAR = "var"
    CVAR = "cvar"
    TRACKING_ERROR = "tracking_error"
    DRAWDOWN = "drawdown"
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"


class LimitStatus(Enum):
    OK = "ok"
    WARNING = "warning"  # approaching limit (>= 80%)
    BREACHED = "breached"  # limit exceeded
    CRITICAL = "critical"  # severely exceeded (>= 120%)


@dataclass
class RiskLimit:
    """A single risk limit constraint."""

    limit_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    budget_type: RiskBudgetType = RiskBudgetType.VOLATILITY
    hard_limit: float = 0.0  # absolute maximum
    soft_limit: float = 0.0  # warning threshold (typically 80% of hard)
    current_value: float = 0.0
    unit: str = "%"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> LimitStatus:
        if not self.enabled or self.hard_limit <= 0:
            return LimitStatus.OK
        ratio = self.current_value / self.hard_limit
        if ratio >= 1.2:
            return LimitStatus.CRITICAL
        if ratio >= 1.0:
            return LimitStatus.BREACHED
        if ratio >= 0.8:
            return LimitStatus.WARNING
        return LimitStatus.OK

    @property
    def utilization_pct(self) -> float:
        return (self.current_value / self.hard_limit * 100) if self.hard_limit > 0 else 0.0

    @property
    def headroom(self) -> float:
        return max(0.0, self.hard_limit - self.current_value)


@dataclass
class RiskBucket:
    """A grouping of risk limits for a portfolio or strategy."""

    bucket_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    owner_id: str = ""  # portfolio_id or strategy_id
    limits: List[RiskLimit] = field(default_factory=list)
    total_budget: float = 0.0
    used_budget: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_limit(self, budget_type: RiskBudgetType) -> Optional[RiskLimit]:
        for limit in self.limits:
            if limit.budget_type == budget_type:
                return limit
        return None

    def check_all(self) -> Dict[str, LimitStatus]:
        return {limit.name or limit.budget_type.value: limit.status for limit in self.limits}

    def get_breaches(self) -> List[RiskLimit]:
        return [l for l in self.limits if l.status in (LimitStatus.BREACHED, LimitStatus.CRITICAL)]

    def get_warnings(self) -> List[RiskLimit]:
        return [l for l in self.limits if l.status == LimitStatus.WARNING]


@dataclass
class BudgetUtilization:
    """Tracks how much of a risk budget is being used."""

    budget_type: RiskBudgetType = RiskBudgetType.VOLATILITY
    allocated: float = 0.0
    used: float = 0.0
    available: float = 0.0
    utilization_pct: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RiskBudget:
    """Overall risk budget for a portfolio."""

    budget_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    name: str = ""
    total_risk_budget: float = 0.0  # e.g., 15% annual vol
    buckets: List[RiskBucket] = field(default_factory=list)
    utilization: List[BudgetUtilization] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_bucket(self, bucket_id: str) -> Optional[RiskBucket]:
        for b in self.buckets:
            if b.bucket_id == bucket_id:
                return b
        return None


class RiskBudgetManager:
    """Manages risk budgets and limits across portfolios and strategies.

    Supports:
    - Multiple risk budget types (vol, VaR, CVaR, TE, drawdown, leverage, concentration)
    - Hard and soft limits with warning thresholds
    - Risk buckets for hierarchical allocation
    - Breach detection and alerting
    """

    def __init__(self):
        self._budgets: Dict[str, RiskBudget] = {}
        self._default_limits: Dict[str, RiskLimit] = {}

    def create_budget(self, portfolio_id: str, name: str, total_risk: float) -> RiskBudget:
        budget = RiskBudget(
            portfolio_id=portfolio_id,
            name=name,
            total_risk_budget=total_risk,
        )
        self._budgets[budget.budget_id] = budget
        logger.info("Risk budget created: %s (total=%.2f%%)", name, total_risk * 100)
        return budget

    def add_bucket(
        self, budget_id: str, name: str, owner_id: str, budget_allocation: float
    ) -> Optional[RiskBucket]:
        budget = self._budgets.get(budget_id)
        if not budget:
            return None

        bucket = RiskBucket(
            name=name,
            owner_id=owner_id,
            total_budget=budget_allocation,
        )
        budget.buckets.append(bucket)
        return bucket

    def add_default_limits(self, bucket: RiskBucket) -> None:
        """Add standard institutional limits to a bucket."""
        defaults = [
            RiskLimit(
                name="Max Position Weight",
                budget_type=RiskBudgetType.CONCENTRATION,
                hard_limit=10.0,
                soft_limit=8.0,
                unit="%",
            ),
            RiskLimit(
                name="Max Sector Exposure",
                budget_type=RiskBudgetType.CONCENTRATION,
                hard_limit=30.0,
                soft_limit=25.0,
                unit="%",
            ),
            RiskLimit(
                name="Daily VaR 95%",
                budget_type=RiskBudgetType.VAR,
                hard_limit=2.0,
                soft_limit=1.5,
                unit="%",
            ),
            RiskLimit(
                name="Max Drawdown",
                budget_type=RiskBudgetType.DRAWDOWN,
                hard_limit=20.0,
                soft_limit=15.0,
                unit="%",
            ),
            RiskLimit(
                name="Max Leverage",
                budget_type=RiskBudgetType.LEVERAGE,
                hard_limit=2.0,
                soft_limit=1.5,
                unit="x",
            ),
            RiskLimit(
                name="Tracking Error",
                budget_type=RiskBudgetType.TRACKING_ERROR,
                hard_limit=5.0,
                soft_limit=3.0,
                unit="%",
            ),
            RiskLimit(
                name="Portfolio Volatility",
                budget_type=RiskBudgetType.VOLATILITY,
                hard_limit=25.0,
                soft_limit=20.0,
                unit="%",
            ),
            RiskLimit(
                name="Daily Loss Limit",
                budget_type=RiskBudgetType.VAR,
                hard_limit=5.0,
                soft_limit=3.0,
                unit="%",
            ),
            RiskLimit(
                name="Liquidity Concentration",
                budget_type=RiskBudgetType.LIQUIDITY,
                hard_limit=20.0,
                soft_limit=15.0,
                unit="% of ADV",
            ),
        ]
        bucket.limits = defaults

    def update_limit(
        self, bucket: RiskBucket, budget_type: RiskBudgetType, current_value: float
    ) -> Optional[RiskLimit]:
        limit = bucket.get_limit(budget_type)
        if limit:
            limit.current_value = current_value
            if limit.status == LimitStatus.BREACHED:
                logger.warning(
                    "Risk limit BREACHED: %s = %.2f (limit: %.2f)",
                    limit.name, current_value, limit.hard_limit,
                )
            elif limit.status == LimitStatus.CRITICAL:
                logger.critical(
                    "Risk limit CRITICAL: %s = %.2f (limit: %.2f)",
                    limit.name, current_value, limit.hard_limit,
                )
        return limit

    def check_portfolio_risk(
        self, portfolio_id: str, metrics: Dict[str, float]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check current risk metrics against all budgets for a portfolio."""
        results: Dict[str, List[Dict[str, Any]]] = {
            "breaches": [],
            "warnings": [],
            "ok": [],
        }

        for budget in self._budgets.values():
            if budget.portfolio_id != portfolio_id:
                continue
            for bucket in budget.buckets:
                for limit in bucket.limits:
                    if not limit.enabled:
                        continue

                    # Map metric name to risk type
                    metric_key = self._map_metric_to_budget_type(limit.budget_type)
                    if metric_key in metrics:
                        limit.current_value = metrics[metric_key]

                    status = limit.status.value
                    # Map "critical" and "breached" both to "breaches"
                    key = "breaches" if status in ("critical", "breached") else ("warnings" if status == "warning" else "ok")
                    results[key].append({
                        "budget_name": budget.name,
                        "bucket_name": bucket.name,
                        "limit_name": limit.name,
                        "limit_type": limit.budget_type.value,
                        "current": limit.current_value,
                        "hard_limit": limit.hard_limit,
                        "utilization_pct": limit.utilization_pct,
                        "status": limit.status.value,
                    })

        return results

    def _map_metric_to_budget_type(self, budget_type: RiskBudgetType) -> str:
        mapping = {
            RiskBudgetType.VOLATILITY: "volatility",
            RiskBudgetType.VAR: "var_95",
            RiskBudgetType.CVAR: "cvar_95",
            RiskBudgetType.TRACKING_ERROR: "tracking_error",
            RiskBudgetType.DRAWDOWN: "max_drawdown",
            RiskBudgetType.LEVERAGE: "leverage",
            RiskBudgetType.CONCENTRATION: "max_position_weight",
            RiskBudgetType.LIQUIDITY: "liquidity_concentration",
        }
        return mapping.get(budget_type, "")

    def get_budget(self, budget_id: str) -> Optional[RiskBudget]:
        return self._budgets.get(budget_id)

    def get_budgets_for_portfolio(self, portfolio_id: str) -> List[RiskBudget]:
        return [b for b in self._budgets.values() if b.portfolio_id == portfolio_id]

    def get_summary(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        budgets = list(self._budgets.values())
        if portfolio_id:
            budgets = [b for b in budgets if b.portfolio_id == portfolio_id]

        total_limits = 0
        breached = 0
        warnings = 0
        for budget in budgets:
            for bucket in budget.buckets:
                total_limits += len(bucket.limits)
                breached += len(bucket.get_breaches())
                warnings += len(bucket.get_warnings())

        return {
            "total_budgets": len(budgets),
            "total_limits": total_limits,
            "breached_limits": breached,
            "warning_limits": warnings,
            "health_pct": (
                (total_limits - breached) / total_limits * 100 if total_limits > 0 else 100.0
            ),
        }
