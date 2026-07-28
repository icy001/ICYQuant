"""Decision Memory – persistent knowledge base for decisions and outcomes."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DecisionMemory:
    """Stores final decisions, conflicts, confidence, and outcomes.

    Forms the Decision Knowledge Base for post-trade analysis and learning.
    """

    def __init__(self) -> None:
        self.history: List[Dict[str, Any]] = []

    def save(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Save a decision record.

        Args:
            decision: decision record dict.

        Returns:
            The saved record with timestamp.
        """
        if "timestamp" not in decision:
            decision["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.history.append(decision)
        return decision

    def save_with_outcome(
        self,
        signal: str,
        confidence: float,
        conflict_score: float = 0.0,
        outcome: Optional[str] = None,
        pnl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save a decision with eventual outcome for learning."""
        record = {
            "signal": signal,
            "confidence": confidence,
            "conflict_score": conflict_score,
            "outcome": outcome,
            "pnl": pnl,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.history.append(record)
        return record

    def query_by_outcome(self, outcome: str) -> List[Dict[str, Any]]:
        """Retrieve decisions by outcome (e.g. 'WIN', 'LOSS')."""
        return [d for d in self.history if d.get("outcome") == outcome]

    def query_high_confidence(self, threshold: float = 0.80) -> List[Dict[str, Any]]:
        """Retrieve decisions with confidence >= threshold."""
        return [d for d in self.history if d.get("confidence", 0) >= threshold]

    def query_high_conflict(self, threshold: float = 0.50) -> List[Dict[str, Any]]:
        """Retrieve decisions with high conflict score."""
        return [d for d in self.history if d.get("conflict_score", 0) >= threshold]

    def win_rate(self) -> Optional[float]:
        """Compute win rate from outcomes."""
        outcomes = [d.get("outcome") for d in self.history if d.get("outcome")]
        if not outcomes:
            return None
        wins = sum(1 for o in outcomes if o == "WIN")
        return wins / len(outcomes)

    @property
    def record_count(self) -> int:
        return len(self.history)

    def clear(self) -> None:
        self.history.clear()
