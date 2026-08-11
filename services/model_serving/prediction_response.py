"""
ICYQuant Prediction Response — Standardized prediction output contract.

Defines the canonical response format returned by model inference,
ensuring consumers can reliably interpret predictions regardless
of model backend or version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json
import numpy as np


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResponseStatus(str, Enum):
    """Prediction response status."""
    SUCCESS = "success"
    FEATURE_ERROR = "feature_error"
    MODEL_NOT_FOUND = "model_not_found"
    MODEL_NOT_READY = "model_not_ready"
    INFERENCE_TIMEOUT = "inference_timeout"
    INFERENCE_ERROR = "inference_error"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"


class PredictionType(str, Enum):
    """Type of prediction output."""
    SCALAR = "scalar"               # Single regression value
    CLASSIFICATION = "classification"  # Class probabilities or label
    RANKING = "ranking"             # Cross-sectional ranking score
    MULTI_OUTPUT = "multi_output"   # Multiple prediction targets
    UNCERTAINTY = "uncertainty"     # Prediction with uncertainty bounds


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PredictionOutput:
    """Structured prediction with metadata."""
    value: Any
    type: PredictionType = PredictionType.SCALAR
    confidence: Optional[float] = None
    upper_bound: Optional[float] = None
    lower_bound: Optional[float] = None
    class_probabilities: Optional[Dict[str, float]] = None
    shap_values: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "value": self._serialize(self.value),
            "type": self.type.value,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.upper_bound is not None:
            result["upper_bound"] = self.upper_bound
        if self.lower_bound is not None:
            result["lower_bound"] = self.lower_bound
        if self.class_probabilities:
            result["class_probabilities"] = self.class_probabilities
        if self.shap_values:
            result["shap_values"] = self.shap_values
        return result

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, (np.ndarray,)):
            return value.tolist()
        if isinstance(value, (np.floating, np.integer)):
            return float(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        return value


@dataclass
class PredictionResponse:
    """Standard prediction response.

    Attributes:
        request_id: Echo of the original request ID.
        model_id: Model that served the prediction.
        model_version: Exact model version used.
        prediction: Structured prediction output.
        status: Response status.
        timestamp: Response creation time.
        inference_latency_ms: Inference execution time.
        feature_version: Feature store version used.
        trace_id: Distributed tracing identifier.
        metadata: Arbitrary additional metadata.
        warnings: Non-fatal warnings about the prediction.
    """
    request_id: str
    model_id: str
    model_version: str
    prediction: PredictionOutput
    status: ResponseStatus = ResponseStatus.SUCCESS
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    inference_latency_ms: float = 0.0
    feature_version: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        result: Dict[str, Any] = {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "prediction": self.prediction.to_dict(),
            "status": self.status.value,
            "timestamp": self.timestamp,
            "inference_latency_ms": round(self.inference_latency_ms, 4),
        }
        if self.feature_version:
            result["feature_version"] = self.feature_version
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.metadata:
            result["metadata"] = self.metadata
        if self.warnings:
            result["warnings"] = self.warnings
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionResponse":
        """Deserialize from dictionary."""
        pred_data = data["prediction"]
        prediction = PredictionOutput(
            value=pred_data.get("value"),
            type=PredictionType(pred_data.get("type", "scalar")),
            confidence=pred_data.get("confidence"),
            upper_bound=pred_data.get("upper_bound"),
            lower_bound=pred_data.get("lower_bound"),
            class_probabilities=pred_data.get("class_probabilities"),
            shap_values=pred_data.get("shap_values"),
        )
        return cls(
            request_id=data["request_id"],
            model_id=data["model_id"],
            model_version=data["model_version"],
            prediction=prediction,
            status=ResponseStatus(data.get("status", "success")),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            inference_latency_ms=data.get("inference_latency_ms", 0.0),
            feature_version=data.get("feature_version"),
            trace_id=data.get("trace_id"),
            metadata=data.get("metadata", {}),
            warnings=data.get("warnings", []),
        )

    @classmethod
    def error_response(
        cls,
        request_id: str,
        model_id: str,
        status: ResponseStatus,
        error_message: str,
    ) -> "PredictionResponse":
        """Factory for error responses."""
        return cls(
            request_id=request_id,
            model_id=model_id,
            model_version="unknown",
            prediction=PredictionOutput(value=None),
            status=status,
            warnings=[error_message],
        )

    @property
    def is_success(self) -> bool:
        return self.status == ResponseStatus.SUCCESS

    def summary(self) -> str:
        """One-line summary for logging."""
        return (
            f"[{self.status.value}] {self.model_id}@{self.model_version} "
            f"→ {self.prediction.value} ({self.inference_latency_ms:.2f}ms)"
        )

    def __repr__(self) -> str:
        return (
            f"PredictionResponse(model={self.model_id}@{self.model_version}, "
            f"status={self.status.value}, latency={self.inference_latency_ms:.1f}ms)"
        )


# ---------------------------------------------------------------------------
# Batch response
# ---------------------------------------------------------------------------

@dataclass
class BatchPredictionResponse:
    """Response for a batch prediction request."""
    batch_id: str
    model_id: str
    model_version: str
    responses: List[PredictionResponse] = field(default_factory=list)
    total_latency_ms: float = 0.0
    success_count: int = 0
    error_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def batch_size(self) -> int:
        return len(self.responses)

    @property
    def success_rate(self) -> float:
        total = self.batch_size
        return self.success_count / max(total, 1)

    @property
    def avg_latency_ms(self) -> float:
        if not self.responses:
            return 0.0
        return sum(r.inference_latency_ms for r in self.responses) / len(self.responses)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "batch_size": self.batch_size,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 4),
            "total_latency_ms": round(self.total_latency_ms, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 4),
            "timestamp": self.timestamp,
            "responses": [r.to_dict() for r in self.responses],
        }

    def __repr__(self) -> str:
        return (
            f"BatchPredictionResponse(model={self.model_id}, "
            f"size={self.batch_size}, success_rate={self.success_rate:.1%})"
        )


# ---------------------------------------------------------------------------
# Model prediction log entry
# ---------------------------------------------------------------------------

@dataclass
class PredictionLog:
    """Immutable prediction log for audit trail."""
    request_id: str
    model_id: str
    model_version: str
    features_hash: str
    prediction_value: Any
    confidence: Optional[float]
    status: ResponseStatus
    latency_ms: float
    feature_version: Optional[str]
    timestamp: str
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "features_hash": self.features_hash,
            "prediction_value": PredictionOutput._serialize(self.prediction_value),
            "confidence": self.confidence,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 4),
            "feature_version": self.feature_version,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }
