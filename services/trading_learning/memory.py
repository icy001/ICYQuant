"""Learning Memory – persistent store for trading experience and lessons."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class LearningRecord:
    """A single learning record capturing trade experience."""

    record_id: str
    trade_id: str
    symbol: str = ""
    outcome: str = ""  # "win", "loss", "breakeven"

    # Analysis
    quality_score: float = 0.0
    mistakes: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)

    # Lessons
    lesson: str = ""
    tags: List[str] = field(default_factory=list)

    # Context
    strategy_id: str = ""
    market_regime: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "outcome": self.outcome,
            "quality_score": self.quality_score,
            "mistakes": self.mistakes,
            "strengths": self.strengths,
            "lesson": self.lesson,
            "tags": self.tags,
            "strategy_id": self.strategy_id,
            "market_regime": self.market_regime,
            "timestamp": self.timestamp,
        }


class LearningMemory:
    """Stores and retrieves trade learning records.

    Builds a quant experience database that enables:
    - Pattern recognition across trades
    - Strategy performance trending
    - Market regime performance analysis
    - Cumulative learning for model improvement
    """

    def __init__(self):
        self.records: List[LearningRecord] = []

    def store(self, item: LearningRecord) -> None:
        """Store a learning record."""
        self.records.append(item)

    def store_trade_result(
        self,
        trade: TradeResult,
        quality_score: float = 0.0,
        mistakes: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        lesson: str = "",
        tags: Optional[List[str]] = None,
    ) -> LearningRecord:
        """Create and store a learning record from a trade result."""
        record = LearningRecord(
            record_id=f"LR-{len(self.records) + 1:04d}",
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            outcome=trade.outcome,
            quality_score=quality_score,
            mistakes=mistakes or [],
            strengths=strengths or [],
            lesson=lesson,
            tags=tags or [],
            strategy_id=trade.strategy_id,
            market_regime=trade.market_regime,
        )
        self.store(record)
        return record

    def query_by_symbol(self, symbol: str) -> List[LearningRecord]:
        """Find all learning records for a symbol."""
        return [r for r in self.records if r.symbol == symbol]

    def query_by_strategy(self, strategy_id: str) -> List[LearningRecord]:
        """Find all learning records for a strategy."""
        return [r for r in self.records if r.strategy_id == strategy_id]

    def query_by_outcome(self, outcome: str) -> List[LearningRecord]:
        """Find all learning records by outcome (win/loss/breakeven)."""
        return [r for r in self.records if r.outcome == outcome]

    def query_by_market_regime(self, regime: str) -> List[LearningRecord]:
        """Find all learning records for a market regime."""
        return [r for r in self.records if r.market_regime == regime]

    def query_by_tag(self, tag: str) -> List[LearningRecord]:
        """Find all learning records with a specific tag."""
        return [r for r in self.records if tag in r.tags]

    def get_all(self) -> List[LearningRecord]:
        """Return all stored learning records."""
        return list(self.records)

    def win_rate_by_symbol(self, symbol: str) -> dict:
        """Compute win rate for a given symbol."""
        records = self.query_by_symbol(symbol)
        if not records:
            return {"symbol": symbol, "total": 0, "win_rate": 0.0}
        wins = sum(1 for r in records if r.outcome == "win")
        return {
            "symbol": symbol,
            "total": len(records),
            "wins": wins,
            "win_rate": round(wins / len(records), 3),
        }

    def win_rate_by_regime(self) -> Dict[str, dict]:
        """Compute win rate by market regime."""
        regimes: Dict[str, List[str]] = {}
        for r in self.records:
            regimes.setdefault(r.market_regime, []).append(r.outcome)

        result = {}
        for regime, outcomes in regimes.items():
            wins = sum(1 for o in outcomes if o == "win")
            result[regime] = {
                "total": len(outcomes),
                "wins": wins,
                "win_rate": round(wins / len(outcomes), 3),
            }
        return result

    def top_mistakes(self, limit: int = 5) -> List[dict]:
        """Return the most common mistakes across all records."""
        counter: Dict[str, int] = {}
        for r in self.records:
            for m in r.mistakes:
                if m != "none":
                    counter[m] = counter.get(m, 0) + 1
        sorted_mistakes = sorted(counter.items(), key=lambda x: x[1], reverse=True)
        return [{"mistake": m, "count": c} for m, c in sorted_mistakes[:limit]]

    def summary(self) -> dict:
        """Generate a summary of the learning memory."""
        if not self.records:
            return {"total_records": 0, "total_trades": 0,
                    "win_rate": 0.0, "avg_quality_score": 0.0}

        wins = sum(1 for r in self.records if r.outcome == "win")
        avg_score = sum(r.quality_score for r in self.records) / len(self.records)
        unique_symbols = len(set(r.symbol for r in self.records))
        unique_strategies = len(set(r.strategy_id for r in self.records
                                    if r.strategy_id))

        return {
            "total_records": len(self.records),
            "total_trades": len(self.records),
            "wins": wins,
            "losses": len(self.records) - wins,
            "win_rate": round(wins / len(self.records), 3),
            "avg_quality_score": round(avg_score, 1),
            "unique_symbols": unique_symbols,
            "unique_strategies": unique_strategies,
        }

    def clear(self) -> None:
        """Clear all records."""
        self.records.clear()
