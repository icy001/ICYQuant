"""
ICYQuant Retraining Policy — Defines retraining and promotion policies.

Manages:
  - Per-model retraining policies (when to retrain)
  - Promotion policies (when to promote candidate → production)
  - Validation criteria for candidate models
  - Rollback strategies for failed promotions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RetrainPolicyType(str, Enum):
    """Types of retraining policies."""
    STRICT = "strict"          # Always retrain on any trigger
    CONSERVATIVE = "conservative"  # Retrain but require validation
    ADAPTIVE = "adaptive"      # Adjust thresholds based on history
    MANUAL_ONLY = "manual_only"  # Only manual triggers


class PromotionPolicy(str, Enum):
    """Types of promotion policies."""
    AUTO_CANARY = "auto_canary"           # Auto-start canary
    AUTO_PROMOTE = "auto_promote"          # Auto-promote to production
    REQUIRE_APPROVAL = "require_approval"  # Manual approval required
    SHADOW_FIRST = "shadow_first"         # Shadow → Canary → Production


@dataclass
class RetrainingPolicyConfig:
    """Comprehensive retraining policy configuration."""
    model_id: str
    retrain_policy: RetrainPolicyType = RetrainPolicyType.CONSERVATIVE
    promotion_policy: PromotionPolicy = PromotionPolicy.AUTO_CANARY

    # Retraining constraints
    max_retrains_per_day: int = 3
    min_hours_between_retrains: float = 1.0
    min_improvement_percent: float = 5.0

    # Validation gates
    require_backtest: bool = True
    require_shadow_evaluation: bool = False
    min_shadow_samples: int = 1000
    max_shadow_duration_hours: float = 24.0

    # Canary settings
    canary_traffic_percent: float = 5.0
    canary_min_duration_hours: float = 1.0
    canary_steps: List[float] = field(default_factory=lambda: [5, 10, 25, 50, 100])

    # Promotion criteria
    min_alpha_improvement: float = 0.0
    max_latency_increase_pct: float = 20.0
    max_error_rate: float = 0.05
    required_metric_improvements: Dict[str, float] = field(default_factory=dict)

    # Rollback
    auto_rollback: bool = True
    rollback_error_threshold: float = 0.10
    rollback_latency_threshold_ms: float = 1000.0

    # Metadata
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "retrain_policy": self.retrain_policy.value,
            "promotion_policy": self.promotion_policy.value,
            "max_retrains_per_day": self.max_retrains_per_day,
            "canary_traffic_percent": self.canary_traffic_percent,
            "auto_rollback": self.auto_rollback,
            "enabled": self.enabled,
        }


# ---------------------------------------------------------------------------
# Policy Evaluator
# ---------------------------------------------------------------------------

class PolicyEvaluator:
    """Evaluates whether to retrain, promote, or rollback based on policies.

    Usage::

        evaluator = PolicyEvaluator()
        evaluator.set_policy(config)
        decision = evaluator.evaluate_retrain("nvda_model", metrics)
    """

    def __init__(self):
        self._policies: Dict[str, RetrainingPolicyConfig] = {}
        self._retrain_counts: Dict[str, List[str]] = {}  # model_id → [timestamps]

    def set_policy(self, config: RetrainingPolicyConfig) -> None:
        self._policies[config.model_id] = config

    def get_policy(self, model_id: str) -> Optional[RetrainingPolicyConfig]:
        return self._policies.get(model_id)

    # ------------------------------------------------------------------
    # Retrain evaluation
    # ------------------------------------------------------------------

    def evaluate_retrain(
        self,
        model_id: str,
        reason: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Evaluate if retraining should proceed.

        Returns:
            Dict with 'allowed', 'reason', 'constraints'.
        """
        policy = self._policies.get(model_id)
        if policy is None:
            return {"allowed": True, "reason": "no_policy", "constraints": []}

        if not policy.enabled:
            return {"allowed": False, "reason": "policy_disabled", "constraints": []}

        constraints = []

        # Check retrain rate limit
        today = datetime.now(timezone.utc).date().isoformat()
        today_retrains = sum(
            1 for ts in self._retrain_counts.get(model_id, [])
            if ts.startswith(today)
        )
        if today_retrains >= policy.max_retrains_per_day:
            constraints.append(f"daily_limit: {today_retrains}/{policy.max_retrains_per_day}")

        # Check minimum interval
        if model_id in self._retrain_counts:
            recent = self._retrain_counts[model_id][-1] if self._retrain_counts[model_id] else None
            if recent:
                last_time = datetime.fromisoformat(recent)
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
                if elapsed < policy.min_hours_between_retrains:
                    constraints.append(f"interval: {elapsed:.1f}h < {policy.min_hours_between_retrains}h")

        if constraints:
            return {"allowed": False, "reason": "constraints_violated", "constraints": constraints}

        # Record retrain
        if model_id not in self._retrain_counts:
            self._retrain_counts[model_id] = []
        self._retrain_counts[model_id].append(datetime.now(timezone.utc).isoformat())

        return {"allowed": True, "reason": reason, "constraints": []}

    # ------------------------------------------------------------------
    # Promotion evaluation
    # ------------------------------------------------------------------

    def evaluate_promotion(
        self,
        model_id: str,
        candidate_metrics: Dict[str, float],
        production_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Evaluate if candidate should be promoted.

        Returns:
            Dict with 'promote', 'method', 'reason', 'checks'.
        """
        policy = self._policies.get(model_id)
        if policy is None:
            return {"promote": True, "method": "all_at_once", "reason": "no_policy"}

        checks = {}

        # Error rate check
        error_rate = candidate_metrics.get("error_rate", 0.0)
        checks["error_rate"] = error_rate <= policy.max_error_rate

        # Latency check
        if production_metrics:
            prod_lat = production_metrics.get("avg_latency_ms", 0)
            cand_lat = candidate_metrics.get("avg_latency_ms", 0)
            if prod_lat > 0:
                latency_increase = (cand_lat - prod_lat) / prod_lat * 100
                checks["latency"] = latency_increase <= policy.max_latency_increase_pct

        # Metric improvements
        for metric, min_improvement in policy.required_metric_improvements.items():
            cand_val = candidate_metrics.get(metric)
            prod_val = production_metrics.get(metric) if production_metrics else None
            if cand_val is not None and prod_val is not None and prod_val != 0:
                improvement = (cand_val - prod_val) / abs(prod_val) * 100
                checks[metric] = improvement >= min_improvement

        all_passed = all(checks.values())

        # Determine promotion method
        if all_passed:
            if policy.promotion_policy == PromotionPolicy.AUTO_PROMOTE:
                method = "all_at_once"
            elif policy.promotion_policy == PromotionPolicy.AUTO_CANARY:
                method = "canary"
            elif policy.promotion_policy == PromotionPolicy.SHADOW_FIRST:
                method = "shadow"
            else:
                method = "approval_required"
        else:
            method = "none"

        return {
            "promote": all_passed,
            "method": method,
            "reason": "all_checks_passed" if all_passed else "checks_failed",
            "checks": checks,
        }

    # ------------------------------------------------------------------
    # Rollback evaluation
    # ------------------------------------------------------------------

    def should_rollback(
        self,
        model_id: str,
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Evaluate if production model should be rolled back."""
        policy = self._policies.get(model_id)
        if policy is None or not policy.auto_rollback:
            return {"rollback": False, "reason": "rollback_disabled"}

        reasons = []

        error_rate = metrics.get("error_rate", 0.0)
        if error_rate > policy.rollback_error_threshold:
            reasons.append(f"error_rate {error_rate} > {policy.rollback_error_threshold}")

        p99 = metrics.get("p99_latency_ms", 0.0)
        if p99 > policy.rollback_latency_threshold_ms:
            reasons.append(f"latency {p99}ms > {policy.rollback_latency_threshold_ms}ms")

        return {
            "rollback": len(reasons) > 0,
            "reason": "; ".join(reasons) if reasons else "no_issue",
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_policies(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._policies.values()]

    def get_retrain_stats(self, model_id: str) -> Dict[str, Any]:
        timestamps = self._retrain_counts.get(model_id, [])
        today = datetime.now(timezone.utc).date().isoformat()
        today_count = sum(1 for ts in timestamps if ts.startswith(today))
        return {
            "model_id": model_id,
            "total_retrains": len(timestamps),
            "retrains_today": today_count,
        }

    def __repr__(self) -> str:
        return f"PolicyEvaluator(policies={len(self._policies)})"
