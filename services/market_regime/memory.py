"""Regime Memory – persist and query market regime history."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .regime import MarketRegime, RegimeTransition


@dataclass
class RegimeRecord:
    """A stored regime observation in memory."""

    record_id: str = ""
    regime_state: str = ""
    confidence: float = 0.0
    timestamp: Optional[str] = None

    # Sub-signals
    trend_signal: str = ""
    trend_strength: float = 0.0
    volatility_signal: str = ""
    volatility_level: float = 0.0
    macro_signal: str = ""

    # Strategy
    recommended_strategies: List[str] = field(default_factory=list)
    suggested_exposure: float = 1.0

    # Metadata
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "regime_state": self.regime_state,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "trend_signal": self.trend_signal,
            "trend_strength": self.trend_strength,
            "volatility_signal": self.volatility_signal,
            "volatility_level": self.volatility_level,
            "macro_signal": self.macro_signal,
            "recommended_strategies": self.recommended_strategies,
            "suggested_exposure": self.suggested_exposure,
            "tags": self.tags,
        }


class RegimeMemory:
    """Persistent memory for market regime observations and transitions.

    Stores:
    - Historical regime classifications
    - Regime transition records
    - Strategy performance per regime
    - Market transition patterns
    """

    def __init__(self):
        self._history: List[RegimeRecord] = []
        self._transitions: List[RegimeTransition] = []
        self._id_counter: int = 0

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def save(self, regime: MarketRegime) -> RegimeRecord:
        """Save a market regime observation to memory."""
        # Check for transition
        if self._history:
            last = self._history[-1]
            if last.regime_state != regime.state:
                transition = RegimeTransition(
                    from_state=last.regime_state,
                    to_state=regime.state,
                    timestamp=regime.timestamp,
                    confidence=regime.confidence,
                    trigger_factors=regime.evidence,
                )
                self._transitions.append(transition)

        record = RegimeRecord(
            record_id=self._next_id(),
            regime_state=regime.state,
            confidence=regime.confidence,
            timestamp=regime.timestamp.isoformat() if regime.timestamp else None,
            trend_signal=regime.trend_signal,
            trend_strength=regime.trend_strength,
            volatility_signal=regime.volatility_signal,
            volatility_level=regime.volatility_level,
            macro_signal=regime.macro_signal,
            recommended_strategies=regime.recommended_strategies,
            suggested_exposure=regime.suggested_exposure,
            tags=list(regime.tags),
        )

        self._history.append(record)
        return record

    def save_dict(self, item: dict) -> RegimeRecord:
        """Save a regime from a dict."""
        record = RegimeRecord(
            record_id=self._next_id(),
            regime_state=item.get("regime_state", item.get("state", "")),
            confidence=item.get("confidence", 0.0),
            timestamp=item.get("timestamp"),
            trend_signal=item.get("trend_signal", ""),
            volatility_signal=item.get("volatility_signal", ""),
            macro_signal=item.get("macro_signal", ""),
            tags=item.get("tags", []),
        )
        self._history.append(record)
        return record

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self) -> List[dict]:
        """Get all regime history as dicts."""
        return [r.to_dict() for r in self._history]

    def get_records(self) -> List[RegimeRecord]:
        """Get all regime records."""
        return list(self._history)

    def get_recent(self, n: int = 10) -> List[RegimeRecord]:
        """Get the most recent N regime records."""
        return self._history[-n:] if len(self._history) >= n else list(self._history)

    def get_latest(self) -> Optional[RegimeRecord]:
        """Get the most recent regime record."""
        return self._history[-1] if self._history else None

    def get_by_state(self, state: str) -> List[RegimeRecord]:
        """Query records by regime state."""
        return [r for r in self._history if r.regime_state == state]

    def get_transitions(self) -> List[RegimeTransition]:
        """Get all regime transitions."""
        return list(self._transitions)

    def get_transitions_between(self, from_state: str,
                                to_state: str) -> List[RegimeTransition]:
        """Get transitions from one state to another."""
        return [t for t in self._transitions
                if t.from_state == from_state and t.to_state == to_state]

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def regime_distribution(self) -> Dict[str, int]:
        """Get count of observations per regime state."""
        dist: Dict[str, int] = {}
        for r in self._history:
            dist[r.regime_state] = dist.get(r.regime_state, 0) + 1
        return dist

    def regime_duration(self, state: str) -> float:
        """Calculate average consecutive duration of a regime (in observations)."""
        runs = []
        current_run = 0
        for r in self._history:
            if r.regime_state == state:
                current_run += 1
            else:
                if current_run > 0:
                    runs.append(current_run)
                current_run = 0
        if current_run > 0:
            runs.append(current_run)

        if not runs:
            return 0.0
        return sum(runs) / len(runs)

    def transition_matrix(self) -> Dict[str, Dict[str, int]]:
        """Build a transition count matrix between regime states."""
        matrix: Dict[str, Dict[str, int]] = {}
        for i in range(1, len(self._history)):
            prev = self._history[i - 1].regime_state
            curr = self._history[i].regime_state
            if prev not in matrix:
                matrix[prev] = {}
            matrix[prev][curr] = matrix[prev].get(curr, 0) + 1
        return matrix

    def average_confidence(self, state: Optional[str] = None) -> float:
        """Get average confidence, optionally filtered by state."""
        records = self._history
        if state:
            records = [r for r in records if r.regime_state == state]
        if not records:
            return 0.0
        return round(sum(r.confidence for r in records) / len(records), 2)

    def summary(self) -> dict:
        """Get a summary of the regime memory."""
        total = len(self._history)
        if total == 0:
            return {"total_observations": 0}

        dist = self.regime_distribution()
        transitions = len(self._transitions)
        latest = self._history[-1]

        return {
            "total_observations": total,
            "total_transitions": transitions,
            "current_regime": latest.regime_state,
            "current_confidence": latest.confidence,
            "regime_distribution": dist,
            "avg_confidence": self.average_confidence(),
            "most_common_regime": max(dist, key=dist.get) if dist else "N/A",
        }

    def reset(self) -> None:
        """Clear all memory."""
        self._history.clear()
        self._transitions.clear()
        self._id_counter = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"REG-{self._id_counter:06d}"
