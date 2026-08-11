"""
Capacity Policy — Configurable policies governing capacity allocation behavior.

Orchestrates the rules engine that determines how capacity decisions
are weighted, prioritized, and enforced across the portfolio.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .liquidity_regime import LiquidityRegime


class PolicyMode(str, Enum):
    NORMAL = "normal"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    LIQUIDITY_PRUDENT = "liquidity_prudent"
    COST_AWARE = "cost_aware"
    CUSTOM = "custom"


@dataclass
class PolicyRule:
    """A single capacity policy rule."""

    rule_id: str = field(default_factory=lambda: f"CPR-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""

    # Rule activation
    priority: int = 0  # lower = applied first
    is_enabled: bool = True

    # Conditions
    min_participation_rate: float = 0.0
    max_participation_rate: float = 1.0
    max_impact_bps: float = float("inf")
    min_liquidity_score: float = 0.0
    applicable_regimes: List[str] = field(default_factory=list)

    # Actions
    auto_resize: bool = True
    auto_split: bool = False
    auto_defer: bool = False
    resize_factor: float = 0.90
    max_splits: int = 5
    defer_seconds: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "max_participation_rate": self.max_participation_rate,
            "max_impact_bps": self.max_impact_bps,
            "min_liquidity_score": self.min_liquidity_score,
            "auto_resize": self.auto_resize,
            "auto_split": self.auto_split,
        }


class CapacityPolicy:
    """Collection of capacity rules structured as a policy.

    Different policy modes (NORMAL, CONSERVATIVE, AGGRESSIVE) configure
    different rule sets that govern capacity decision-making.
    """

    def __init__(self, mode: PolicyMode = PolicyMode.NORMAL):
        self.mode: PolicyMode = mode
        self._rules: List[PolicyRule] = []
        self._global_config: Dict[str, Any] = {}
        self._initialize_mode(mode)

    def _initialize_mode(self, mode: PolicyMode) -> None:
        """Set up default rules for the selected policy mode."""
        if mode == PolicyMode.NORMAL:
            self._init_normal()
        elif mode == PolicyMode.CONSERVATIVE:
            self._init_conservative()
        elif mode == PolicyMode.AGGRESSIVE:
            self._init_aggressive()
        elif mode == PolicyMode.LIQUIDITY_PRUDENT:
            self._init_liquidity_prudent()
        elif mode == PolicyMode.COST_AWARE:
            self._init_cost_aware()

    # ── Mode Initializers ─────────────────────────────────────────

    def _init_normal(self) -> None:
        """Standard balanced policy."""
        self._rules = [
            PolicyRule(
                name="Standard Participation",
                description="10% participation cap, 15bps impact budget",
                priority=0,
                max_participation_rate=0.10,
                max_impact_bps=15.0,
                min_liquidity_score=30.0,
            ),
            PolicyRule(
                name="Large Order Splitting",
                description="Auto-split orders > 50% of daily capacity",
                priority=1,
                auto_split=True,
                max_splits=5,
            ),
            PolicyRule(
                name="Low Liquidity Deferral",
                description="Defer when liquidity score < 30",
                priority=2,
                min_liquidity_score=30.0,
                auto_defer=True,
                defer_seconds=300,
            ),
            PolicyRule(
                name="Crisis Override",
                description="Strict limits during crisis regime",
                priority=0,
                max_participation_rate=0.01,
                max_impact_bps=5.0,
                applicable_regimes=[LiquidityRegime.CRISIS.value],
                auto_resize=True,
                resize_factor=0.30,
            ),
        ]

    def _init_conservative(self) -> None:
        """Risk-averse policy with tighter limits."""
        self._rules = [
            PolicyRule(
                name="Conservative Participation",
                description="5% participation cap, 10bps impact budget",
                priority=0,
                max_participation_rate=0.05,
                max_impact_bps=10.0,
                min_liquidity_score=40.0,
                auto_resize=True,
            ),
            PolicyRule(
                name="Mandatory Splitting",
                description="Split orders > 20% of daily capacity",
                priority=1,
                auto_split=True,
                max_splits=8,
            ),
            PolicyRule(
                name="Stressed Deferral",
                description="Defer when liquidity score < 40",
                priority=2,
                min_liquidity_score=40.0,
                auto_defer=True,
                defer_seconds=600,
            ),
            PolicyRule(
                name="Crisis Freeze",
                description="Reject all orders in crisis",
                priority=0,
                max_participation_rate=0.0,
                applicable_regimes=[LiquidityRegime.CRISIS.value],
                auto_resize=False,
            ),
        ]

    def _init_aggressive(self) -> None:
        """Performance-seeking policy with wider limits."""
        self._rules = [
            PolicyRule(
                name="Aggressive Participation",
                description="15% participation cap, 25bps impact budget",
                priority=0,
                max_participation_rate=0.15,
                max_impact_bps=25.0,
                min_liquidity_score=15.0,
            ),
            PolicyRule(
                name="Minimum Splitting",
                description="Only split if absolutely necessary",
                priority=1,
                auto_split=True,
                max_splits=3,
            ),
            PolicyRule(
                name="Low Liquidity Warning",
                description="Defer only at very low liquidity (score < 15)",
                priority=2,
                min_liquidity_score=15.0,
                auto_defer=True,
                defer_seconds=120,
            ),
        ]

    def _init_liquidity_prudent(self) -> None:
        """Optimizes for liquidity availability above all else."""
        self._rules = [
            PolicyRule(
                name="Participation Adaptive",
                description="Dynamic participation based on liquidity score",
                priority=0,
                max_participation_rate=0.08,
                max_impact_bps=10.0,
                min_liquidity_score=50.0,
                auto_resize=True,
            ),
            PolicyRule(
                name="Liquidity-Driven Splitting",
                description="Split aggressively based on depth",
                priority=1,
                auto_split=True,
                max_splits=10,
            ),
            PolicyRule(
                name="Strict Deferral",
                description="Defer quickly at first sign of stress",
                priority=2,
                min_liquidity_score=50.0,
                auto_defer=True,
                defer_seconds=900,
            ),
        ]

    def _init_cost_aware(self) -> None:
        """Minimizes transaction costs and market impact."""
        self._rules = [
            PolicyRule(
                name="Cost-Optimized Participation",
                description="5% participation, 8bps impact budget",
                priority=0,
                max_participation_rate=0.05,
                max_impact_bps=8.0,
                min_liquidity_score=35.0,
                auto_resize=True,
                resize_factor=0.80,
            ),
            PolicyRule(
                name="TWAP/VWAP Splitting",
                description="Split into time-weighted slices",
                priority=1,
                auto_split=True,
                max_splits=12,
            ),
            PolicyRule(
                name="Spread-Aware Deferral",
                description="Defer when spreads are unfavorable",
                priority=2,
                min_liquidity_score=35.0,
                auto_defer=True,
                defer_seconds=600,
            ),
        ]

    # ── Rule Management ───────────────────────────────────────────

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def enable_rule(self, rule_id: str) -> None:
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.is_enabled = True

    def disable_rule(self, rule_id: str) -> None:
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.is_enabled = False

    # ── Rule Evaluation ───────────────────────────────────────────

    def active_rules(self) -> List[PolicyRule]:
        """Return enabled rules sorted by priority."""
        return [r for r in self._rules if r.is_enabled]

    def get_participation_limit(self,
                                 regime: Optional[str] = None,
                                 liquidity_score: float = 100.0) -> float:
        """Most restrictive participation limit among applicable rules."""
        limit = 1.0
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.max_participation_rate < limit:
                limit = rule.max_participation_rate
        return limit

    def get_impact_limit(self,
                          regime: Optional[str] = None,
                          liquidity_score: float = 100.0) -> float:
        """Most restrictive impact budget among applicable rules."""
        limit = float("inf")
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.max_impact_bps < limit:
                limit = rule.max_impact_bps
        return limit

    def should_resize(self,
                       regime: Optional[str] = None,
                       liquidity_score: float = 100.0) -> bool:
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.auto_resize:
                return True
        return False

    def should_split(self,
                      regime: Optional[str] = None,
                      liquidity_score: float = 100.0) -> bool:
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.auto_split:
                return True
        return False

    def should_defer(self,
                      regime: Optional[str] = None,
                      liquidity_score: float = 100.0) -> Tuple[bool, int]:
        """Returns (should_defer, defer_seconds)."""
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.auto_defer:
                return True, rule.defer_seconds
        return False, 0

    def get_split_params(self,
                          regime: Optional[str] = None,
                          liquidity_score: float = 100.0) -> Tuple[int, float]:
        """Returns (max_splits, resize_factor)."""
        max_splits = 1
        resize_factor = 1.0
        for rule in self.active_rules():
            if not self._rule_applies(rule, regime, liquidity_score):
                continue
            if rule.auto_split:
                max_splits = max(max_splits, rule.max_splits)
            if rule.auto_resize:
                resize_factor = min(resize_factor, rule.resize_factor)
        return max_splits, resize_factor

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _rule_applies(rule: PolicyRule,
                       regime: Optional[str],
                       liquidity_score: float) -> bool:
        if rule.applicable_regimes:
            if regime is None or regime not in rule.applicable_regimes:
                return False
        if liquidity_score < rule.min_liquidity_score - 1e-6:
            return False
        return True

    # ── Global Config ─────────────────────────────────────────────

    def set_config(self, key: str, value: Any) -> None:
        self._global_config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._global_config.get(key, default)

    # ── Mode Switching ────────────────────────────────────────────

    def switch_mode(self, mode: PolicyMode) -> None:
        """Switch the policy mode and reinitialize rules."""
        self.mode = mode
        self._initialize_mode(mode)

    # ── Queries ───────────────────────────────────────────────────

    def rule_count(self) -> int:
        return len(self._rules)

    def active_count(self) -> int:
        return len(self.active_rules())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "total_rules": self.rule_count(),
            "active_rules": self.active_count(),
            "participation_limit": self.get_participation_limit(),
            "impact_limit": self.get_impact_limit(),
            "auto_resize": self.should_resize(),
            "auto_split": self.should_split(),
            "rules": [r.to_dict() for r in self._rules],
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "active_rules": self.active_count(),
            "participation_limit": round(self.get_participation_limit(), 4),
            "impact_limit_bps": self.get_impact_limit(),
            "features": {
                "auto_resize": self.should_resize(),
                "auto_split": self.should_split(),
                "auto_defer": self.should_defer()[0],
            },
        }
