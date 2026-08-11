"""Opportunity Queue — Priority queue for research opportunities."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class OpportunityQueue:
    """Priority queue for research opportunities — higher priority served first."""

    def __init__(self, max_size: int = 100) -> None:
        self._queue: List[Dict[str, Any]] = []
        self.max_size = max_size

    async def enqueue(self, opportunity: Dict[str, Any]) -> None:
        if len(self._queue) >= self.max_size:
            self._queue.pop(0)
        opportunity["queued_at"] = datetime.now(timezone.utc).isoformat()
        self._queue.append(opportunity)
        self._sort()

    async def dequeue(self) -> Dict[str, Any]:
        if self._queue:
            return self._queue.pop(0)
        return {"status": "empty"}

    def _sort(self) -> None:
        self._queue.sort(key=lambda o: o.get("priority_score", 0), reverse=True)

    def size(self) -> int:
        return len(self._queue)
