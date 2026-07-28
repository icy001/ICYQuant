"""Conflict Detection Engine – detects disagreement among agent decisions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .collector import DecisionPackage


@dataclass
class ConflictReport:
    has_conflict: bool
    unique_signals: int
    conflict_score: float
    details: Dict[str, Any] = field(default_factory=dict)


class ConflictDetectionEngine:
    """Detects and quantifies conflicts among decisions from multiple agents."""

    # Signal distance matrix: maps pairs to conflict weight
    SIGNAL_CONFLICT_WEIGHT = {
        ("BUY", "SELL"): 1.0,
        ("BUY", "STRONG_SELL"): 1.0,
        ("SELL", "STRONG_BUY"): 1.0,
        ("BUY", "HOLD"): 0.3,
        ("SELL", "HOLD"): 0.3,
        ("STRONG_BUY", "HOLD"): 0.5,
        ("STRONG_SELL", "HOLD"): 0.5,
    }

    def detect(self, decisions: List[DecisionPackage]) -> bool:
        """Return True if there is any signal disagreement.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            True if multiple unique signals exist.
        """
        if not decisions:
            return False
        signals = {d.signal for d in decisions}
        return len(signals) > 1

    def conflict_score(self, decisions: List[DecisionPackage]) -> float:
        """Compute a conflict score (0.0 = full agreement, 1.0 = max conflict).

        Considers both signal diversity and confidence-weighted disagreement.
        """
        if len(decisions) < 2:
            return 0.0

        signals = [d.signal for d in decisions]
        unique_signals = set(signals)

        # Signal diversity component
        diversity = (len(unique_signals) - 1) / max(len(decisions) - 1, 1)

        # Pairwise conflict component (confidence-weighted)
        pairwise_conflict = 0.0
        count = 0
        for i in range(len(decisions)):
            for j in range(i + 1, len(decisions)):
                pair = tuple(sorted([decisions[i].signal, decisions[j].signal]))
                weight = self.SIGNAL_CONFLICT_WEIGHT.get(pair, 0.0)
                if weight > 0:
                    avg_conf = (decisions[i].confidence + decisions[j].confidence) / 2
                    pairwise_conflict += weight * avg_conf
                    count += 1

        pair_component = pairwise_conflict / max(count, 1)

        return round((diversity * 0.4 + pair_component * 0.6), 4)

    def analyze(self, decisions: List[DecisionPackage]) -> ConflictReport:
        """Full conflict analysis.

        Returns:
            ConflictReport with has_conflict, unique_signals, conflict_score, details.
        """
        if not decisions:
            return ConflictReport(has_conflict=False, unique_signals=0, conflict_score=0.0)

        signals = {d.signal for d in decisions}
        score = self.conflict_score(decisions)

        signal_breakdown: Dict[str, int] = {}
        for d in decisions:
            signal_breakdown[d.signal] = signal_breakdown.get(d.signal, 0) + 1

        return ConflictReport(
            has_conflict=len(signals) > 1,
            unique_signals=len(signals),
            conflict_score=score,
            details={
                "signal_breakdown": signal_breakdown,
                "total_decisions": len(decisions),
                "severity": "high" if score > 0.7 else "medium" if score > 0.3 else "low",
            },
        )
