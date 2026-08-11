"""Research Queue — Manages pending research tasks with budget awareness."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ResearchQueue:
    """Research task queue with budget-aware scheduling."""

    def __init__(self, max_concurrent: int = 10) -> None:
        self._tasks: List[Dict[str, Any]] = []
        self.max_concurrent = max_concurrent

    async def add(self, task: Dict[str, Any]) -> None:
        self._tasks.append(task)

    async def get_next(self) -> Dict[str, Any]:
        if self._tasks:
            return self._tasks.pop(0)
        return {}

    def pending(self) -> int:
        return len(self._tasks)
