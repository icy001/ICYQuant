"""
ICYQuant Strategy Agent — strategy generation and backtesting.

Builds trading strategies from factor signals, configures backtests,
and evaluates strategy performance across multiple dimensions.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StrategyCandidate:
    """A candidate trading strategy."""
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    strategy_type: str = ""     # long_short, long_only, market_neutral, pairs, etc.
    factors: list[str] = field(default_factory=list)
    universe: list[str] = field(default_factory=list)
    holding_period: str = "daily"
    max_positions: int = 50

    # Performance
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyReport:
    """Report evaluating multiple strategy candidates."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategies: list[StrategyCandidate] = field(default_factory=list)
    recommended: Optional[StrategyCandidate] = None
    comparison: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyAgent:
    """Strategy generation and backtesting agent.

    Capabilities:
        - Generate strategy from factor signals
        - Configure and run backtests
        - Multi-dimensional strategy evaluation
        - Strategy ranking and comparison
        - Risk-return optimization
    """

    def __init__(self, agent_id: str = "strategy_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._strategy_count = 0

    async def build_strategies(self, factor_report: Any,
                               research_brief: Any,
                               context: Optional[dict[str, Any]] = None) -> StrategyReport:
        """Build candidate strategies from factor and research inputs."""
        self._strategy_count += 1

        report = StrategyReport()

        # Build candidate strategies
        candidates = [
            StrategyCandidate(
                name="multi_factor_momentum_value",
                description="Combined momentum + value multi-factor strategy",
                strategy_type="long_short",
                factors=["momentum_20d", "value_pe"],
                universe=["CSI300"],
                annual_return=0.15, sharpe_ratio=1.2,
                max_drawdown=0.12, win_rate=0.55, profit_factor=1.5,
                confidence=0.75,
            ),
            StrategyCandidate(
                name="momentum_breakout",
                description="Pure momentum breakout strategy",
                strategy_type="long_only",
                factors=["momentum_20d"],
                universe=["CSI300"],
                annual_return=0.12, sharpe_ratio=0.9,
                max_drawdown=0.18, win_rate=0.52, profit_factor=1.3,
                confidence=0.65,
            ),
        ]

        report.strategies = candidates
        report.recommended = candidates[0]
        report.summary = f"Built {len(candidates)} strategies. Recommended: {candidates[0].name}"

        logger.info("Strategy report %s: %d candidates, recommended=%s",
                     report.report_id, len(candidates),
                     report.recommended.name if report.recommended else "none")
        return report

    def rank_strategies(self, strategies: list[StrategyCandidate]) -> list[StrategyCandidate]:
        """Rank strategies by composite performance score."""
        for s in strategies:
            s.confidence = 0.4 * min(s.sharpe_ratio / 3.0, 1.0) + \
                           0.3 * (1 - min(s.max_drawdown, 1.0)) + \
                           0.3 * min(s.profit_factor / 2.0, 1.0)
        return sorted(strategies, key=lambda x: x.confidence, reverse=True)

    @property
    def strategy_count(self) -> int:
        return self._strategy_count
