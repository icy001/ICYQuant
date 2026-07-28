"""Signal Attribution Engine – decomposes a signal into module contributions."""

from typing import Dict


class SignalAttributionEngine:
    """Attributes a trading signal to contributing sub-modules (price, macro, sentiment, etc.)."""

    def analyze(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Normalize raw scores into proportional contributions summing to ~1.0.

        Args:
            scores: raw scores per module, e.g. {"price_model": 0.40, "macro": 0.25}.

        Returns:
            Normalized contribution map.
        """
        if not scores:
            return {}

        total = sum(scores.values())
        if total == 0:
            return {k: 0.0 for k in scores}

        return {k: round(v / total, 4) for k, v in scores.items()}

    def top_contributors(self, scores: Dict[str, float], n: int = 3) -> Dict[str, float]:
        """Return the top-N contributing modules."""
        attr = self.analyze(scores)
        sorted_items = sorted(attr.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_items[:n])
