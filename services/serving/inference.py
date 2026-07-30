"""Inference Engine — unified online and batch prediction.

Supports multiple model frameworks (LightGBM, XGBoost, CatBoost, ONNX, PyTorch),
real-time single predictions and batch prediction with configurable batching.

Usage::

    engine = InferenceEngine(config=InferenceConfig(batch_size=64))
    result = engine.predict(model, features)        # single
    results = engine.predict_batch(model, df)        # batch
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


class PredictionMode(str, Enum):
    """Prediction mode."""
    ONLINE = "online"
    BATCH = "batch"
    STREAMING = "streaming"


@dataclass
class InferenceConfig:
    """Inference engine configuration.

    Attributes:
        batch_size: Max batch size for batch predictions.
        timeout_ms: Max prediction timeout in milliseconds.
        enable_confidence: Whether to compute confidence scores.
        num_threads: Number of threads for parallel inference.
        warmup_iterations: Number of warmup calls before serving.
        enable_input_validation: Validate input feature shapes.
    """

    batch_size: int = 64
    timeout_ms: int = 500
    enable_confidence: bool = True
    num_threads: int = 4
    warmup_iterations: int = 10
    enable_input_validation: bool = True


@dataclass
class BatchInferenceRequest:
    """A batch prediction request.

    Attributes:
        symbols: List of symbols to predict for.
        features_list: List of feature dicts, one per symbol.
        model_name: Optional model name override.
        request_id: Unique request identifier.
    """

    symbols: List[str] = field(default_factory=list)
    features_list: List[Dict[str, float]] = field(default_factory=list)
    model_name: str = ""
    request_id: str = ""

    def __post_init__(self):
        if not self.request_id:
            import uuid
            self.request_id = str(uuid.uuid4())[:8]


@dataclass
class BatchInferenceResult:
    """Batch prediction results.

    Attributes:
        predictions: List of prediction values.
        confidences: List of confidence scores (if available).
        symbols: List of symbols in same order.
        latency_ms: Total batch latency.
        model_name: Model that produced predictions.
        request_id: Matching request id.
    """

    predictions: List[float] = field(default_factory=list)
    confidences: List[Optional[float]] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    model_name: str = ""
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictions": self.predictions,
            "confidences": self.confidences,
            "symbols": self.symbols,
            "latency_ms": self.latency_ms,
            "model_name": self.model_name,
            "request_id": self.request_id,
        }


class InferenceEngine:
    """Unified inference engine for online and batch predictions.

    Handles prediction for multiple model frameworks with optional
    confidence scoring and input validation.
    """

    def __init__(self, config: Optional[InferenceConfig] = None):
        self.config = config or InferenceConfig()
        self._warmed_up: Dict[str, bool] = {}

    def predict(
        self,
        model: Any,
        features: Dict[str, float],
        model_name: str = "",
    ) -> Tuple[float, Optional[float]]:
        """Single online prediction.

        Args:
            model: Loaded model object with predict() method.
            features: Feature name -> value mapping.
            model_name: Model identifier (for warmup tracking).

        Returns:
            (prediction, confidence) tuple.
        """
        if self.config.enable_input_validation:
            self._validate_features(features)

        start = time.perf_counter()

        try:
            # Convert features to model-compatible format
            if hasattr(model, 'predict_proba') and self.config.enable_confidence:
                # Tree models with probability output
                feature_array = self._features_to_array(features, getattr(model, 'feature_names_', None))
                proba = model.predict_proba(feature_array)[0]
                prediction = float(proba[1]) if len(proba) > 1 else float(proba[0])
                confidence = float(max(proba))
            elif hasattr(model, 'predict'):
                feature_array = self._features_to_array(features, getattr(model, 'feature_names_', None))
                raw = model.predict(feature_array)
                prediction = float(raw[0]) if hasattr(raw, '__iter__') else float(raw)
                confidence = self._estimate_confidence(model, features, prediction)
            else:
                prediction = float(model.predict(features))
                confidence = None
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            if latency > self.config.timeout_ms:
                raise TimeoutError(f"Prediction timeout: {latency:.0f}ms > {self.config.timeout_ms}ms")
            raise RuntimeError(f"Inference failed: {e}") from e

        if self.config.enable_confidence and confidence is None:
            confidence = 0.5  # default neutral confidence

        return prediction, confidence

    def predict_batch(
        self,
        model: Any,
        features_list: List[Dict[str, float]],
        symbols: Optional[List[str]] = None,
        model_name: str = "",
    ) -> BatchInferenceResult:
        """Batch prediction for multiple samples.

        Args:
            model: Loaded model object.
            features_list: List of feature dicts.
            symbols: Optional list of symbols (uses index if None).
            model_name: Model identifier.

        Returns:
            BatchInferenceResult with predictions and confidences.
        """
        start = time.perf_counter()
        request = BatchInferenceRequest(
            symbols=symbols or [f"sample_{i}" for i in range(len(features_list))],
            features_list=features_list,
            model_name=model_name,
        )

        predictions: List[float] = []
        confidences: List[Optional[float]] = []

        for features in features_list:
            pred, conf = self.predict(model, features, model_name)
            predictions.append(pred)
            confidences.append(conf)

        latency = (time.perf_counter() - start) * 1000

        return BatchInferenceResult(
            predictions=predictions,
            confidences=confidences,
            symbols=request.symbols,
            latency_ms=round(latency, 3),
            model_name=model_name,
            request_id=request.request_id,
        )

    def warmup(self, model: Any, sample_features: Dict[str, float], model_name: str = "") -> None:
        """Run warmup iterations to pre-JIT compile and cache model internals.

        Args:
            model: Loaded model.
            sample_features: Representative feature dict.
            model_name: Model identifier.
        """
        if model_name in self._warmed_up:
            return

        for _ in range(self.config.warmup_iterations):
            try:
                self.predict(model, sample_features, model_name)
            except Exception:
                pass

        self._warmed_up[model_name] = True

    # ---- internal helpers ----

    def _features_to_array(self, features: Dict[str, float], feature_names: Optional[List[str]]) -> np.ndarray:
        """Convert feature dict to ordered numpy array."""
        if feature_names:
            ordered = [features.get(name, 0.0) for name in feature_names]
        else:
            ordered = list(features.values())
        return np.array([ordered], dtype=np.float64)

    def _validate_features(self, features: Dict[str, float]) -> None:
        """Validate input features."""
        if not features:
            raise ValueError("Empty feature dict")
        for name, value in features.items():
            if not isinstance(value, (int, float)):
                raise TypeError(f"Feature '{name}' must be numeric, got {type(value).__name__}")
            if np.isnan(value) or np.isinf(value):
                raise ValueError(f"Feature '{name}' is NaN or Inf")

    def _estimate_confidence(
        self,
        model: Any,
        features: Dict[str, float],
        prediction: float,
    ) -> Optional[float]:
        """Estimate prediction confidence when predict_proba not available."""
        # Use tree ensemble stddev if available
        if hasattr(model, 'predict') and hasattr(model, 'estimators_'):
            try:
                estimator_preds = []
                feature_array = self._features_to_array(features, getattr(model, 'feature_names_', None))
                for est in model.estimators_:
                    p = est.predict(feature_array)
                    estimator_preds.append(float(p[0]) if hasattr(p, '__iter__') else float(p))
                if len(estimator_preds) > 1:
                    std = float(np.std(estimator_preds))
                    # Normalize: std=0 → 1.0, large std → 0.0
                    confidence = 1.0 / (1.0 + std)
                    return round(confidence, 4)
            except Exception:
                pass
        return None
