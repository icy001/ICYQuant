"""Portfolio Manager Service – high-level API for autonomous portfolio management."""

from typing import Dict, List, Optional

from .manager import PortfolioState, PortfolioProposal
from .allocation import AllocationEngine
from .strategy_selector import StrategySelector, Strategy
from .rebalance import RebalanceEngine, RebalanceResult
from .attribution import PerformanceAttribution, AttributionResult
from .committee import InvestmentCommittee, CommitteeResult
from .memory import PortfolioMemory, AllocationRecord


class PortfolioManagerService:
    """Unified service for AI-driven portfolio management.

    Integrates asset allocation, strategy selection, rebalancing,
    performance attribution, investment committee workflow, and
    portfolio memory into a single API.
    """

    def __init__(
        self,
        allocation: Optional[AllocationEngine] = None,
        selector: Optional[StrategySelector] = None,
        rebalance: Optional[RebalanceEngine] = None,
        attribution: Optional[PerformanceAttribution] = None,
        committee: Optional[InvestmentCommittee] = None,
        memory: Optional[PortfolioMemory] = None,
    ):
        self._allocation_engine = allocation or AllocationEngine()
        self._selector = selector or StrategySelector()
        self._rebalance_engine = rebalance or RebalanceEngine()
        self._attribution = attribution or PerformanceAttribution()
        self._committee = committee or InvestmentCommittee()
        self._memory = memory or PortfolioMemory()

    # ------------------------------------------------------------------
    # Asset Allocation
    # ------------------------------------------------------------------

    def allocate(
        self,
        assets: List[str],
        method: str = "equal",
        alpha_scores: Optional[Dict[str, float]] = None,
        risk_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Allocate capital across assets using the specified method."""
        return self._allocation_engine.allocate(
            assets=assets,
            method=method,
            alpha_scores=alpha_scores,
            risk_scores=risk_scores,
        )

    def optimize_allocation(
        self,
        assets: List[str],
        alpha_scores: Dict[str, float],
        risk_scores: Dict[str, float],
        alpha_weight: float = 0.5,
    ) -> Dict[str, float]:
        """Blended optimization: alpha + risk-adjusted allocation."""
        return self._allocation_engine.optimize(
            assets=assets,
            alpha_scores=alpha_scores,
            risk_scores=risk_scores,
            alpha_weight=alpha_weight,
        )

    # ------------------------------------------------------------------
    # Strategy Selection
    # ------------------------------------------------------------------

    def select_strategies(
        self,
        strategies: List[Strategy],
        market_regime: str = "normal",
    ) -> List[Strategy]:
        """Select the best strategy combination."""
        return self._selector.select(strategies, market_regime)

    def allocate_strategy_capital(
        self,
        selected: List[Strategy],
        total_capital: float,
    ) -> Dict[str, float]:
        """Allocate capital across selected strategies."""
        return self._selector.allocate_capital(selected, total_capital)

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        total_value: float = 1_000_000.0,
        force: bool = False,
    ) -> RebalanceResult:
        """Generate rebalance orders."""
        return self._rebalance_engine.rebalance(
            current_weights, target_weights, total_value, force,
        )

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        signal_change: bool = False,
        risk_increase: bool = False,
        regime_change: bool = False,
    ) -> bool:
        """Check if rebalancing should be triggered."""
        return self._rebalance_engine.should_rebalance(
            current_weights, target_weights,
            signal_change, risk_increase, regime_change,
        )

    # ------------------------------------------------------------------
    # Performance Attribution
    # ------------------------------------------------------------------

    def attribute_performance(
        self,
        total_return: float,
        market_return: float = 0.0,
        stock_contributions: Optional[Dict[str, float]] = None,
        factor_contributions: Optional[Dict[str, float]] = None,
        sector_contributions: Optional[Dict[str, float]] = None,
        period: str = "",
    ) -> AttributionResult:
        """Attribute portfolio returns to sources."""
        return self._attribution.analyze(
            total_return=total_return,
            market_return=market_return,
            stock_contributions=stock_contributions,
            factor_contributions=factor_contributions,
            sector_contributions=sector_contributions,
            period=period,
        )

    # ------------------------------------------------------------------
    # Investment Committee
    # ------------------------------------------------------------------

    def submit_proposal(
        self,
        portfolio_id: str,
        description: str,
        current_weights: Dict[str, float],
        proposed_weights: Dict[str, float],
        rationale: str = "",
        risk_score: float = 0.0,
    ) -> CommitteeResult:
        """Submit a portfolio proposal for committee review."""
        proposal = PortfolioProposal(
            portfolio_id=portfolio_id,
            proposal_id=f"PROP-{portfolio_id}-{len(self._memory.history()) + 1:04d}",
            description=description,
            current_weights=current_weights,
            proposed_weights=proposed_weights,
            rationale=rationale,
            risk_score=risk_score,
        )
        return self._committee.run_workflow(proposal)

    def approve_proposal(self, proposal: dict) -> dict:
        """Simple approval check (legacy interface)."""
        return self._committee.approve(proposal)

    # ------------------------------------------------------------------
    # Portfolio Memory
    # ------------------------------------------------------------------

    def record_allocation(
        self,
        portfolio_id: str,
        weights: Dict[str, float],
        decision_reason: str = "",
        market_regime: str = "",
        risk_level: str = "",
        returns_since: float = 0.0,
    ) -> AllocationRecord:
        """Record an allocation decision in portfolio memory."""
        record = AllocationRecord(
            portfolio_id=portfolio_id,
            weights=weights,
            decision_reason=decision_reason,
            market_regime=market_regime,
            risk_level=risk_level,
            returns_since=returns_since,
        )
        self._memory.save(record)
        return record

    def memory_history(self) -> List[AllocationRecord]:
        """Return full allocation history."""
        return self._memory.history()

    def memory_summary(self) -> dict:
        """Return performance summary across all allocations."""
        return self._memory.performance_summary()

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    def build_portfolio(
        self,
        portfolio_id: str,
        assets: List[str],
        objective: str = "growth",
        risk_level: str = "medium",
        method: str = "equal",
        alpha_scores: Optional[Dict[str, float]] = None,
        risk_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Build a portfolio end-to-end: allocate → construct weights."""
        weights = self.allocate(
            assets=assets,
            method=method,
            alpha_scores=alpha_scores,
            risk_scores=risk_scores,
        )

        # Record in memory
        self.record_allocation(
            portfolio_id=portfolio_id,
            weights=weights,
            decision_reason=f"Built {objective} portfolio via {method} allocation",
            risk_level=risk_level,
        )

        return weights
