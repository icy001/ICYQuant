"""
Evolution Memory — Records generation-by-generation evolution history.

Stores:
    - Population snapshots per generation
    - Fitness trends across generations
    - Diversity metrics per generation
    - Pareto frontier size evolution
    - Elite lineage across generations
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvolutionMemory:
    """Records generation-by-generation evolution history."""

    def __init__(self, max_generations_stored: int = 500):
        self._history: List[Dict[str, Any]] = []
        self._max_generations = max_generations_stored

    async def record_generation(self, snapshot: Dict[str, Any]) -> None:
        """Record a generation snapshot."""
        snapshot["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._history.append(snapshot)
        if len(self._history) > self._max_generations:
            self._history = self._history[-self._max_generations:]

    async def get_generation(self, gen: int) -> Optional[Dict[str, Any]]:
        for snap in self._history:
            if snap.get("generation") == gen:
                return snap
        return None

    async def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        return self._history[-n:]

    async def get_fitness_trend(self) -> List[Dict[str, Any]]:
        """Extract fitness trend over generations."""
        return [
            {
                "generation": s.get("generation", 0),
                "best_fitness": s.get("best_fitness", 0),
                "avg_fitness": s.get("avg_fitness", 0),
                "pareto_size": s.get("pareto_size", 0),
            }
            for s in self._history
        ]

    async def get_diversity_trend(self) -> List[Dict[str, Any]]:
        return [
            {"generation": s.get("generation", 0), "diversity": s.get("diversity", 0)}
            for s in self._history
        ]

    async def get_summary(self) -> Dict[str, Any]:
        if not self._history:
            return {"generations": 0}
        latest = self._history[-1]
        first = self._history[0]
        return {
            "total_generations": len(self._history),
            "current_best_fitness": latest.get("best_fitness", 0),
            "initial_best_fitness": first.get("best_fitness", 0),
            "fitness_improvement": latest.get("best_fitness", 0) - first.get("best_fitness", 0),
        }
