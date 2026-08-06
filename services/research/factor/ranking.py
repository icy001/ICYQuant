"""Ranking — cross-sectional factor value ranking.

Supports::

    Ascending, Descending, Percentile Rank, Cross Section Rank

Used for portfolio construction and factor evaluation.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RankingMethod(str, Enum):
    """Ranking methods."""

    ASCENDING = "ascending"
    DESCENDING = "descending"
    PERCENTILE = "percentile"
    CROSS_SECTION = "cross_section"


class Ranker:
    """Cross-sectional factor value ranker.

    Methods:
    * Ascending: rank from lowest to highest (1 = lowest)
    * Descending: rank from highest to lowest (1 = highest)
    * Percentile: rank as percentile [0, 1]
    * Cross Section: rank within each cross-section independently
    """

    def __init__(
        self, method: RankingMethod = RankingMethod.DESCENDING
    ) -> None:
        self._method = method

    @property
    def method(self) -> RankingMethod:
        return self._method

    def rank(self, values: List[float]) -> List[float]:
        """Rank factor values.

        Args:
            values: factor values for a single cross-section

        Returns:
            ranked values (1-based ranks or percentiles)
        """
        if not values:
            return []

        n = len(values)
        indexed = list(enumerate(values))

        if self._method == RankingMethod.ASCENDING:
            indexed.sort(key=lambda x: x[1])
        elif self._method == RankingMethod.DESCENDING:
            indexed.sort(key=lambda x: -x[1])
        elif self._method in (RankingMethod.PERCENTILE, RankingMethod.CROSS_SECTION):
            indexed.sort(key=lambda x: x[1])

        ranks = [0.0] * n

        if self._method == RankingMethod.PERCENTILE:
            for rank_pos, (orig_idx, _) in enumerate(indexed):
                ranks[orig_idx] = rank_pos / (n - 1) if n > 1 else 0.5
        else:
            # Handle ties by assigning average rank
            i = 0
            while i < n:
                j = i
                while j < n and indexed[j][1] == indexed[i][1]:
                    j += 1
                avg_rank = (i + j - 1) / 2 + 1  # 1-based average
                for k in range(i, j):
                    ranks[indexed[k][0]] = avg_rank
                i = j

        return ranks

    def rank_cross_sectional(
        self,
        cross_sections: Dict[str, List[float]],
    ) -> Dict[str, List[float]]:
        """Rank each cross-section independently.

        Args:
            cross_sections: date → values mapping

        Returns:
            date → ranked values mapping
        """
        result: Dict[str, List[float]] = {}
        for date_key, values in cross_sections.items():
            result[date_key] = self.rank(values)
        return result

    def top_n(
        self,
        values: List[float],
        n: int = 50,
        identifiers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get top N ranked items with scores.

        Args:
            values: factor values
            n: number of top items to return
            identifiers: optional item identifiers

        Returns:
            list of {index/id, value, rank} dicts
        """
        if not values:
            return []

        ranks = self.rank(values)
        items = []
        for i, (v, r) in enumerate(zip(values, ranks)):
            items.append({
                "index": i,
                "id": identifiers[i] if identifiers else str(i),
                "value": v,
                "rank": r,
            })

        if self._method == RankingMethod.DESCENDING:
            items.sort(key=lambda x: x["value"], reverse=True)
        else:
            items.sort(key=lambda x: x["value"])

        return items[:n]
