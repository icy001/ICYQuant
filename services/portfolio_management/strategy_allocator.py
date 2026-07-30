"""Strategy Allocator — strategy-level allocation within portfolios."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    ALPHA_LONG = "alpha_long"
    ALPHA_SHORT = "alpha_short"
    MARKET_NEUTRAL = "market_neutral"
    STAT_ARBITRAGE = "stat_arbitrage"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    EVENT_DRIVEN = "event_driven"
    MACRO = "macro"
    CTA_TREND = "cta_trend"
    CTA_MEAN_REVERSION = "cta_mean_reversion"
    VOLATILITY = "volatility"
    OPTIONS = "options"
    AI_DRIVEN = "ai_driven"
    CUSTOM = "custom"


class StrategyRiskLevel(Enum):
    ULTRA_LOW = "ultra_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA_HIGH = "ultra_high"


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""

    name: str = ""
    strategy_type: StrategyType = StrategyType.ALPHA_LONG
    risk_level: StrategyRiskLevel = StrategyRiskLevel.MEDIUM
    expected_return_annual: float = 0.15
    expected_volatility: float = 0.20
    expected_sharpe: float = 0.75
    max_drawdown_limit: float = 0.25
    correlation_to_benchmark: float = 0.5
    min_capital: float = 1_000_000
    max_capacity: float = 500_000_000
    turnover_annual: float = 3.0  # times per year
    holding_period_days: float = 60
    asset_class: str = "equity"
    region: str = "cn"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyCapacity:
    """Capacity analysis for a strategy."""

    strategy_id: str = ""
    current_allocation: float = 0.0
    max_capacity: float = 0.0
    utilization_pct: float = 0.0
    marginal_impact_bps: float = 0.0  # bp impact per additional 1M
    optimal_range: tuple = (0.0, 0.0)
    last_updated: float = field(default_factory=time.time)

    @property
    def has_capacity(self) -> bool:
        return self.current_allocation < self.max_capacity

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.max_capacity - self.current_allocation)


@dataclass
class StrategyAllocation:
    """Allocation to a specific strategy."""

    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    portfolio_id: str = ""
    strategy_id: str = ""
    config: StrategyConfig = field(default_factory=StrategyConfig)
    allocated_capital: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0
    performance_score: float = 0.0
    risk_contribution: float = 0.0
    active: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def drift(self) -> float:
        return abs(self.current_weight - self.target_weight)


class StrategyAllocator:
    """Manages strategy-level allocation within portfolios.

    Handles:
    - Strategy registration and configuration
    - Weight allocation across strategies
    - Capacity management
    - Performance-based adjustments
    """

    def __init__(self):
        self._strategies: Dict[str, StrategyConfig] = {}
        self._allocations: Dict[str, StrategyAllocation] = {}
        self._capacities: Dict[str, StrategyCapacity] = {}

    def register_strategy(self, config: StrategyConfig) -> str:
        strategy_id = str(uuid.uuid4())[:8]
        self._strategies[strategy_id] = config
        self._capacities[strategy_id] = StrategyCapacity(
            strategy_id=strategy_id,
            max_capacity=config.max_capacity,
            optimal_range=(config.min_capital, config.max_capacity * 0.8),
        )
        return strategy_id

    def allocate(
        self,
        portfolio_id: str,
        strategy_ids: List[str],
        total_capital: float,
        method: str = "equal_weight",
    ) -> List[StrategyAllocation]:
        """Allocate capital across strategies."""
        valid_strategies = [s for s in strategy_ids if s in self._strategies]
        if not valid_strategies:
            return []

        allocations = []
        if method == "risk_parity":
            weights = self._compute_risk_parity_weights(valid_strategies)
        elif method == "performance_weighted":
            weights = self._compute_performance_weights(valid_strategies)
        else:
            # Equal weight
            w = 1.0 / len(valid_strategies)
            weights = {s: w for s in valid_strategies}

        for sid in valid_strategies:
            config = self._strategies[sid]
            capacity = self._capacities[sid]
            target_weight = weights.get(sid, 0.0)
            capital = total_capital * target_weight

            # Respect capacity limits
            if capital > capacity.remaining_capacity:
                capital = capacity.remaining_capacity
                target_weight = capital / total_capital if total_capital > 0 else 0.0

            allocation = StrategyAllocation(
                portfolio_id=portfolio_id,
                strategy_id=sid,
                config=config,
                allocated_capital=capital,
                target_weight=target_weight,
                current_weight=target_weight,
            )
            self._allocations[allocation.allocation_id] = allocation
            capacity.current_allocation += capital

            allocations.append(allocation)

        return allocations

    def _compute_risk_parity_weights(self, strategy_ids: List[str]) -> Dict[str, float]:
        """Compute risk parity weights based on strategy volatilities."""
        vols = []
        for sid in strategy_ids:
            config = self._strategies.get(sid)
            vol = config.expected_volatility if config else 0.20
            vols.append(vol)

        inv_vols = [1.0 / max(v, 0.001) for v in vols]
        total_inv = sum(inv_vols)
        return {
            sid: inv / total_inv for sid, inv in zip(strategy_ids, inv_vols)
        }

    def _compute_performance_weights(self, strategy_ids: List[str]) -> Dict[str, float]:
        """Compute weights based on recent performance scores."""
        scores = []
        for sid in strategy_ids:
            allocs = [
                a for a in self._allocations.values()
                if a.strategy_id == sid and a.performance_score > 0
            ]
            score = sum(a.performance_score for a in allocs) / max(len(allocs), 1)
            scores.append(max(score, 0.1))  # floor at 0.1

        total = sum(scores)
        return {
            sid: s / total for sid, s in zip(strategy_ids, scores)
        } if total > 0 else {s: 1.0 / len(strategy_ids) for s in strategy_ids}

    def update_performance(
        self, allocation_id: str, performance_score: float
    ) -> Optional[StrategyAllocation]:
        alloc = self._allocations.get(allocation_id)
        if alloc:
            alloc.performance_score = performance_score
            alloc.updated_at = time.time()
        return alloc

    def get_strategy(self, strategy_id: str) -> Optional[StrategyConfig]:
        return self._strategies.get(strategy_id)

    def get_allocations_for_portfolio(self, portfolio_id: str) -> List[StrategyAllocation]:
        return [a for a in self._allocations.values() if a.portfolio_id == portfolio_id]

    def get_capacity(self, strategy_id: str) -> Optional[StrategyCapacity]:
        return self._capacities.get(strategy_id)

    def get_summary(self) -> Dict[str, Any]:
        total_allocated = sum(a.allocated_capital for a in self._allocations.values())
        total_strategies = len(self._strategies)
        active_allocations = sum(1 for a in self._allocations.values() if a.active)

        by_type: Dict[str, int] = {}
        for config in self._strategies.values():
            t = config.strategy_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_strategies": total_strategies,
            "active_allocations": active_allocations,
            "total_allocated_capital": total_allocated,
            "strategies_by_type": by_type,
        }
