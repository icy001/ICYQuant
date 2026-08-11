"""
Compute Budget Manager — Fine-grained compute resource allocation.

Manages compute budgets specifically for autonomous research,
including CPU hours, GPU hours, and priority-based allocation.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ComputeBudget:
    """Compute resource budget."""
    cpu_hours: float = 10.0
    gpu_hours: float = 2.0
    memory_gb_hours: float = 100.0


class ComputeBudgetManager:
    """
    Manages compute resource budgets for autonomous operations.

    Tracks CPU/GPU/memory usage and enforces daily limits.
    """

    def __init__(self, daily_budget: Optional[ComputeBudget] = None):
        self._budget = daily_budget or ComputeBudget()
        self._cpu_used: float = 0.0
        self._gpu_used: float = 0.0
        self._memory_used: float = 0.0
        self._last_reset = time.time()
        self._reset_interval = 86400

    def check(self, cpu_needed: float = 0, gpu_needed: float = 0, memory_gb: float = 0) -> tuple[bool, str]:
        """Check if requested compute resources are available."""
        self._maybe_reset()

        if cpu_needed > 0 and self._cpu_used + cpu_needed > self._budget.cpu_hours:
            return False, f"CPU budget exceeded ({self._cpu_used:.1f}/{self._budget.cpu_hours:.1f}h)"
        if gpu_needed > 0 and self._gpu_used + gpu_needed > self._budget.gpu_hours:
            return False, f"GPU budget exceeded ({self._gpu_used:.1f}/{self._budget.gpu_hours:.1f}h)"
        if memory_gb > 0 and self._memory_used + memory_gb > self._budget.memory_gb_hours:
            return False, f"Memory budget exceeded"

        return True, ""

    def consume(self, cpu: float = 0, gpu: float = 0, memory: float = 0):
        """Consume compute resources."""
        self._maybe_reset()
        self._cpu_used += cpu
        self._gpu_used += gpu
        self._memory_used += memory

    def _maybe_reset(self):
        if time.time() - self._last_reset >= self._reset_interval:
            self._cpu_used = 0.0
            self._gpu_used = 0.0
            self._memory_used = 0.0
            self._last_reset = time.time()

    def remaining(self) -> dict:
        self._maybe_reset()
        return {
            "cpu_hours": self._budget.cpu_hours - self._cpu_used,
            "gpu_hours": self._budget.gpu_hours - self._gpu_used,
            "memory_gb_hours": self._budget.memory_gb_hours - self._memory_used,
        }

    def stats(self) -> dict:
        r = self.remaining()
        return {
            "budget": {
                "cpu_hours": self._budget.cpu_hours,
                "gpu_hours": self._budget.gpu_hours,
                "memory_gb_hours": self._budget.memory_gb_hours,
            },
            "used": {"cpu": self._cpu_used, "gpu": self._gpu_used, "memory": self._memory_used},
            "remaining": r,
        }
