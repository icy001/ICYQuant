"""Portfolio Manager Model – core portfolio state and configuration."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PortfolioState:
    """Represents the current state of a managed portfolio.

    Captures holdings, target weights, cash position, constraints,
    and the current market regime context.
    """

    portfolio_id: str
    objective: str  # e.g. "growth", "income", "balanced", "hedge"
    risk_level: str  # "low", "medium", "high"

    # Current allocation: symbol -> weight (sum to 1.0)
    holdings: Dict[str, float] = field(default_factory=dict)

    # Target allocation for rebalancing
    target_weights: Dict[str, float] = field(default_factory=dict)

    # Cash as fraction of portfolio
    cash: float = 0.0

    # Constraints
    max_single_position: float = 0.30
    max_sector_exposure: float = 0.50
    min_cash: float = 0.05
    turnover_limit: float = 0.30

    # Metadata
    total_value: float = 0.0
    market_regime: str = "normal"
    rebalance_triggered: bool = False

    def total_exposure(self) -> float:
        """Return total invested exposure (1.0 - cash)."""
        return 1.0 - self.cash

    def is_valid(self) -> bool:
        """Check if portfolio respects all constraints."""
        # Single position limit
        for symbol, weight in self.holdings.items():
            if weight > self.max_single_position:
                return False
        # Cash floor
        if self.cash < self.min_cash and self.cash < 0:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "objective": self.objective,
            "risk_level": self.risk_level,
            "holdings": self.holdings,
            "target_weights": self.target_weights,
            "cash": self.cash,
            "max_single_position": self.max_single_position,
            "max_sector_exposure": self.max_sector_exposure,
            "min_cash": self.min_cash,
            "total_value": self.total_value,
            "market_regime": self.market_regime,
        }


@dataclass
class PortfolioProposal:
    """A proposed portfolio change submitted for approval.

    Contains the rationale, proposed target weights, impact analysis,
    and tracks approval workflow status.
    """

    portfolio_id: str
    proposal_id: str
    description: str
    current_weights: Dict[str, float] = field(default_factory=dict)
    proposed_weights: Dict[str, float] = field(default_factory=dict)
    expected_impact: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    status: str = "draft"  # draft, submitted, approved, rejected, executed
    approved_by: str = ""
    risk_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "proposal_id": self.proposal_id,
            "description": self.description,
            "current_weights": self.current_weights,
            "proposed_weights": self.proposed_weights,
            "expected_impact": self.expected_impact,
            "rationale": self.rationale,
            "status": self.status,
            "risk_score": self.risk_score,
        }
