"""
Alpha Repository — Alpha score persistence and query.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Persistent storage of alpha scores
    - Time-series queries by alpha, instrument, time range
    - Batch save operations
    - Score statistics aggregation
"""

from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaScore, AlphaType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class AlphaQuery:
    """Flexible query for alpha score history."""
    alpha_id: Optional[str] = None
    alpha_type: Optional[AlphaType] = None
    instrument: Optional[str] = None
    min_quality: Optional[float] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


@dataclass
class AlphaStats:
    """Aggregated statistics for alpha scores."""
    alpha_id: str = ""
    count: int = 0
    mean: float = 0.0
    std: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    avg_quality: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Alpha Repository
# ---------------------------------------------------------------------------

class AlphaRepository:
    """Persistent storage for alpha scores.

    In production, backed by a time-series database.
    """

    DEFAULT_MAX_CAPACITY = 200_000

    def __init__(self, max_capacity: int = DEFAULT_MAX_CAPACITY):
        self._max_capacity = max_capacity
        self._scores: OrderedDict[str, AlphaScore] = OrderedDict()
        self._index_alpha: Dict[str, List[str]] = defaultdict(list)  # alpha_id → [score_ids]
        self._index_instrument: Dict[str, List[str]] = defaultdict(list)
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AlphaRepository initialized (capacity=%d)", self._max_capacity)

    async def shutdown(self) -> None:
        self._scores.clear()
        self._index_alpha.clear()
        self._index_instrument.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, score: AlphaScore) -> str:
        self._evict_if_needed()
        score_id = score.alpha_id or str(int(score.timestamp.timestamp() * 1_000_000))
        # Ensure unique key
        key = f"{score.alpha_id}:{score.instrument}:{score_id}"
        self._scores[key] = score
        self._index_alpha[score.alpha_id].append(key)
        self._index_instrument[score.instrument].append(key)
        return key

    async def save_batch(self, scores: List[AlphaScore]) -> List[str]:
        return [await self.save(s) for s in scores]

    async def query(self, q: AlphaQuery) -> List[AlphaScore]:
        results = []
        for score in self._scores.values():
            if q.alpha_id and score.alpha_id != q.alpha_id:
                continue
            if q.alpha_type and score.alpha_type != q.alpha_type:
                continue
            if q.instrument and score.instrument != q.instrument:
                continue
            if q.min_quality is not None and score.quality_score < q.min_quality:
                continue
            if q.from_time and score.timestamp < q.from_time:
                continue
            if q.to_time and score.timestamp > q.to_time:
                continue
            results.append(score)

        results.sort(key=lambda s: s.timestamp, reverse=True)
        return results[q.offset: q.offset + q.limit]

    async def get_by_alpha(self, alpha_id: str, limit: int = 100) -> List[AlphaScore]:
        keys = self._index_alpha.get(alpha_id, [])
        return [self._scores[k] for k in reversed(keys[-limit:]) if k in self._scores]

    async def get_by_instrument(self, instrument: str, limit: int = 100) -> List[AlphaScore]:
        keys = self._index_instrument.get(instrument, [])
        return [self._scores[k] for k in reversed(keys[-limit:]) if k in self._scores]

    async def get_latest(self, alpha_id: str, instrument: str) -> Optional[AlphaScore]:
        keys = self._index_alpha.get(alpha_id, [])
        for k in reversed(keys):
            score = self._scores.get(k)
            if score and score.instrument == instrument:
                return score
        return None

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_stats(self, alpha_id: str, from_time: Optional[datetime] = None,
                        to_time: Optional[datetime] = None) -> AlphaStats:
        scores = await self.get_by_alpha(alpha_id)
        if from_time:
            scores = [s for s in scores if s.timestamp >= from_time]
        if to_time:
            scores = [s for s in scores if s.timestamp <= to_time]

        stats = AlphaStats(alpha_id=alpha_id, count=len(scores))
        if not scores:
            return stats

        raw = [s.raw_score for s in scores]
        quality = [s.quality_score for s in scores]
        n = len(raw)

        mean = sum(raw) / n
        variance = sum((x - mean) ** 2 for x in raw) / n

        stats.mean = mean
        stats.std = variance ** 0.5
        stats.min_score = min(raw)
        stats.max_score = max(raw)
        stats.avg_quality = sum(quality) / n
        stats.period_start = min(s.timestamp for s in scores)
        stats.period_end = max(s.timestamp for s in scores)

        return stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        while len(self._scores) >= self._max_capacity:
            oldest_key, _ = self._scores.popitem(last=False)

    @property
    def count(self) -> int:
        return len(self._scores)
