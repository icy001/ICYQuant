"""Allocation Manager — bridges all allocation sub-systems.

Acts as the facade coordinating: scoring, marginal analysis,
optimization, constraints, decisions, rebalancing, guards,
and feedback into a unified allocation management layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ManagerMode(str, Enum):
    """Allocation manager operating mode."""
    OBSERVE = "OBSERVE"
    RECOMMEND = "RECOMMEND"
    SEMI_AUTO = "SEMI_AUTO"
    FULL_AUTO = "FULL_AUTO"
    EMERGENCY = "EMERGENCY"


@dataclass
class AllocationProfile:
    """Unified profile aggregating all allocation dimensions."""
    strategy_id: str
    capital: float = 0.0
    weight: float = 0.0
    target_weight: float = 0.0
    alpha_score: float = 0.0
    risk_score: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    impact_score: float = 0.0
    stress_score: float = 0.0
    survival_score: float = 0.0
    composite_score: float = 0.0
    marginal_alpha: float = 0.0
    marginal_risk: float = 0.0
    marginal_cost: float = 0.0
    rank: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AllocationSummary:
    """Summary of the allocation state across all strategies."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_capital: float = 0.0
    deployed_capital: float = 0.0
    reserve_capital: float = 0.0
    buffer_capital: float = 0.0
    available_capital: float = 0.0
    profiles: List[AllocationProfile] = field(default_factory=list)
    top_strategy: str = ""
    top_score: float = 0.0
    mode: ManagerMode = ManagerMode.OBSERVE
    constraint_violations: List[str] = field(default_factory=list)
    pending_rebalances: int = 0
    last_update: Optional[datetime] = None

    @property
    def deployable_capital(self) -> float:
        return self.total_capital - self.reserve_capital - self.buffer_capital

    @property
    def deployment_ratio(self) -> float:
        if self.deployable_capital <= 0:
            return 0.0
        return self.deployed_capital / self.deployable_capital


class AllocationManager:
    """Unified allocation manager coordinating all sub-systems.

    Pulls together: scoring, marginal analysis, optimization,
    constraints, decisions, rebalancing, and feedback.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._mode = ManagerMode.OBSERVE
        self._profiles: Dict[str, AllocationProfile] = {}
        self._scorers: Dict[str, Any] = {}
        self._marginal_calculators: Dict[str, Any] = {}
        self._constraints: List[Any] = []
        self._guards: List[Any] = []
        self._last_summary: Optional[AllocationSummary] = None
        self._update_count = 0

    @property
    def mode(self) -> ManagerMode:
        return self._mode

    @property
    def last_summary(self) -> Optional[AllocationSummary]:
        return self._last_summary

    def set_mode(self, mode: ManagerMode) -> None:
        """Set manager operating mode."""
        self._mode = mode

    def register_scorer(self, name: str, scorer: Any) -> None:
        """Register a scoring component."""
        self._scorers[name] = scorer

    def register_marginal_calculator(self, name: str, calculator: Any) -> None:
        """Register a marginal analysis calculator."""
        self._marginal_calculators[name] = calculator

    def register_constraint(self, constraint: Any) -> None:
        """Register an allocation constraint."""
        self._constraints.append(constraint)

    def register_guard(self, guard: Any) -> None:
        """Register an allocation guard."""
        self._guards.append(guard)

    def create_profile(self, strategy_id: str, capital: float = 0.0,
                       weight: float = 0.0) -> AllocationProfile:
        """Create or get an allocation profile for a strategy."""
        if strategy_id not in self._profiles:
            self._profiles[strategy_id] = AllocationProfile(
                strategy_id=strategy_id,
                capital=capital,
                weight=weight,
            )
        return self._profiles[strategy_id]

    def update_profile(self, strategy_id: str, **kwargs) -> Optional[AllocationProfile]:
        """Update an allocation profile with new values."""
        profile = self._profiles.get(strategy_id)
        if not profile:
            return None
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.timestamp = datetime.utcnow()
        return profile

    def compute_composite_score(self, profile: AllocationProfile,
                                weights: Optional[Dict[str, float]] = None) -> float:
        """Compute composite allocation score from sub-scores.

        Default weights:
            alpha=0.25, risk=0.15, capacity=0.15, liquidity=0.12,
            impact=0.10, stress=0.12, survival=0.11
        """
        w = weights or {
            "alpha": 0.25, "risk": 0.15, "capacity": 0.15,
            "liquidity": 0.12, "impact": 0.10, "stress": 0.12,
            "survival": 0.11,
        }
        score = (
            w["alpha"] * profile.alpha_score +
            w["risk"] * profile.risk_score +
            w["capacity"] * profile.capacity_score +
            w["liquidity"] * profile.liquidity_score +
            w["impact"] * profile.impact_score +
            w["stress"] * profile.stress_score +
            w["survival"] * profile.survival_score
        )
        profile.composite_score = score
        return score

    def rank_strategies(self) -> List[Tuple[str, float]]:
        """Rank strategies by composite score descending."""
        ranked = [(pid, p.composite_score) for pid, p in self._profiles.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        for i, (pid, _) in enumerate(ranked):
            if pid in self._profiles:
                self._profiles[pid].rank = i + 1
        return ranked

    def check_constraints(self, profile: AllocationProfile) -> List[str]:
        """Check all registered constraints against a profile."""
        violations = []
        for constraint in self._constraints:
            try:
                result = constraint.check(profile)
                if hasattr(result, 'violations'):
                    violations.extend(result.violations)
                elif isinstance(result, list):
                    violations.extend(result)
            except Exception as e:
                violations.append(f"Constraint error [{constraint}]: {e}")
        return violations

    def summarize(self, total_capital: float, reserve: float,
                  buffer: float) -> AllocationSummary:
        """Generate a comprehensive allocation summary."""
        deployed = sum(p.capital for p in self._profiles.values())
        ranked = self.rank_strategies()

        top_strategy = ""
        top_score = 0.0
        if ranked:
            top_strategy = ranked[0][0]
            top_score = ranked[0][1]

        violations = []
        for profile in self._profiles.values():
            violations.extend(self.check_constraints(profile))

        summary = AllocationSummary(
            timestamp=datetime.utcnow(),
            total_capital=total_capital,
            deployed_capital=deployed,
            reserve_capital=reserve,
            buffer_capital=buffer,
            available_capital=total_capital - reserve - buffer - deployed,
            profiles=list(self._profiles.values()),
            top_strategy=top_strategy,
            top_score=top_score,
            mode=self._mode,
            constraint_violations=list(set(violations)),
            pending_rebalances=self._count_pending_rebalances(),
            last_update=datetime.utcnow(),
        )
        self._last_summary = summary
        self._update_count += 1
        return summary

    def _count_pending_rebalances(self) -> int:
        """Count profiles needing rebalance."""
        count = 0
        for p in self._profiles.values():
            if abs(p.target_weight - p.weight) > 0.001:
                count += 1
        return count

    def get_profile(self, strategy_id: str) -> Optional[AllocationProfile]:
        """Get a strategy's allocation profile."""
        return self._profiles.get(strategy_id)

    def get_all_profiles(self) -> Dict[str, AllocationProfile]:
        """Get all allocation profiles."""
        return dict(self._profiles)

    def clear_profiles(self) -> None:
        """Clear all profiles."""
        self._profiles.clear()
