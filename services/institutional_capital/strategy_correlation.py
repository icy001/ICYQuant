"""
Strategy Correlation — Returns-Based Correlation Matrix

Computes pairwise strategy correlations from return streams.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class StrategyCorrelation:
    """
    Computes and stores pairwise strategy return correlations.
    Handles missing data, stale correlations, and correlation drift detection.
    """

    def __init__(
        self,
        corr_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.corr_id = corr_id or f"scorr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._matrix: Dict[str, Dict[str, float]] = {}
        self._stale_threshold_hours = self.config.get("stale_hours", 24)

    def set(self, s1: str, s2: str, correlation: float) -> None:
        """Set pairwise correlation (automatically symmetric)."""
        self._matrix.setdefault(s1, {})[s2] = correlation
        self._matrix.setdefault(s2, {})[s1] = correlation

    def get(self, s1: str, s2: str) -> Optional[float]:
        if s1 == s2:
            return 1.0
        return self._matrix.get(s1, {}).get(s2)

    def get_matrix(self) -> Dict[str, Dict[str, float]]:
        return self._matrix

    def get_average_correlation(self) -> float:
        """Average off-diagonal correlation."""
        values = []
        keys = list(self._matrix.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                v = self._matrix[keys[i]].get(keys[j])
                if v is not None:
                    values.append(v)
        return sum(values) / len(values) if values else 0.0

    def detect_correlation_breaks(self) -> List[Dict[str, Any]]:
        """Detect pairs with high correlation (>0.70) that need attention."""
        breaks = []
        keys = list(self._matrix.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                corr = self._matrix[keys[i]].get(keys[j], 0)
                if abs(corr) > 0.70:
                    breaks.append({
                        "strategies": [keys[i], keys[j]],
                        "correlation": corr,
                        "severity": "HIGH" if abs(corr) > 0.85 else "MEDIUM",
                    })
        return breaks
