"""
Model Registry — Central registry for all autonomous models.

Stores metadata for Alpha, Strategy, Portfolio, Risk, and Execution
models with versioning and state tracking.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Registry for all autonomous models across the system.

    Each model entry includes:
    - model_id, version, type
    - Parent model lineage
    - Dataset version
    - Experiment/Strategy/Portfolio IDs
    - Risk profile
    - Current lifecycle state
    """

    def __init__(self):
        self._models: dict[str, dict] = {}
        self._by_type: dict[str, list[str]] = {}
        self._by_state: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        model_id: str,
        model_type: str,
        version: str = "1.0.0",
        parent_model: Optional[str] = None,
        dataset_version: Optional[str] = None,
        experiment_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        risk_profile: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Register a new model."""
        entry = {
            "model_id": model_id,
            "model_type": model_type,
            "version": version,
            "parent_model": parent_model,
            "dataset_version": dataset_version,
            "experiment_id": experiment_id,
            "strategy_id": strategy_id,
            "portfolio_id": portfolio_id,
            "risk_profile": risk_profile or {},
            "metadata": metadata or {},
            "state": "discovered",
            "created_at": time.time(),
            "state_updated_at": time.time(),
        }
        self._models[model_id] = entry
        self._by_type.setdefault(model_type, []).append(model_id)
        self._by_state.setdefault("discovered", []).append(model_id)

        logger.info("Model registered: %s (type=%s, v=%s)", model_id, model_type, version)
        return entry

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, model_id: str) -> Optional[dict]:
        return self._models.get(model_id)

    def all(self) -> list[dict]:
        return list(self._models.values())

    def by_type(self, model_type: str) -> list[dict]:
        ids = self._by_type.get(model_type, [])
        return [self._models[mid] for mid in ids if mid in self._models]

    def by_state(self, state: str) -> list[dict]:
        ids = self._by_state.get(state, [])
        return [self._models[mid] for mid in ids if mid in self._models]

    def active_production(self) -> list[dict]:
        return self.by_state("production")

    def update_state(self, model_id: str, old_state: str, new_state: str) -> None:
        """Update state indices when a model transitions."""
        # Remove from old state index
        if old_state in self._by_state:
            self._by_state[old_state] = [m for m in self._by_state[old_state] if m != model_id]
        # Add to new state index
        self._by_state.setdefault(new_state, []).append(model_id)

    def count(self) -> int:
        return len(self._models)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_models": len(self._models),
            "by_type": {t: len(ids) for t, ids in self._by_type.items()},
            "by_state": {s: len(ids) for s, ids in self._by_state.items()},
        }
