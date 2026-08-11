"""
Decision Context — Unified context for all autonomous decisions.

Aggregates all relevant context from across the autonomous system
for a single decision evaluation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MarketSnapshot:
    """Market conditions at decision time."""
    timestamp: float = field(default_factory=time.time)
    regime: str = "unknown"
    volatility: float = 0.0
    trend: str = "neutral"
    liquidity_index: float = 0.0


@dataclass
class AlphaSnapshot:
    """Alpha state at decision time."""
    alpha_id: str = ""
    alpha_score: float = 0.0
    alpha_decay_half_life: float = 0.0
    confidence: float = 0.0


@dataclass
class StrategySnapshot:
    """Strategy state at decision time."""
    strategy_id: str = ""
    strategy_version: str = ""
    performance_sharpe: float = 0.0
    drawdown: float = 0.0
    allocation: float = 0.0


@dataclass
class PortfolioSnapshot:
    """Portfolio state at decision time."""
    portfolio_id: str = ""
    nav: float = 0.0
    var: float = 0.0
    expected_shortfall: float = 0.0
    concentration_top3: float = 0.0


@dataclass
class DecisionContext:
    """
    Comprehensive context for an autonomous decision.

    Aggregates market, research, alpha, strategy, portfolio, risk,
    execution, policy, permission, autonomy, budget, and system health
    snapshots into a single unified context.
    """
    trace_id: str = ""
    decision_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Domain snapshots
    market: Optional[MarketSnapshot] = None
    alpha: Optional[AlphaSnapshot] = None
    strategy: Optional[StrategySnapshot] = None
    portfolio: Optional[PortfolioSnapshot] = None

    # Control snapshots
    policy_context: dict = field(default_factory=dict)
    autonomy_level: int = 0
    permissions: list[str] = field(default_factory=list)
    budget_remaining: dict = field(default_factory=dict)
    system_health: dict = field(default_factory=dict)

    # Request
    action: str = ""
    requested_scope: str = ""
    entity_type: str = ""
    entity_id: str = ""

    def snapshot(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "market": self.market.__dict__ if self.market else None,
            "alpha": self.alpha.__dict__ if self.alpha else None,
            "strategy": self.strategy.__dict__ if self.strategy else None,
            "portfolio": self.portfolio.__dict__ if self.portfolio else None,
            "policy_context": self.policy_context,
            "autonomy_level": self.autonomy_level,
            "permissions": self.permissions,
            "budget_remaining": self.budget_remaining,
            "system_health": self.system_health,
            "action": self.action,
            "requested_scope": self.requested_scope,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
        }

    @classmethod
    def from_control_plane_context(cls, cp_context) -> "DecisionContext":
        """Convert a ControlPlaneContext into a DecisionContext."""
        return cls(
            trace_id=getattr(cp_context, "trace_id", ""),
            timestamp=getattr(cp_context, "timestamp", time.time()),
            market=MarketSnapshot(
                regime=cp_context.market_context.get("regime", "unknown")
                if cp_context.market_context else "unknown",
                volatility=cp_context.market_context.get("volatility", 0.0)
                if cp_context.market_context else 0.0,
            ),
            policy_context=cp_context.policy_context or {},
            autonomy_level=cp_context.autonomy_context.get("level", 0)
            if cp_context.autonomy_context else 0,
            action=getattr(cp_context, "action", ""),
            requested_scope=getattr(cp_context, "requested_scope", ""),
            entity_type=getattr(cp_context, "entity_type", ""),
            entity_id=getattr(cp_context, "entity_id", ""),
        )
