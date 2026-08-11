"""
Experiment Budget Manager — Limits and prioritizes research experiments.

Controls the number of experiments per hypothesis, dynamically adjusts
budget based on experiment value, and prevents resource waste on
low-performing research directions.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ExperimentBudgetManager:
    """
    Manages experiment budgets per research hypothesis/domain.

    Automatically reduces budget for consistently failing experiments
    and increases for promising directions.
    """

    def __init__(self, daily_total: int = 500, max_per_hypothesis: int = 50):
        self._daily_total = daily_total
        self._max_per_hypothesis = max_per_hypothesis
        self._used_total: int = 0
        self._per_hypothesis: dict[str, dict] = {}
        self._last_reset = time.time()
        self._reset_interval = 86400

    def check(self, hypothesis_id: str) -> tuple[bool, str]:
        """Check if experiments are still available."""
        self._maybe_reset()

        if self._used_total >= self._daily_total:
            return False, "Daily experiment budget exhausted"

        h = self._per_hypothesis.get(hypothesis_id, {"used": 0, "budget": self._max_per_hypothesis})
        if h["used"] >= h["budget"]:
            return False, f"Hypothesis {hypothesis_id} budget exhausted"

        return True, ""

    def consume(self, hypothesis_id: str, result_quality: float = 0.5):
        """Consume one experiment with quality feedback."""
        self._maybe_reset()
        self._used_total += 1

        h = self._per_hypothesis.setdefault(
            hypothesis_id,
            {"used": 0, "budget": self._max_per_hypothesis, "last_quality": 0.5, "consecutive_fails": 0},
        )
        h["used"] += 1
        h["last_quality"] = result_quality

        # Dynamic adjustment
        if result_quality < 0.1:
            h["consecutive_fails"] += 1
            if h["consecutive_fails"] >= 5:
                h["budget"] = max(5, h["budget"] // 2)
                logger.info("Hypothesis %s budget reduced to %d after %d consecutive failures",
                            hypothesis_id, h["budget"], h["consecutive_fails"])
        else:
            h["consecutive_fails"] = 0
            if result_quality > 0.7:
                h["budget"] = min(self._max_per_hypothesis * 2, int(h["budget"] * 1.2))
                logger.info("Hypothesis %s budget increased to %d", hypothesis_id, h["budget"])

    def _maybe_reset(self):
        if time.time() - self._last_reset >= self._reset_interval:
            self._used_total = 0
            self._per_hypothesis.clear()
            self._last_reset = time.time()

    def stats(self) -> dict:
        self._maybe_reset()
        return {
            "total_used": self._used_total,
            "total_limit": self._daily_total,
            "hypotheses_tracked": len(self._per_hypothesis),
            "per_hypothesis": {
                hid: {"used": h["used"], "budget": h["budget"]}
                for hid, h in self._per_hypothesis.items()
            },
        }
