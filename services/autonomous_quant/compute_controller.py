"""Compute Controller — Manages compute resource allocation for research tasks."""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


class ComputeController:
    """Manages CPU/GPU/memory allocation for autonomous research."""

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self._active_tasks: int = 0

    async def acquire(self, task_type: str) -> bool:
        if self._active_tasks >= self.config.max_concurrent_research:
            return False
        self._active_tasks += 1
        return True

    async def release(self, task_type: str) -> None:
        self._active_tasks = max(0, self._active_tasks - 1)

    async def health(self) -> Dict[str, Any]:
        return {"active_tasks": self._active_tasks, "max_concurrent": self.config.max_concurrent_research}
