"""Multi-Agent Fusion Engine – fuses decisions from multiple agents into one consensus."""

from typing import Dict, List, Optional

from .collector import DecisionPackage


class MultiAgentFusionEngine:
    """Fuses multiple DecisionPackages into a single consensus decision.

    Supports:
      - Confidence-weighted fusion (default)
      - Weighted voting
      - Bayesian-style fusion
    """

    # Standard signal hierarchy for voting resolution
    SIGNAL_STRENGTH = {
        "STRONG_BUY": 5,
        "BUY": 4,
        "WEAK_BUY": 3,
        "HOLD": 2,
        "WEAK_SELL": 1,
        "SELL": 0,
        "STRONG_SELL": -1,
    }

    def fuse(self, decisions: List[DecisionPackage]) -> Optional[DecisionPackage]:
        """Fuse by picking the decision with highest confidence.

        Args:
            decisions: list of DecisionPackages from different agents.

        Returns:
            The winning DecisionPackage, or None if empty.
        """
        if not decisions:
            return None
        return max(decisions, key=lambda d: d.confidence)

    def weighted_vote(
        self,
        decisions: List[DecisionPackage],
        weights: Optional[Dict[str, float]] = None,
    ) -> str:
        """Weighted voting across decisions to produce a single signal.

        Args:
            decisions: list of DecisionPackages.
            weights: optional per-source weight map.

        Returns:
            The winning signal string.
        """
        if not decisions:
            return "HOLD"

        scores: Dict[str, float] = {}
        for d in decisions:
            w = (weights or {}).get(d.source, 1.0)
            signal = d.signal
            scores[signal] = scores.get(signal, 0.0) + d.confidence * w

        return max(scores, key=scores.get) if scores else "HOLD"

    def confidence_weighted_fuse(
        self,
        decisions: List[DecisionPackage],
    ) -> Dict[str, float]:
        """Return a signal → aggregated confidence map.

        Each signal's score = sum(confidence_i) for all decisions with that signal.
        """
        if not decisions:
            return {}

        scores: Dict[str, float] = {}
        for d in decisions:
            scores[d.signal] = scores.get(d.signal, 0.0) + d.confidence

        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

    def bayesian_fuse(
        self,
        decisions: List[DecisionPackage],
        priors: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Bayesian-style fusion with optional priors.

        Posterior ∝ prior * likelihood (confidence_i for signal_i).
        """
        if not decisions:
            return {}

        priors = priors or {}
        signals: Dict[str, float] = {}

        for d in decisions:
            prior = priors.get(d.signal, 1.0 / max(len(decisions), 1))
            signals[d.signal] = signals.get(d.signal, 0.0) + prior * d.confidence

        total = sum(signals.values())
        if total > 0:
            signals = {k: round(v / total, 4) for k, v in signals.items()}

        return dict(sorted(signals.items(), key=lambda x: x[1], reverse=True))
