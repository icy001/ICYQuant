"""Trading Memory – record trade history and decisions for long-term learning."""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from datetime import datetime


@dataclass
class MemoryRecord:
    """A single record in the trading memory.

    Captures the trade, decision context, market environment, and outcome
    for later analysis and pattern recognition.
    """

    trade_id: str
    symbol: str
    action: str
    decision_reason: str
    market_environment: Dict[str, Any] = field(default_factory=dict)
    outcome: str = ""  # "win", "loss", "breakeven"
    pnl_pct: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "action": self.action,
            "decision_reason": self.decision_reason,
            "market_environment": self.market_environment,
            "outcome": self.outcome,
            "pnl_pct": self.pnl_pct,
            "timestamp": self.timestamp,
        }


class TradingMemory:
    """Persistent trading memory for recording and querying trade history.

    Supports saving individual records, retrieving full history, and
    filtering by symbol, outcome, or time range.
    """

    def __init__(self):
        self.records: List[MemoryRecord] = []

    def save(self, item: MemoryRecord) -> None:
        """Store a memory record."""
        self.records.append(item)

    def history(self) -> List[MemoryRecord]:
        """Return all memory records in insertion order."""
        return list(self.records)

    def by_symbol(self, symbol: str) -> List[MemoryRecord]:
        """Return records filtered by symbol."""
        return [r for r in self.records if r.symbol == symbol]

    def by_outcome(self, outcome: str) -> List[MemoryRecord]:
        """Return records filtered by outcome (win/loss/breakeven)."""
        return [r for r in self.records if r.outcome == outcome]

    def win_rate(self) -> float:
        """Calculate overall win rate from stored records."""
        total = len(self.records)
        if total == 0:
            return 0.0
        wins = sum(1 for r in self.records if r.outcome == "win")
        return wins / total

    def recent(self, n: int = 10) -> List[MemoryRecord]:
        """Return the n most recent records."""
        return self.records[-n:]

    def clear(self) -> None:
        """Clear all records."""
        self.records.clear()
