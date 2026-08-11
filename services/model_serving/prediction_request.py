"""
ICYQuant Prediction Request — Standardized prediction request contract.

Defines the canonical request format for model inference,
ensuring consistency across all consumers: strategy agents,
risk engine, API gateways, and batch processors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid
import hashlib
import json


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RequestSource(str, Enum):
    """Origin of the prediction request."""
    STRATEGY = "strategy"
    RISK = "risk"
    AI_AGENT = "ai_agent"
    API = "api"
    BACKTEST = "backtest"
    RESEARCH = "research"
    MONITOR = "monitor"
    SCHEDULER = "scheduler"
    UNKNOWN = "unknown"


class RequestPriority(str, Enum):
    """Request priority for queue scheduling."""
    CRITICAL = "critical"     # Trading decisions
    HIGH = "high"             # Risk calculations
    NORMAL = "normal"         # Standard predictions
    LOW = "low"               # Research / backtest
    BACKGROUND = "background"  # Batch processing


class RequestFormat(str, Enum):
    """Feature format specification."""
    DICT = "dict"
    ARRAY = "array"
    DATAFRAME = "dataframe"
    TENSOR = "tensor"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FeatureSpec:
    """Specification of expected input features."""
    required_features: List[str] = field(default_factory=list)
    optional_features: List[str] = field(default_factory=list)
    feature_types: Dict[str, str] = field(default_factory=dict)
    allow_extra_features: bool = True

    def validate(self, features: Dict[str, Any]) -> List[str]:
        """Validate features against spec. Returns list of missing features."""
        missing = []
        for feat in self.required_features:
            if feat not in features:
                missing.append(feat)
        return missing


@dataclass
class PredictionRequest:
    """Standard prediction request.

    Attributes:
        request_id: Unique request identifier (auto-generated).
        model_id: Target model identifier.
        features: Input feature dictionary.
        version: Optional pinned model version.
        source: Request origin.
        priority: Request priority.
        timestamp: Request creation time.
        timeout_ms: Per-request timeout in milliseconds.
        metadata: Arbitrary key-value metadata.
        format: Feature format specification.
        validate_schema: Whether to validate against feature schema.
        trace_id: Distributed tracing identifier.
        parent_span_id: Parent span for tracing.
    """
    model_id: str
    features: Dict[str, Any]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: Optional[str] = None
    source: RequestSource = RequestSource.API
    priority: RequestPriority = RequestPriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timeout_ms: int = 5000
    metadata: Dict[str, Any] = field(default_factory=dict)
    format: RequestFormat = RequestFormat.DICT
    validate_schema: bool = True
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "version": self.version,
            "features": self.features,
            "source": self.source.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "timeout_ms": self.timeout_ms,
            "metadata": self.metadata,
            "format": self.format.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionRequest":
        """Deserialize from dictionary."""
        return cls(
            request_id=data.get("request_id", str(uuid.uuid4())),
            model_id=data["model_id"],
            features=data["features"],
            version=data.get("version"),
            source=RequestSource(data.get("source", "api")),
            priority=RequestPriority(data.get("priority", "normal")),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            timeout_ms=data.get("timeout_ms", 5000),
            metadata=data.get("metadata", {}),
        )

    def content_hash(self) -> str:
        """Hash the feature content for deduplication."""
        feature_json = json.dumps(self.features, sort_keys=True, default=str)
        return hashlib.sha256(feature_json.encode()).hexdigest()[:16]

    def elapsed_ms(self) -> float:
        """Milliseconds since request creation."""
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now(timezone.utc) - created).total_seconds() * 1000

    def create_child(self, model_id: str, features: Dict[str, Any]) -> "PredictionRequest":
        """Create a child request inheriting tracing context."""
        return PredictionRequest(
            model_id=model_id,
            features=features,
            version=self.version,
            source=self.source,
            priority=self.priority,
            timeout_ms=self.timeout_ms,
            trace_id=self.trace_id,
            parent_span_id=self.request_id,
        )

    def __repr__(self) -> str:
        return (
            f"PredictionRequest(id={self.request_id[:8]}.., "
            f"model={self.model_id}, priority={self.priority.value})"
        )


# ---------------------------------------------------------------------------
# Batch request
# ---------------------------------------------------------------------------

@dataclass
class BatchPredictionRequest:
    """Batch prediction request for multiple samples.

    Supports efficient batch processing with shared model context.
    """
    model_id: str
    features_list: List[Dict[str, Any]]
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: Optional[str] = None
    source: RequestSource = RequestSource.RESEARCH
    priority: RequestPriority = RequestPriority.BACKGROUND
    timeout_ms: int = 30000
    max_batch_size: int = 256
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def batch_size(self) -> int:
        return len(self.features_list)

    def split_batches(self) -> List[Dict[str, Any]]:
        """Split into sub-batches respecting max_batch_size.

        Returns:
            List of batch spec dicts.
        """
        batches = []
        for i in range(0, len(self.features_list), self.max_batch_size):
            chunk = self.features_list[i:i + self.max_batch_size]
            batches.append({
                "model_id": self.model_id,
                "features_list": chunk,
                "version": self.version,
                "batch_id": f"{self.batch_id}_{i // self.max_batch_size}",
            })
        return batches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "model_id": self.model_id,
            "version": self.version,
            "batch_size": self.batch_size,
            "features_list": self.features_list,
            "source": self.source.value,
            "timeout_ms": self.timeout_ms,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"BatchPredictionRequest(model={self.model_id}, size={self.batch_size})"
