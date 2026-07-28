"""AI Risk Budget Engine — hierarchical risk budget allocation & tracking.

Distributes total portfolio risk budget across strategies, asset classes,
sectors, and individual positions. Monitors risk utilization and provides
early warnings when budgets are approached.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BudgetLevel(str, Enum):
    """Hierarchical levels for risk budget allocation."""

    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    ASSET_CLASS = "asset_class"
    SECTOR = "sector"
    POSITION = "position"


class BudgetMethod(str, Enum):
    """Risk budget allocation methodologies."""

    EQUAL_DISTRIBUTION = "equal_distribution"
    VOLATILITY_WEIGHTED = "volatility_weighted"
    SHARPE_WEIGHTED = "sharpe_weighted"
    CUSTOM = "custom"


class BudgetStatus(str, Enum):
    """Risk budget consumption status."""

    UNDER_BUDGET = "under_budget"  # < 70% consumed
    NORMAL = "normal"  # 70–90% consumed
    NEAR_LIMIT = "near_limit"  # 90–100% consumed
    EXCEEDED = "exceeded"  # > 100% consumed


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RiskBudget:
    """Risk budget allocation for a single entity.

    Attributes:
        entity_id: Identifier (strategy name, sector, symbol, etc.).
        level: Hierarchical budget level.
        budget_pct: Allocated risk budget as percentage of total (0–1).
        consumed_pct: Currently consumed risk (0–1).
        utilization: consumed / budget ratio.
        status: Current budget status.
        var_limit: VaR limit for this entity.
        cvar_limit: CVaR limit for this entity.
        max_drawdown_limit: Maximum allowable drawdown.
    """

    entity_id: str
    level: BudgetLevel
    budget_pct: float
    consumed_pct: float = 0.0
    var_limit: float = 0.02
    cvar_limit: float = 0.03
    max_drawdown_limit: float = 0.10

    @property
    def utilization(self) -> float:
        """Risk budget utilization ratio (consumed / budget)."""
        return self.consumed_pct / max(self.budget_pct, 0.0001)

    @property
    def remaining(self) -> float:
        """Remaining risk budget."""
        return max(0.0, self.budget_pct - self.consumed_pct)

    @property
    def status(self) -> BudgetStatus:
        """Current budget consumption status."""
        if self.utilization >= 1.0:
            return BudgetStatus.EXCEEDED
        elif self.utilization >= 0.9:
            return BudgetStatus.NEAR_LIMIT
        elif self.utilization >= 0.7:
            return BudgetStatus.NORMAL
        else:
            return BudgetStatus.UNDER_BUDGET

    @property
    def is_exceeded(self) -> bool:
        """Whether the budget has been exceeded."""
        return self.status == BudgetStatus.EXCEEDED

    @property
    def is_near_limit(self) -> bool:
        """Whether the budget is near its limit."""
        return self.status == BudgetStatus.NEAR_LIMIT


@dataclass
class BudgetAllocation:
    """Complete risk budget allocation result.

    Attributes:
        total_risk_budget: Total portfolio risk budget (as volatility %).
        budgets: List of per-entity risk budgets.
        method: Allocation method used.
        unused_budget: Total unallocated risk budget.
        concentration: Budget concentration (HHI normalized).
        timestamp: When allocation was computed.
        metadata: Additional allocation context.
    """

    total_risk_budget: float
    budgets: list[RiskBudget]
    method: BudgetMethod = BudgetMethod.EQUAL_DISTRIBUTION
    unused_budget: float = 0.0
    concentration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def exceeded_budgets(self) -> list[RiskBudget]:
        """List of budgets that have been exceeded."""
        return [b for b in self.budgets if b.is_exceeded]

    @property
    def near_limit_budgets(self) -> list[RiskBudget]:
        """List of budgets near their limits."""
        return [b for b in self.budgets if b.is_near_limit]

    @property
    def total_consumed(self) -> float:
        """Total risk consumed across all budgets."""
        return sum(b.consumed_pct for b in self.budgets)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "total_risk_budget": self.total_risk_budget,
            "budgets": [
                {
                    "entity_id": b.entity_id,
                    "level": b.level.value,
                    "budget_pct": b.budget_pct,
                    "consumed_pct": b.consumed_pct,
                    "utilization": b.utilization,
                    "status": b.status.value,
                    "var_limit": b.var_limit,
                    "cvar_limit": b.cvar_limit,
                }
                for b in self.budgets
            ],
            "method": self.method.value,
            "unused_budget": self.unused_budget,
            "concentration": self.concentration,
        }


# ---------------------------------------------------------------------------
# RiskBudgetEngine
# ---------------------------------------------------------------------------


class RiskBudgetEngine:
    """AI-driven risk budget engine.

    Allocates total portfolio risk budget across hierarchical levels
    using multiple methodologies. Tracks consumption and provides
    warnings when budgets are approached or exceeded.

    Attributes:
        method: Default allocation method.
        total_budget: Total portfolio risk budget (annual vol %).
        max_single_position: Maximum risk budget for any single position.
        history: Past budget allocations.
    """

    LEVEL_WEIGHTS: dict[BudgetLevel, float] = {
        BudgetLevel.PORTFOLIO: 1.0,
        BudgetLevel.STRATEGY: 0.6,
        BudgetLevel.ASSET_CLASS: 0.4,
        BudgetLevel.SECTOR: 0.25,
        BudgetLevel.POSITION: 0.10,
    }

    DEFAULT_LIMITS: dict[BudgetLevel, dict[str, float]] = {
        BudgetLevel.PORTFOLIO: {"var": 0.02, "cvar": 0.03, "max_dd": 0.15},
        BudgetLevel.STRATEGY: {"var": 0.015, "cvar": 0.02, "max_dd": 0.10},
        BudgetLevel.ASSET_CLASS: {"var": 0.01, "cvar": 0.015, "max_dd": 0.08},
        BudgetLevel.SECTOR: {"var": 0.008, "cvar": 0.012, "max_dd": 0.05},
        BudgetLevel.POSITION: {"var": 0.005, "cvar": 0.008, "max_dd": 0.03},
    }

    def __init__(
        self,
        method: BudgetMethod = BudgetMethod.EQUAL_DISTRIBUTION,
        total_budget: float = 0.15,  # 15% annual vol budget
        max_single_position: float = 0.05,
    ) -> None:
        """Initialize the risk budget engine.

        Args:
            method: Default allocation method.
            total_budget: Total portfolio risk budget as annualized volatility.
            max_single_position: Max risk budget for any single position.
        """
        self.method = method
        self.total_budget = total_budget
        self.max_single_position = max_single_position
        self.history: list[BudgetAllocation] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def allocate(
        self,
        entities: list[dict[str, Any]],
        method: Optional[BudgetMethod] = None,
        consumption: Optional[dict[str, float]] = None,
    ) -> BudgetAllocation:
        """Allocate risk budget across entities.

        Args:
            entities: List of entity dicts with keys: entity_id, level,
                      volatility, sharpe, weight (custom budget weight).
            method: Override default allocation method.
            consumption: Current risk consumption per entity_id.

        Returns:
            BudgetAllocation with allocated risk budgets.
        """
        method = method or self.method
        consumption = consumption or {}

        # Allocate budgets by method
        if method == BudgetMethod.EQUAL_DISTRIBUTION:
            budgets = self._allocate_equal(entities)
        elif method == BudgetMethod.VOLATILITY_WEIGHTED:
            budgets = self._allocate_volatility_weighted(entities)
        elif method == BudgetMethod.SHARPE_WEIGHTED:
            budgets = self._allocate_sharpe_weighted(entities)
        elif method == BudgetMethod.CUSTOM:
            budgets = self._allocate_custom(entities)
        else:
            budgets = self._allocate_equal(entities)

        # Cap individual budgets
        level_max = {
            BudgetLevel.POSITION: self.max_single_position,
            BudgetLevel.SECTOR: self.max_single_position * 2,
            BudgetLevel.ASSET_CLASS: self.max_single_position * 3,
            BudgetLevel.STRATEGY: self.max_single_position * 5,
            BudgetLevel.PORTFOLIO: self.total_budget,
        }

        for b in budgets:
            max_b = level_max.get(b.level, self.max_single_position)
            if b.budget_pct > max_b:
                b.budget_pct = max_b

        # Renormalize
        total_allocated = sum(b.budget_pct for b in budgets)
        if total_allocated > 0:
            for b in budgets:
                b.budget_pct = (b.budget_pct / total_allocated) * self.total_budget

        # Set consumption
        for b in budgets:
            b.consumed_pct = consumption.get(b.entity_id, 0.0)

        # Remove consumed from budget to get unused
        total_consumed = sum(b.consumed_pct for b in budgets)
        unused = max(0.0, self.total_budget - total_consumed)

        # Concentration metric
        n = max(len(budgets), 1)
        weights = [b.budget_pct / self.total_budget for b in budgets]
        hhi = sum(w**2 for w in weights)
        conc = max(0.0, min(1.0, (hhi * n - 1.0) / (n - 1.0))) if n > 1 else 1.0

        result = BudgetAllocation(
            total_risk_budget=self.total_budget,
            budgets=budgets,
            method=method,
            unused_budget=unused,
            concentration=conc,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Allocation Methods
    # ------------------------------------------------------------------

    def _allocate_equal(
        self,
        entities: list[dict[str, Any]],
    ) -> list[RiskBudget]:
        """Equal distribution of risk budget."""
        n = max(len(entities), 1)
        budget_per = self.total_budget / n

        return [
            RiskBudget(
                entity_id=e["entity_id"],
                level=BudgetLevel(e["level"]),
                budget_pct=budget_per,
                var_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("var", 0.005),
                cvar_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("cvar", 0.008),
                max_drawdown_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("max_dd", 0.03),
            )
            for e in entities
        ]

    def _allocate_volatility_weighted(
        self,
        entities: list[dict[str, Any]],
    ) -> list[RiskBudget]:
        """Allocate budget proportional to entity volatility."""
        vols = {}
        for e in entities:
            vols[e["entity_id"]] = max(e.get("volatility", 0.15), 0.01)

        total_vol = sum(vols.values())
        if total_vol == 0:
            return self._allocate_equal(entities)

        return [
            RiskBudget(
                entity_id=e["entity_id"],
                level=BudgetLevel(e["level"]),
                budget_pct=self.total_budget * (vols[e["entity_id"]] / total_vol),
                var_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("var", 0.005),
                cvar_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("cvar", 0.008),
                max_drawdown_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("max_dd", 0.03),
            )
            for e in entities
        ]

    def _allocate_sharpe_weighted(
        self,
        entities: list[dict[str, Any]],
    ) -> list[RiskBudget]:
        """Allocate budget proportional to Sharpe ratio (higher Sharpe = more budget)."""
        sharpes = {}
        for e in entities:
            sharpes[e["entity_id"]] = max(e.get("sharpe", 0.5), 0.1)

        total_s = sum(sharpes.values())
        if total_s == 0:
            return self._allocate_equal(entities)

        return [
            RiskBudget(
                entity_id=e["entity_id"],
                level=BudgetLevel(e["level"]),
                budget_pct=self.total_budget * (sharpes[e["entity_id"]] / total_s),
                var_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("var", 0.005),
                cvar_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("cvar", 0.008),
                max_drawdown_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("max_dd", 0.03),
            )
            for e in entities
        ]

    def _allocate_custom(
        self,
        entities: list[dict[str, Any]],
    ) -> list[RiskBudget]:
        """Custom budget allocation using entity-provided weights."""
        weights = {}
        for e in entities:
            w = e.get("weight", 1.0 / max(len(entities), 1))
            weights[e["entity_id"]] = w

        total_w = sum(weights.values())
        if total_w == 0:
            return self._allocate_equal(entities)

        return [
            RiskBudget(
                entity_id=e["entity_id"],
                level=BudgetLevel(e["level"]),
                budget_pct=self.total_budget * (weights[e["entity_id"]] / total_w),
                var_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("var", 0.005),
                cvar_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("cvar", 0.008),
                max_drawdown_limit=self.DEFAULT_LIMITS.get(BudgetLevel(e["level"]), {}).get("max_dd", 0.03),
            )
            for e in entities
        ]

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def check_budgets(
        self,
        allocation: Optional[BudgetAllocation] = None,
    ) -> dict[str, Any]:
        """Check budget status and generate warnings.

        Args:
            allocation: Specific allocation to check (default: latest).

        Returns:
            Dict with summary, warnings, and actions.
        """
        allocation = allocation or (self.history[-1] if self.history else None)
        if not allocation:
            return {"status": "no_data", "warnings": [], "actions": []}

        warnings = []
        actions = []

        for b in allocation.budgets:
            if b.status == BudgetStatus.EXCEEDED:
                warnings.append(
                    f"{b.entity_id} ({b.level.value}): risk budget EXCEEDED "
                    f"({b.utilization:.1%})"
                )
                actions.append(
                    {"entity": b.entity_id, "action": "reduce", "by_pct": b.utilization - 1.0}
                )
            elif b.status == BudgetStatus.NEAR_LIMIT:
                warnings.append(
                    f"{b.entity_id} ({b.level.value}): near limit "
                    f"({b.utilization:.1%})"
                )
                actions.append(
                    {"entity": b.entity_id, "action": "monitor", "utilization": b.utilization}
                )

        overall_status = (
            "critical" if any(b.is_exceeded for b in allocation.budgets)
            else "warning" if any(b.is_near_limit for b in allocation.budgets)
            else "healthy"
        )

        return {
            "overall_status": overall_status,
            "total_budget": allocation.total_risk_budget,
            "total_consumed": allocation.total_consumed,
            "unused_budget": allocation.unused_budget,
            "warnings": warnings,
            "actions": actions,
            "exceeded_count": len(allocation.exceeded_budgets),
            "near_limit_count": len(allocation.near_limit_budgets),
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_budget(
        self,
        entity_ids: list[str],
        level: BudgetLevel = BudgetLevel.POSITION,
    ) -> dict[str, Any]:
        """Quick risk budget allocation with defaults.

        Args:
            entity_ids: List of entity identifiers.
            level: Budget level for all entities.

        Returns:
            Dict with budget allocations and summary.
        """
        entities = [
            {"entity_id": eid, "level": level.value}
            for eid in entity_ids
        ]
        result = self.allocate(entities)
        return {
            "total_budget": result.total_risk_budget,
            "method": result.method.value,
            "budgets": {
                b.entity_id: {
                    "budget_pct": round(b.budget_pct, 4),
                    "consumed_pct": round(b.consumed_pct, 4),
                    "status": b.status.value,
                }
                for b in result.budgets
            },
            "unused_budget": round(result.unused_budget, 4),
        }

    def last_result(self) -> Optional[BudgetAllocation]:
        """Return the most recent budget allocation."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset budget history."""
        self.history.clear()
