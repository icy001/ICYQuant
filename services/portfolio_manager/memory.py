"""Portfolio Memory – record allocation history and decisions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class AllocationRecord:
    """A single historical allocation snapshot.

    Captures the portfolio state, the decision context, market
    environment, and the outcome of the allocation decision.
    """

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    portfolio_id: str = ""
    weights: Dict[str, float] = field(default_factory=dict)
    decision_reason: str = ""
    market_regime: str = ""
    risk_level: str = ""
    returns_since: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "portfolio_id": self.portfolio_id,
            "weights": self.weights,
            "decision_reason": self.decision_reason,
            "market_regime": self.market_regime,
            "risk_level": self.risk_level,
            "returns_since": self.returns_since,
            "notes": self.notes,
        }


class PortfolioMemory:
    """Persistent portfolio management experience store.

    Records historical allocations, decision rationale, market context,
    and performance outcomes for long-term learning and review.
    """

    def __init__(self):
        self.records: List[AllocationRecord] = []

    def save(self, item: AllocationRecord) -> None:
        """Store an allocation record."""
        self.records.append(item)

    def history(self) -> List[AllocationRecord]:
        """Return all records in chronological order."""
        return list(self.records)

    def by_portfolio(self, portfolio_id: str) -> List[AllocationRecord]:
        """Return records for a specific portfolio."""
        return [r for r in self.records if r.portfolio_id == portfolio_id]

    def by_regime(self, regime: str) -> List[AllocationRecord]:
        """Return records from a specific market regime."""
        return [r for r in self.records if r.market_regime == regime]

    def recent(self, n: int = 10) -> List[AllocationRecord]:
        """Return the n most recent records."""
        return self.records[-n:]

    def performance_summary(self) -> dict:
        """Summarize performance across all recorded periods."""
        if not self.records:
            return {"total_records": 0, "avg_return": 0.0}

        returns = [r.returns_since for r in self.records if r.returns_since != 0]
        if not returns:
            return {"total_records": len(self.records), "avg_return": 0.0}

        return {
            "total_records": len(self.records),
            "avg_return": sum(returns) / len(returns),
            "max_return": max(returns),
            "min_return": min(returns),
        }

    def clear(self) -> None:
        """Clear all records."""
        self.records.clear()
