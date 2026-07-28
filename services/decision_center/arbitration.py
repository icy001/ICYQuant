"""Decision Arbitration Engine – resolves conflicts via priority-based selection."""

from typing import Dict, List, Optional

from .collector import DecisionPackage
from .conflict import ConflictDetectionEngine, ConflictReport


class DecisionArbitrationEngine:
    """Arbitrates among conflicting decisions using priority-based resolution.

    Priority order (highest to lowest):
        risk > macro > strategy > portfolio > sentiment > execution > simulation
    """

    DEFAULT_PRIORITY = [
        "risk",
        "macro",
        "strategy",
        "portfolio",
        "sentiment",
        "execution",
        "simulation",
    ]

    def __init__(
        self,
        priorities: Optional[List[str]] = None,
        conflict_engine: Optional[ConflictDetectionEngine] = None,
    ) -> None:
        self.priorities = priorities or list(self.DEFAULT_PRIORITY)
        self._priority_map = {s: i for i, s in enumerate(self.priorities)}
        self.conflict_engine = conflict_engine or ConflictDetectionEngine()

    def select(self, decisions: List[DecisionPackage]) -> Optional[DecisionPackage]:
        """Select the highest-priority decision.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            The winning DecisionPackage, or None if empty.
        """
        if not decisions:
            return None

        # Sort by priority rank (lower index = higher priority), then by confidence
        sorted_decisions = sorted(
            decisions,
            key=lambda d: (
                self._priority_map.get(d.source, len(self.priorities)),
                -d.confidence,
            ),
        )
        return sorted_decisions[0]

    def select_top_k(
        self,
        decisions: List[DecisionPackage],
        k: int = 3,
    ) -> List[DecisionPackage]:
        """Return top-k decisions by priority."""
        if not decisions:
            return []
        sorted_decisions = sorted(
            decisions,
            key=lambda d: (
                self._priority_map.get(d.source, len(self.priorities)),
                -d.confidence,
            ),
        )
        return sorted_decisions[:k]

    def arbitrate(self, decisions: List[DecisionPackage]) -> Dict:
        """Full arbitration: detect conflict, select winner, return report.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            Dict with winner, conflict_report, alternatives, rationale.
        """
        if not decisions:
            return {
                "winner": None,
                "conflict_report": ConflictReport(
                    has_conflict=False, unique_signals=0, conflict_score=0.0
                ),
                "alternatives": [],
                "rationale": "No decisions provided.",
            }

        conflict = self.conflict_engine.analyze(decisions)
        winner = self.select(decisions)
        alternatives = [d for d in decisions if d.signal != winner.signal] if winner else []

        if conflict.has_conflict:
            rationale = (
                f"Conflict detected (score={conflict.conflict_score}). "
                f"Arbitrated to '{winner.signal}' from '{winner.source}' "
                f"based on priority ranking."
            )
        else:
            rationale = (
                f"All agents agree on '{winner.signal}'. "
                f"Selected '{winner.source}' as highest-priority agent."
            )

        return {
            "winner": winner,
            "conflict_report": conflict,
            "alternatives": alternatives,
            "rationale": rationale,
        }

    def set_priorities(self, priorities: List[str]) -> None:
        """Update the priority order dynamically."""
        self.priorities = priorities
        self._priority_map = {s: i for i, s in enumerate(priorities)}
