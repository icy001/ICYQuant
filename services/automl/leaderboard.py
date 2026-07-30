"""Model Leaderboard.

Ranking system for AutoML trials across multiple scopes
and ranking metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class LeaderboardScope(str, Enum):
    GLOBAL = "global"
    MARKET = "market"
    STRATEGY = "strategy"
    MODEL_TYPE = "model_type"


class RankMetric(str, Enum):
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    IC = "ic"
    COMPOSITE = "composite"
    STABILITY = "stability"
    RETURN = "return"


@dataclass
class LeaderboardEntry:
    """A single entry in the leaderboard."""

    rank: int = 0
    model_name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    trial_id: str = ""
    created_at: float = field(default_factory=time.time)
    scope: LeaderboardScope = LeaderboardScope.GLOBAL
    tags: List[str] = field(default_factory=list)


@dataclass
class LeaderboardConfig:
    """Leaderboard configuration.

    Attributes:
        scope: Ranking scope.
        metric: Primary ranking metric.
        top_n: How many entries to retain.
        maximize: Higher score = better rank.
        min_trials_for_rank: Minimum trials before ranking.
    """

    scope: LeaderboardScope = LeaderboardScope.GLOBAL
    metric: RankMetric = RankMetric.SHARPE
    top_n: int = 50
    maximize: bool = True
    min_trials_for_rank: int = 5


class Leaderboard:
    """AutoML model ranking leaderboard.

    Manages ranked entries across multiple scopes and supports
    querying by market, model type, or strategy.
    """

    # ---- init ----

    def __init__(self, config: Optional[LeaderboardConfig] = None) -> None:
        self.config = config or LeaderboardConfig()
        self._entries: Dict[LeaderboardScope, List[LeaderboardEntry]] = {
            scope: [] for scope in LeaderboardScope
        }

    # ---- entry management ----

    def add_entry(self, entry: LeaderboardEntry) -> None:
        """Add an entry and re-rank."""
        scope = entry.scope
        self._entries.setdefault(scope, [])
        self._entries[scope].append(entry)
        self._rank_scope(scope)

    def add_result(
        self,
        model_name: str,
        score: float,
        metrics: Optional[Dict[str, float]] = None,
        config: Optional[Dict[str, Any]] = None,
        trial_id: str = "",
        scope: LeaderboardScope = LeaderboardScope.GLOBAL,
        tags: Optional[List[str]] = None,
    ) -> LeaderboardEntry:
        """Add a result and return the ranked entry."""
        entry = LeaderboardEntry(
            rank=0,
            model_name=model_name,
            config=config or {},
            score=score,
            metrics=metrics or {},
            trial_id=trial_id,
            scope=scope,
            tags=tags or [],
        )
        self.add_entry(entry)
        return entry

    # ---- ranking ----

    def _rank_scope(self, scope: LeaderboardScope) -> None:
        entries = self._entries.get(scope, [])
        cfg = self.config
        # Sort by metric
        entries.sort(key=lambda e: self._get_rank_value(e), reverse=cfg.maximize)
        for i, entry in enumerate(entries[:cfg.top_n]):
            entry.rank = i + 1
        # Trim excess
        self._entries[scope] = entries[:cfg.top_n]

    def _get_rank_value(self, entry: LeaderboardEntry) -> float:
        metric_key = self.config.metric.value
        # Try exact metric key first
        return entry.metrics.get(metric_key, entry.score)

    # ---- query ----

    def top(self, n: int = 10, scope: Optional[LeaderboardScope] = None) -> List[LeaderboardEntry]:
        scope = scope or self.config.scope
        entries = self._entries.get(scope, [])
        return entries[:n]

    def get_rank(self, model_name: str, scope: Optional[LeaderboardScope] = None) -> Optional[int]:
        scope = scope or self.config.scope
        for entry in self._entries.get(scope, []):
            if entry.model_name == model_name:
                return entry.rank
        return None

    def champion(self, scope: Optional[LeaderboardScope] = None) -> Optional[LeaderboardEntry]:
        scope = scope or self.config.scope
        entries = self._entries.get(scope, [])
        return entries[0] if entries else None

    def list_models(self, scope: Optional[LeaderboardScope] = None) -> List[str]:
        scope = scope or self.config.scope
        return [e.model_name for e in self._entries.get(scope, [])]

    # ---- comparison ----

    def compare(self, model_a: str, model_b: str, scope: Optional[LeaderboardScope] = None) -> Dict[str, Any]:
        scope = scope or self.config.scope
        entry_a = None
        entry_b = None
        for e in self._entries.get(scope, []):
            if e.model_name == model_a:
                entry_a = e
            if e.model_name == model_b:
                entry_b = e

        result: Dict[str, Any] = {
            "model_a": model_a,
            "model_b": model_b,
            "scope": scope.value if scope else "global",
        }

        if entry_a and entry_b:
            result["a_rank"] = entry_a.rank
            result["b_rank"] = entry_b.rank
            result["a_score"] = entry_a.score
            result["b_score"] = entry_b.score
            result["winner"] = model_a if entry_a.rank < entry_b.rank else model_b
            # Metric diff
            diff: Dict[str, float] = {}
            all_keys = set(entry_a.metrics.keys()) | set(entry_b.metrics.keys())
            for key in all_keys:
                va = entry_a.metrics.get(key, 0)
                vb = entry_b.metrics.get(key, 0)
                diff[key] = va - vb
            result["metric_diff"] = diff

        return result

    # ---- stats ----

    def stats(self, scope: Optional[LeaderboardScope] = None) -> Dict[str, Any]:
        scope = scope or self.config.scope
        entries = self._entries.get(scope, [])
        if not entries:
            return {"scope": scope.value if scope else "global", "entries": 0}

        scores = [e.score for e in entries]
        return {
            "scope": scope.value if scope else "global",
            "entries": len(entries),
            "champion": entries[0].model_name if entries else None,
            "best_score": max(scores),
            "worst_score": min(scores),
            "mean_score": float(np.mean(scores)),
            "std_score": float(np.std(scores)) if len(scores) > 1 else 0.0,
            "top_models": [e.model_name for e in entries[:5]],
        }

    def clear(self, scope: Optional[LeaderboardScope] = None) -> None:
        if scope:
            self._entries[scope] = []
        else:
            self._entries = {s: [] for s in LeaderboardScope}

    def entry_count(self, scope: Optional[LeaderboardScope] = None) -> int:
        if scope:
            return len(self._entries.get(scope, []))
        return sum(len(v) for v in self._entries.values())
