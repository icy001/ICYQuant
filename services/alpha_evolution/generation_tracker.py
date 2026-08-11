"""
Generation Tracker — Tracks per-generation evolution statistics.

Records:
    - Generation number
    - Population size (factors + alphas)
    - Fitness statistics (min, max, avg, median)
    - Elitism count
    - Mutation/crossover counts
    - Validation pass/fail rates
    - Diversity metrics
    - Compute cost
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GenerationTracker:
    """Tracks per-generation statistics for the entire evolution run."""

    def __init__(self, max_generations_stored: int = 500):
        self._generations: List[Dict[str, Any]] = []
        self._max_gen = max_generations_stored

    async def start_generation(self, gen: int) -> None:
        """Mark the start of a new generation."""
        self._generations.append({
            "generation": gen,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "started",
        })

    async def finish_generation(self, gen: int, stats: Dict[str, Any]) -> None:
        """Record final statistics for a generation."""
        for g in reversed(self._generations):
            if g["generation"] == gen:
                g.update(stats)
                g["status"] = "completed"
                g["finished_at"] = datetime.now(timezone.utc).isoformat()
                break

        if len(self._generations) > self._max_gen:
            self._generations = self._generations[-self._max_gen:]

    async def get_current_generation(self) -> int:
        if self._generations:
            return self._generations[-1]["generation"]
        return 0

    async def get_generation(self, gen: int) -> Optional[Dict[str, Any]]:
        for g in self._generations:
            if g["generation"] == gen:
                return g
        return None

    async def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        return self._generations[-n:]

    async def get_summary(self) -> Dict[str, Any]:
        if not self._generations:
            return {"total_generations": 0}
        completed = [g for g in self._generations if g["status"] == "completed"]
        return {
            "total_generations": len(self._generations),
            "completed_generations": len(completed),
            "current_generation": self._generations[-1]["generation"],
            "status": self._generations[-1]["status"],
        }
