"""Cost Manager — tracks and optimizes monetary cost across all model calls.

The CostManager integrates with the ModelRegistry's pricing data to compute
real-time costs for every model call. It tracks costs per user, project, and
model, providing dashboards and alerts for cost governance.

Cost tracking dimensions:
    - Per user
    - Per project
    - Per model
    - Per provider
    - Per time period (daily, weekly, monthly)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """A single cost entry for a model call."""
    timestamp: float = field(default_factory=time.monotonic)
    user_id: str = ""
    project_id: str = ""
    model_id: str = ""
    provider_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostSummary:
    """Aggregated cost summary."""
    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    by_user: Dict[str, float] = field(default_factory=dict)
    by_project: Dict[str, float] = field(default_factory=dict)
    by_model: Dict[str, float] = field(default_factory=dict)
    by_provider: Dict[str, float] = field(default_factory=dict)


class CostManager:
    """Tracks and manages monetary costs for AI model usage.

    Records every model call's cost, aggregates by dimensions, and provides
    real-time cost visibility for budget governance.

    Usage:
        cm = CostManager()
        await cm.initialize()
        cm.record_cost(user_id="user_1", model_id="gpt-4o", input_tokens=500, output_tokens=200, cost_usd=0.005)
        summary = cm.get_summary()
    """

    def __init__(self) -> None:
        self._records: List[CostRecord] = []
        self._max_records: int = 50000
        self._pricing: Dict[str, Dict[str, float]] = {}
        self._initialized: bool = False
        self._lock = threading.Lock()
        logger.info("CostManager created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("CostManager initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._records.clear()
            self._pricing.clear()
        self._initialized = False
        logger.info("CostManager shutdown complete")

    def register_pricing(self, model_id: str, input_per_1k: float, output_per_1k: float) -> None:
        """Register pricing for a model (per 1000 tokens)."""
        self._pricing[model_id] = {"input": input_per_1k, "output": output_per_1k}

    def compute_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Compute cost for a model call based on registered pricing."""
        pricing = self._pricing.get(model_id, {"input": 0.0, "output": 0.0})
        cost = (input_tokens / 1000.0) * pricing["input"] + (output_tokens / 1000.0) * pricing["output"]
        return round(cost, 6)

    def record_cost(self, user_id: str = "", project_id: str = "", model_id: str = "", provider_name: str = "", input_tokens: int = 0, output_tokens: int = 0, cost_usd: Optional[float] = None) -> CostRecord:
        """Record a model call cost."""
        if cost_usd is None:
            cost_usd = self.compute_cost(model_id, input_tokens, output_tokens)

        record = CostRecord(
            user_id=user_id,
            project_id=project_id,
            model_id=model_id,
            provider_name=provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

        logger.debug("CostManager: recorded $%.6f (model=%s, user=%s)", cost_usd, model_id, user_id)
        return record

    def get_summary(self, since_sec: Optional[float] = None) -> CostSummary:
        """Get aggregated cost summary, optionally since a specific time."""
        summary = CostSummary()
        with self._lock:
            records = self._records
            if since_sec is not None:
                records = [r for r in records if r.timestamp >= since_sec]

            for r in records:
                summary.total_cost_usd += r.cost_usd
                summary.total_calls += 1
                summary.total_input_tokens += r.input_tokens
                summary.total_output_tokens += r.output_tokens
                if r.user_id:
                    summary.by_user[r.user_id] = summary.by_user.get(r.user_id, 0.0) + r.cost_usd
                if r.project_id:
                    summary.by_project[r.project_id] = summary.by_project.get(r.project_id, 0.0) + r.cost_usd
                if r.model_id:
                    summary.by_model[r.model_id] = summary.by_model.get(r.model_id, 0.0) + r.cost_usd
                if r.provider_name:
                    summary.by_provider[r.provider_name] = summary.by_provider.get(r.provider_name, 0.0) + r.cost_usd

        summary.total_cost_usd = round(summary.total_cost_usd, 6)
        return summary

    def get_user_cost(self, user_id: str) -> float:
        """Get total cost for a user."""
        with self._lock:
            return round(sum(r.cost_usd for r in self._records if r.user_id == user_id), 6)

    def get_project_cost(self, project_id: str) -> float:
        """Get total cost for a project."""
        with self._lock:
            return round(sum(r.cost_usd for r in self._records if r.project_id == project_id), 6)

    def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get users ranked by cost."""
        with self._lock:
            user_costs: Dict[str, float] = {}
            for r in self._records:
                if r.user_id:
                    user_costs[r.user_id] = user_costs.get(r.user_id, 0.0) + r.cost_usd
            ranked = sorted(user_costs.items(), key=lambda x: x[1], reverse=True)
            return [{"user_id": uid, "cost_usd": round(c, 6)} for uid, c in ranked[:limit]]

    def get_summary_dict(self) -> Dict[str, Any]:
        summary = self.get_summary()
        return {
            "initialized": self._initialized,
            "total_cost_usd": summary.total_cost_usd,
            "total_calls": summary.total_calls,
            "total_input_tokens": summary.total_input_tokens,
            "total_output_tokens": summary.total_output_tokens,
            "unique_users": len(summary.by_user),
            "unique_projects": len(summary.by_project),
            "unique_models": len(summary.by_model),
            "top_users": self.get_top_users(5),
        }
