"""
Portfolio Memory — Persisted Portfolio State & History

Stores portfolio state, composition history, and decision records
for learning and audit purposes.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PortfolioMemory:
    """
    Persisted memory for portfolio state, composition history,
    and orchestration decision records.
    """

    def __init__(
        self,
        memory_id: Optional[str] = None,
        retention_days: int = 365,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.memory_id = memory_id or f"pm-{uuid.uuid4().hex[:12]}"
        self.retention_days = retention_days
        self.config = config or {}
        self._snapshots: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []

    def store(self, snapshot: Dict[str, Any]) -> None:
        self._snapshots.append({
            "timestamp": datetime.utcnow().isoformat(),
            **snapshot,
        })

    def store_decision(self, decision: Dict[str, Any]) -> None:
        self._decisions.append({
            "stored_at": datetime.utcnow().isoformat(),
            **decision,
        })

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._snapshots[-limit:]

    def get_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._decisions[-limit:]

    def flush(self) -> None:
        pass
