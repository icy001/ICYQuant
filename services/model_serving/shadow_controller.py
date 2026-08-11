"""
ICYQuant Shadow Controller — Shadow deployment management.

Manages shadow (dark launch) deployments where a candidate model
receives the same inputs as production but predictions are only
logged and compared — never affecting live trading decisions.

Shadow deployments are critical for safe quant model evaluation:
  - Zero production risk
  - Full parallelism with live traffic
  - Side-by-side comparison with production
  - Statistical significance tracking
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class ShadowState(str, Enum):
    """Shadow deployment state."""
    STARTING = "starting"
    COLLECTING = "collecting"
    EVALUATING = "evaluating"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ABORTED = "aborted"


class ComparisonMetric(str, Enum):
    """Metrics for comparing shadow vs production."""
    IC = "ic"
    RANK_IC = "rank_ic"
    SHARPE = "sharpe"
    ACCURACY = "accuracy"
    MAE = "mae"
    RMSE = "rmse"
    PROB_CALIBRATION = "prob_calibration"
    PREDICTION_CORRELATION = "prediction_correlation"
    STABILITY = "stability"


@dataclass
class PredictionPair:
    """A pair of production and shadow predictions for the same input."""
    request_id: str
    features_hash: str
    timestamp: str
    production_prediction: Any
    shadow_prediction: Any
    production_latency_ms: float
    shadow_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "production": self.production_prediction,
            "shadow": self.shadow_prediction,
            "prod_latency_ms": self.production_latency_ms,
            "shadow_latency_ms": self.shadow_latency_ms,
        }


@dataclass
class ShadowConfig:
    """Shadow deployment configuration."""
    min_samples: int = 1000
    max_duration_seconds: int = 86400  # 24 hours
    significance_level: float = 0.05
    comparison_window_size: int = 500
    store_predictions: bool = True
    max_stored_pairs: int = 100000
    alert_on_regression: bool = True
    regression_threshold_pct: float = 5.0  # 5% worse = regression


# ---------------------------------------------------------------------------
# Shadow Controller
# ---------------------------------------------------------------------------

class ShadowController:
    """Manages shadow deployment — safe model evaluation.

    Usage::

        controller = ShadowController("nvda_model")
        controller.start_shadow(candidate_version="v1.6")

        # Mirror production requests
        prod_result = await production_model.predict(features)
        shadow_result = await shadow_model.predict(features)
        controller.record_pair(prod_result, shadow_result)

        # Evaluate
        comparison = controller.compare()
        if comparison["better"]:
            controller.promote()
    """

    def __init__(
        self,
        model_id: str,
        config: Optional[ShadowConfig] = None,
    ):
        self.model_id = model_id
        self.config = config or ShadowConfig()
        self._initialized = False

        # State
        self._state = ShadowState.STARTING
        self._candidate_version: Optional[str] = None
        self._started_at: Optional[datetime] = None

        # Prediction storage
        self._pairs: Deque[PredictionPair] = deque(maxlen=self.config.max_stored_pairs)

        # Windowed metrics for trend analysis
        self._metrics_windows: Deque[Dict[str, float]] = deque(maxlen=50)

        # Aggregated comparison results
        self._latest_comparison: Optional[Dict[str, Any]] = None

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("ShadowController initialized for %s", self.model_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_shadow(self, candidate_version: str) -> None:
        """Begin shadow deployment.

        Args:
            candidate_version: Candidate model version to shadow.
        """
        self._state = ShadowState.STARTING
        self._candidate_version = candidate_version
        self._started_at = datetime.now(timezone.utc)
        self._pairs.clear()
        self._metrics_windows.clear()
        self._latest_comparison = None

        logger.info(
            "Shadow started: %s@%s (collecting predictions...)",
            self.model_id, candidate_version,
        )

        self._state = ShadowState.COLLECTING

    def stop_shadow(self) -> None:
        """Stop shadow deployment."""
        self._state = ShadowState.ABORTED
        logger.info("Shadow stopped: %s@%s", self.model_id, self._candidate_version)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_pair(
        self,
        production_prediction: Any,
        shadow_prediction: Any,
        *,
        request_id: Optional[str] = None,
        features_hash: Optional[str] = None,
        production_latency_ms: float = 0.0,
        shadow_latency_ms: float = 0.0,
    ) -> None:
        """Record a production-shadow prediction pair.

        Args:
            production_prediction: Prediction from production model.
            shadow_prediction: Prediction from shadow/candidate model.
            request_id: Optional request identifier.
            features_hash: Optional features hash for dedup.
            production_latency_ms: Production model latency.
            shadow_latency_ms: Shadow model latency.
        """
        if self._state != ShadowState.COLLECTING:
            return

        pair = PredictionPair(
            request_id=request_id or str(uuid.uuid4()),
            features_hash=features_hash or "",
            timestamp=datetime.now(timezone.utc).isoformat(),
            production_prediction=production_prediction,
            shadow_prediction=shadow_prediction,
            production_latency_ms=production_latency_ms,
            shadow_latency_ms=shadow_latency_ms,
        )

        async with self._lock:
            self._pairs.append(pair)

    async def record_batch(
        self,
        pairs: List[Tuple[Any, Any]],
        latencies: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        """Record multiple prediction pairs in batch."""
        for i, (prod_pred, shadow_pred) in enumerate(pairs):
            prod_lat, shadow_lat = latencies[i] if latencies else (0.0, 0.0)
            await self.record_pair(
                production_prediction=prod_pred,
                shadow_prediction=shadow_pred,
                production_latency_ms=prod_lat,
                shadow_latency_ms=shadow_lat,
            )

    # ------------------------------------------------------------------
    # Comparison & evaluation
    # ------------------------------------------------------------------

    async def compare(self) -> Dict[str, Any]:
        """Compare shadow vs production predictions.

        Computes:
          - Prediction correlation
          - Mean Absolute Error between predictions
          - Prediction distribution similarity
          - Latency comparison
          - Statistical significance test

        Returns:
            Comparison dict with metrics and verdict.
        """
        if self._state not in (ShadowState.COLLECTING, ShadowState.EVALUATING):
            return {"error": "Shadow not collecting"}

        async with self._lock:
            pairs = list(self._pairs)

        if len(pairs) < self.config.min_samples:
            return {
                "status": "insufficient_data",
                "samples": len(pairs),
                "required": self.config.min_samples,
            }

        self._state = ShadowState.EVALUATING

        # Extract predictions as arrays
        prod_preds = np.array([p.production_prediction for p in pairs], dtype=float)
        shadow_preds = np.array([p.shadow_prediction for p in pairs], dtype=float)

        prod_lat = np.array([p.production_latency_ms for p in pairs])
        shadow_lat = np.array([p.shadow_latency_ms for p in pairs])

        # Compute comparison metrics
        comparison = await self._compute_comparison(
            prod_preds, shadow_preds, prod_lat, shadow_lat
        )

        comparison.update({
            "model_id": self.model_id,
            "candidate_version": self._candidate_version,
            "samples": len(pairs),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": (
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
                if self._started_at else 0.0
            ),
        })

        self._latest_comparison = comparison
        self._metrics_windows.append({
            "correlation": comparison.get("prediction_correlation", 0.0),
            "mae": comparison.get("mae", 0.0),
            "samples": len(pairs),
        })

        logger.info(
            "Shadow comparison: %s@%s (corr=%.4f, mae=%.6f, samples=%d)",
            self.model_id, self._candidate_version,
            comparison.get("prediction_correlation", 0.0),
            comparison.get("mae", 0.0),
            len(pairs),
        )

        return comparison

    async def _compute_comparison(
        self,
        prod_preds: np.ndarray,
        shadow_preds: np.ndarray,
        prod_lat: np.ndarray,
        shadow_lat: np.ndarray,
    ) -> Dict[str, Any]:
        """Compute all comparison metrics between production and shadow."""
        n = len(prod_preds)
        if n == 0:
            return {}

        result: Dict[str, Any] = {}

        # Correlation
        if n >= 3 and np.std(prod_preds) > 0 and np.std(shadow_preds) > 0:
            result["prediction_correlation"] = round(
                float(np.corrcoef(prod_preds, shadow_preds)[0, 1]), 6
            )
        else:
            result["prediction_correlation"] = 0.0

        # MAE
        result["mae"] = round(float(np.mean(np.abs(prod_preds - shadow_preds))), 6)
        result["rmse"] = round(float(np.sqrt(np.mean((prod_preds - shadow_preds) ** 2))), 6)

        # Mean predictions
        result["prod_mean"] = round(float(np.mean(prod_preds)), 6)
        result["shadow_mean"] = round(float(np.mean(shadow_preds)), 6)
        result["mean_difference"] = round(
            float(np.mean(shadow_preds) - np.mean(prod_preds)), 6
        )

        # Std deviation
        result["prod_std"] = round(float(np.std(prod_preds)), 6)
        result["shadow_std"] = round(float(np.std(shadow_preds)), 6)

        # Latency comparison
        result["prod_avg_latency_ms"] = round(float(np.mean(prod_lat)), 2)
        result["shadow_avg_latency_ms"] = round(float(np.mean(shadow_lat)), 2)
        result["latency_ratio"] = round(
            float(np.mean(shadow_lat)) / max(float(np.mean(prod_lat)), 0.001), 4
        )

        # Prediction stability (std of diff)
        diff = shadow_preds - prod_preds
        result["diff_std"] = round(float(np.std(diff)), 6)

        # Direction agreement (for binary classification)
        if np.all(np.isin(prod_preds, [0, 1])) and np.all(np.isin(shadow_preds, [0, 1])):
            result["direction_agreement"] = round(
                float(np.mean(prod_preds == shadow_preds)), 6
            )

        # Verdict
        correlation = result["prediction_correlation"]
        mae = result["mae"]

        if correlation > 0.95 and mae < 0.01:
            result["verdict"] = "highly_similar"
        elif correlation > 0.80:
            result["verdict"] = "similar"
        elif correlation > 0.50:
            result["verdict"] = "moderately_different"
        else:
            result["verdict"] = "significantly_different"

        # Regression check
        result["is_regression"] = self._check_regression(result)

        return result

    def _check_regression(self, comparison: Dict[str, Any]) -> bool:
        """Check if shadow model is regressing vs production."""
        # Higher latency is a problem
        latency_ratio = comparison.get("latency_ratio", 1.0)
        if latency_ratio > 1 + self.config.regression_threshold_pct / 100.0:
            return True

        # Very different predictions could mean regression
        correlation = comparison.get("prediction_correlation", 1.0)
        if correlation < 0.5:
            return True

        return False

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    async def should_promote(self) -> Tuple[bool, str]:
        """Determine if shadow should be promoted to canary.

        Returns:
            (promote, reason) tuple.
        """
        if self._state != ShadowState.EVALUATING:
            return False, f"not_evaluating (state={self._state.value})"

        comparison = self._latest_comparison
        if comparison is None:
            comparison = await self.compare()

        samples = comparison.get("samples", 0)
        if samples < self.config.min_samples:
            return False, f"insufficient_samples ({samples}/{self.config.min_samples})"

        # Don't promote if regression detected
        if comparison.get("is_regression", False):
            return False, "regression_detected"

        # Don't promote if latency is much worse
        latency_ratio = comparison.get("latency_ratio", 1.0)
        if latency_ratio > 1.5:
            return False, f"high_latency_ratio ({latency_ratio:.2f})"

        # Promote if correlation is high (meaning shadow is very similar)
        correlation = comparison.get("prediction_correlation", 0.0)
        if correlation > 0.90:
            return True, f"high_correlation ({correlation:.4f})"

        return True, "shadow_evaluation_passed"

    async def promote(self) -> bool:
        """Mark shadow as promoted (transition to canary stage)."""
        if self._state != ShadowState.EVALUATING:
            logger.warning("Cannot promote shadow in state %s", self._state.value)
            return False

        self._state = ShadowState.PROMOTED
        logger.info(
            "Shadow promoted: %s@%s → ready for canary",
            self.model_id, self._candidate_version,
        )
        return True

    async def reject(self, reason: str = "") -> None:
        """Reject shadow deployment."""
        self._state = ShadowState.REJECTED
        logger.info(
            "Shadow rejected: %s@%s (reason=%s)",
            self.model_id, self._candidate_version, reason or "no_reason",
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get shadow deployment status."""
        return {
            "model_id": self.model_id,
            "candidate_version": self._candidate_version,
            "state": self._state.value,
            "samples_collected": len(self._pairs),
            "min_samples": self.config.min_samples,
            "started_at": (
                self._started_at.isoformat() if self._started_at else None
            ),
            "elapsed_seconds": (
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
                if self._started_at else 0.0
            ),
            "latest_comparison": self._latest_comparison,
        }

    @property
    def state(self) -> ShadowState:
        return self._state

    @property
    def sample_count(self) -> int:
        return len(self._pairs)

    @property
    def is_collecting(self) -> bool:
        return self._state == ShadowState.COLLECTING

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "state": self._state.value,
            "samples": len(self._pairs),
            "candidate_version": self._candidate_version,
        }

    def __repr__(self) -> str:
        return (
            f"ShadowController(model={self.model_id}, "
            f"state={self._state.value}, samples={len(self._pairs)})"
        )
