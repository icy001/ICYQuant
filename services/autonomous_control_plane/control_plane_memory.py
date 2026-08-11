"""
Control Plane Memory — Persistent memory for governance decisions.

Stores policy memory, decision memory, incident memory, autonomy memory,
budget memory, and promotion memory for learning and audit.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControlPlaneMemory:
    """
    Persistent memory for the Control Plane.

    Records governance decisions, policy effectiveness, incident
    patterns, and promotion outcomes to enable learning.

    Memory can influence future recommendations but cannot bypass policy.
    """

    def __init__(self):
        self._policy_effectiveness: list[dict] = []
        self._decision_outcomes: list[dict] = []
        self._promotion_results: list[dict] = []
        self._incident_patterns: list[dict] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_policy_effect(self, policy_id: str, decision_id: str, prevented_loss: bool, context: dict):
        """Record policy enforcement outcome."""
        self._policy_effectiveness.append({
            "policy_id": policy_id,
            "decision_id": decision_id,
            "prevented_loss": prevented_loss,
            "context": context,
            "timestamp": time.time(),
        })

    def record_decision_outcome(self, decision_id: str, outcome: str, quality_score: float):
        """Record decision outcome for learning."""
        self._decision_outcomes.append({
            "decision_id": decision_id,
            "outcome": outcome,
            "quality_score": quality_score,
            "timestamp": time.time(),
        })

    def record_promotion(self, model_id: str, success: bool, pnl_impact: float):
        """Record promotion result."""
        self._promotion_results.append({
            "model_id": model_id,
            "success": success,
            "pnl_impact": pnl_impact,
            "timestamp": time.time(),
        })

    def record_incident_pattern(self, pattern_type: str, frequency: int, avoidance_strategy: str):
        """Record an incident pattern for future prevention."""
        self._incident_patterns.append({
            "pattern_type": pattern_type,
            "frequency": frequency,
            "avoidance_strategy": avoidance_strategy,
            "timestamp": time.time(),
        })

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_policy_stats(self) -> dict:
        """Get statistics on policy effectiveness."""
        total = len(self._policy_effectiveness)
        prevented = sum(1 for e in self._policy_effectiveness if e["prevented_loss"])
        return {
            "total_enforcements": total,
            "loss_prevention": prevented,
            "prevention_rate": prevented / max(total, 1),
        }

    def get_decision_quality(self) -> dict:
        if not self._decision_outcomes:
            return {"average_quality": 0, "samples": 0}
        avg = sum(d["quality_score"] for d in self._decision_outcomes) / len(self._decision_outcomes)
        return {"average_quality": avg, "samples": len(self._decision_outcomes)}

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "policy_records": len(self._policy_effectiveness),
            "decision_records": len(self._decision_outcomes),
            "promotion_records": len(self._promotion_results),
            "incident_patterns": len(self._incident_patterns),
            "policy_stats": self.get_policy_stats(),
            "decision_quality": self.get_decision_quality(),
        }
