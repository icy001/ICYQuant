"""
Rebalance Memory — Rebalance History & Learning

Stores rebalance plans, execution results, and cost/benefit outcomes
for continuous improvement of rebalancing decisions.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class RebalanceMemory:
    """Stores rebalance history for audit and learning."""

    def __init__(
        self,
        memory_id: Optional[str] = None,
        retention_days: int = 365,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.memory_id = memory_id or f"rm-{uuid.uuid4().hex[:12]}"
        self.retention_days = retention_days
        self.config = config or {}
        self._plans: List[Dict[str, Any]] = []
        self._executions: List[Dict[str, Any]] = []

    def record_plan(self, plan: Dict[str, Any]) -> None:
        self._plans.append({
            "timestamp": datetime.utcnow().isoformat(),
            **plan,
        })

    def record_execution(self, execution: Dict[str, Any]) -> None:
        self._executions.append({
            "timestamp": datetime.utcnow().isoformat(),
            **execution,
        })

    def get_total_savings(self) -> float:
        """Estimated cost savings from skipped rebalances."""
        skipped = [e for e in self._executions if e.get("action") == "SKIP"]
        return sum(e.get("cost_saved", 0) for e in skipped)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._plans)

    def flush(self) -> None:
        pass
