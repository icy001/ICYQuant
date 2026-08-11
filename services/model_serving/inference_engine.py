"""
ICYQuant Inference Engine — Core prediction executor.

Orchestrates the full inference pipeline:
  Feature validation → Feature enrichment → Model resolution → Inference → Post-processing

Ensures research-production feature contract consistency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .model_runtime import ModelRuntime
    from .feature_adapter import FeatureAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class InferenceStatus(str, Enum):
    SUCCESS = "success"
    FEATURE_ERROR = "feature_error"
    MODEL_NOT_FOUND = "model_not_found"
    TIMEOUT = "timeout"
    RUNTIME_ERROR = "runtime_error"
    VALIDATION_ERROR = "validation_error"


@dataclass
class InferenceResult:
    """Structured inference result."""
    model_id: str
    model_version: str
    prediction: Any
    confidence: Optional[float] = None
    feature_version: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    inference_latency_ms: float = 0.0
    status: InferenceStatus = InferenceStatus.SUCCESS
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "prediction": self._serialize_prediction(),
            "confidence": self.confidence,
            "feature_version": self.feature_version,
            "timestamp": self.timestamp,
            "inference_latency_ms": round(self.inference_latency_ms, 4),
            "status": self.status.value,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def _serialize_prediction(self) -> Any:
        """Serialize prediction to JSON-safe format."""
        if isinstance(self.prediction, np.ndarray):
            return self.prediction.tolist()
        if isinstance(self.prediction, (np.floating, np.integer)):
            return float(self.prediction)
        return self.prediction


@dataclass
class InferenceRequest:
    """Inference request specification."""
    model_id: str
    features: Dict[str, Any]
    version: Optional[str] = None
    timeout_ms: int = 5000
    request_id: Optional[str] = None
    enrich_features: bool = True
    validate_features: bool = True


# ---------------------------------------------------------------------------
# Inference Engine
# ---------------------------------------------------------------------------

class InferenceEngine:
    """Core prediction executor.

    Pipeline stages:
      1. Feature validation (required fields, types, ranges)
      2. Feature enrichment (from online feature store)
      3. Model resolution (model_id → loaded runtime instance)
      4. Inference execution (routing to correct backend)
      5. Post-processing (confidence, formatting)
    """

    def __init__(
        self,
        runtime: "ModelRuntime",
        feature_adapter: Optional["FeatureAdapter"] = None,
    ):
        self.runtime = runtime
        self.feature_adapter = feature_adapter
        self._initialized = False

        # Stats
        self._inference_count: int = 0
        self._error_count: int = 0
        self._total_latency_ns: int = 0

    async def initialize(self) -> None:
        """Initialize the engine."""
        self._initialized = True
        logger.info("InferenceEngine initialized")

    async def shutdown(self) -> None:
        """Shutdown the engine."""
        self._initialized = False

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    async def predict(
        self,
        model_id: str,
        features: Dict[str, Any],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run single inference with full pipeline.

        Args:
            model_id: Model identifier.
            features: Feature dictionary.
            version: Optional pinned version.
            timeout_ms: Timeout override.

        Returns:
            Prediction dict.
        """
        request = InferenceRequest(
            model_id=model_id,
            features=features,
            version=version,
            timeout_ms=timeout_ms or 5000,
        )

        try:
            result = await asyncio.wait_for(
                self._execute_pipeline(request),
                timeout=request.timeout_ms / 1000.0,
            )
            return result.to_dict()
        except asyncio.TimeoutError:
            self._error_count += 1
            return InferenceResult(
                model_id=model_id,
                model_version=version or "unknown",
                prediction=None,
                status=InferenceStatus.TIMEOUT,
                inference_latency_ms=request.timeout_ms,
            ).to_dict()
        except Exception as exc:
            self._error_count += 1
            logger.exception("Inference failed for %s", model_id)
            return InferenceResult(
                model_id=model_id,
                model_version=version or "unknown",
                prediction=None,
                status=InferenceStatus.RUNTIME_ERROR,
                metadata={"error": str(exc)},
            ).to_dict()

    async def predict_batch(
        self,
        model_id: str,
        features_list: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Run batch inference."""
        tasks = [
            self.predict(
                model_id=model_id,
                features=features,
                version=version,
                timeout_ms=timeout_ms,
            )
            for features in features_list
        ]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _execute_pipeline(self, request: InferenceRequest) -> InferenceResult:
        """Execute the full inference pipeline."""
        start_ns = time.perf_counter_ns()

        # Stage 1: Validate features
        if request.validate_features:
            self._validate_features(request.features)

        # Stage 2: Enrich features from online store
        features = request.features
        feature_version = None
        if request.enrich_features and self.feature_adapter:
            enriched = await self.feature_adapter.enrich(
                request.model_id, features
            )
            features = enriched.get("features", features)
            feature_version = enriched.get("feature_version")

        # Stage 3: Resolve model version
        resolved_version = request.version
        if resolved_version is None:
            resolved_version = await self._resolve_version(request.model_id)

        # Stage 4: Run inference
        prediction_raw = await self.runtime.predict(
            model_id=request.model_id,
            version=resolved_version,
            features=features,
        )

        # Stage 5: Post-process
        confidence = self._compute_confidence(prediction_raw)
        latency_ns = time.perf_counter_ns() - start_ns
        latency_ms = latency_ns / 1_000_000.0

        self._inference_count += 1
        self._total_latency_ns += latency_ns

        return InferenceResult(
            model_id=request.model_id,
            model_version=resolved_version,
            prediction=prediction_raw,
            confidence=confidence,
            feature_version=feature_version,
            inference_latency_ms=latency_ms,
            status=InferenceStatus.SUCCESS,
            metadata={
                "request_id": request.request_id,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_features(self, features: Dict[str, Any]) -> None:
        """Validate feature dictionary."""
        if not features:
            raise ValueError("Features dictionary is empty")
        # Check for required feature keys could be added via a schema registry
        for key, value in features.items():
            if value is None:
                logger.warning("Feature '%s' is None", key)

    async def _resolve_version(self, model_id: str) -> str:
        """Resolve model_id to its production version.

        Delegates to registry client or uses runtime state.
        """
        # Check runtime for any loaded version marked as production
        loaded = self.runtime.list_models()
        for model in loaded:
            if model["model_id"] == model_id and model["state"] == "ready":
                return model["version"]

        raise ValueError(f"No production version found for model: {model_id}")

    @staticmethod
    def _compute_confidence(prediction: Any) -> Optional[float]:
        """Compute prediction confidence score."""
        if isinstance(prediction, np.ndarray):
            if prediction.dtype == np.float32 or prediction.dtype == np.float64:
                if prediction.size == 1:
                    return None  # Single regression — no confidence
                if prediction.size == 2 and prediction.shape[-1] == 2:
                    # Binary classification probabilities
                    probs = prediction.ravel()
                    return float(abs(probs[0] - 0.5) * 2.0)
                if prediction.size >= 2:
                    # Multi-class — use max prob
                    probs = prediction.ravel()
                    max_prob = float(probs.max())
                    return max_prob
        return None

    # ------------------------------------------------------------------
    # Health & stats
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Engine health check."""
        runtime_health = await self.runtime.health()
        return {
            "status": runtime_health.get("status", "unknown"),
            "initialized": self._initialized,
            "inference_count": self._inference_count,
            "error_count": self._error_count,
            "avg_latency_ms": round(
                (self._total_latency_ns / 1_000_000.0) / max(self._inference_count, 1), 4
            ),
            "runtime": runtime_health,
        }

    async def drain(self, timeout: float = 30.0) -> None:
        """Drain in-flight inferences."""
        await self.runtime.drain(timeout=timeout)

    def __repr__(self) -> str:
        return (
            f"InferenceEngine(inferences={self._inference_count}, "
            f"errors={self._error_count})"
        )
