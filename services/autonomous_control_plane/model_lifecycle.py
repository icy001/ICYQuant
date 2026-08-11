"""
Model Lifecycle — Unified model state lifecycle management.

Manages the full lifecycle of all models (Alpha, Strategy, Portfolio)
from discovery through retirement with defined state transitions.
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ModelLifecycleState(Enum):
    """Unified model lifecycle states."""
    DISCOVERED = "discovered"
    RESEARCH = "research"
    VALIDATING = "validating"
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    PAPER = "paper"
    PRODUCTION = "production"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


# Valid state transitions
VALID_TRANSITIONS: dict[ModelLifecycleState, list[ModelLifecycleState]] = {
    ModelLifecycleState.DISCOVERED: [ModelLifecycleState.RESEARCH],
    ModelLifecycleState.RESEARCH: [ModelLifecycleState.VALIDATING, ModelLifecycleState.RETIRED],
    ModelLifecycleState.VALIDATING: [ModelLifecycleState.CANDIDATE, ModelLifecycleState.RETIRED],
    ModelLifecycleState.CANDIDATE: [ModelLifecycleState.SHADOW, ModelLifecycleState.RETIRED],
    ModelLifecycleState.SHADOW: [ModelLifecycleState.PAPER, ModelLifecycleState.DEGRADED, ModelLifecycleState.RETIRED],
    ModelLifecycleState.PAPER: [ModelLifecycleState.PRODUCTION, ModelLifecycleState.DEGRADED, ModelLifecycleState.RETIRED],
    ModelLifecycleState.PRODUCTION: [ModelLifecycleState.DEGRADED, ModelLifecycleState.QUARANTINED, ModelLifecycleState.RETIRED],
    ModelLifecycleState.DEGRADED: [ModelLifecycleState.PRODUCTION, ModelLifecycleState.QUARANTINED, ModelLifecycleState.RETIRED],
    ModelLifecycleState.QUARANTINED: [ModelLifecycleState.SHADOW, ModelLifecycleState.RETIRED],
    ModelLifecycleState.RETIRED: [],  # Terminal state
}


class ModelLifecycle:
    """
    Unified lifecycle manager for all autonomous models.

    Tracks each model's state, enforces valid transitions, and
    maintains transition history for audit.
    """

    def __init__(self, registry=None):
        from .model_registry import ModelRegistry
        self._registry = registry or ModelRegistry()
        self._transitions: list[dict] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        logger.info("ModelLifecycle started")

    async def evaluate(self, context) -> object:
        """Evaluate whether the model is in a healthy state."""
        from .decision_result import DecisionResult
        model_id = getattr(context, "entity_id", "")
        if not model_id:
            return DecisionResult.allowed_result()

        model = self._registry.get(model_id)
        if not model:
            return DecisionResult.allowed_result()

        state = ModelLifecycleState(model.get("state", "discovered"))
        if state in (ModelLifecycleState.QUARANTINED, ModelLifecycleState.RETIRED):
            return DecisionResult.denied(f"Model in {state.value} state")
        if state == ModelLifecycleState.DEGRADED:
            return DecisionResult(
                allowed=True,
                reason="Model degraded — use with caution",
            )

        return DecisionResult.allowed_result()

    # ------------------------------------------------------------------
    # State Transitions
    # ------------------------------------------------------------------

    def transition(
        self, model_id: str, to_state: ModelLifecycleState, reason: str = ""
    ) -> tuple[bool, str]:
        """Transition a model to a new state."""
        model = self._registry.get(model_id)
        if not model:
            return False, "Model not found"

        current = ModelLifecycleState(model.get("state", "discovered"))
        valid_next = VALID_TRANSITIONS.get(current, [])

        if to_state not in valid_next:
            return False, f"Invalid transition: {current.value} → {to_state.value}"

        model["state"] = to_state.value
        model["state_updated_at"] = time.time()

        self._transitions.append({
            "model_id": model_id,
            "from": current.value,
            "to": to_state.value,
            "reason": reason,
            "timestamp": time.time(),
        })

        logger.info("Model %s: %s → %s (%s)", model_id, current.value, to_state.value, reason)
        return True, ""

    def get_state(self, model_id: str) -> Optional[ModelLifecycleState]:
        model = self._registry.get(model_id)
        if model:
            return ModelLifecycleState(model.get("state", "discovered"))
        return None

    def history(self, model_id: str = None) -> list[dict]:
        if model_id:
            return [t for t in self._transitions if t["model_id"] == model_id]
        return list(self._transitions)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        counts = {}
        for model in self._registry.all():
            state = model.get("state", "unknown")
            counts[state] = counts.get(state, 0) + 1
        return {
            "total_models": self._registry.count(),
            "state_distribution": counts,
            "transitions_total": len(self._transitions),
        }
