"""
Experiment model definitions.

Defines the core data structures for A/B
testing experiments including experiment
configuration, lifecycle states, and results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class ExperimentStatus:
    """Experiment lifecycle status constants."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Experiment:
    """
    An A/B testing experiment.

    Defines an experiment with variants,
    traffic allocation, and lifecycle management.

    Attributes:
        experiment_id: Unique experiment identifier.
        name: Human-readable name.
        feature_key: Associated feature flag key.
        variants: List of variant definitions.
        status: Current lifecycle status.
        traffic_percentage: Percentage of eligible traffic to include.
        created_at: Creation timestamp.
        started_at: When the experiment started.
        completed_at: When the experiment completed.
        winner_variant_id: ID of the winning variant.
        metadata: Additional key-value metadata.
    """

    experiment_id: str = ""
    name: str = ""
    feature_key: str = ""
    variants: list = field(default_factory=list)
    status: str = ExperimentStatus.DRAFT
    traffic_percentage: float = 100.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    winner_variant_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "feature_key": self.feature_key,
            "variants": [v.to_dict() if hasattr(v, "to_dict") else v for v in self.variants],
            "status": self.status,
            "traffic_percentage": self.traffic_percentage,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "winner_variant_id": self.winner_variant_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experiment":
        """Create from dictionary."""
        return cls(
            experiment_id=data.get("experiment_id", ""),
            name=data.get("name", ""),
            feature_key=data.get("feature_key", ""),
            status=data.get("status", ExperimentStatus.DRAFT),
            traffic_percentage=data.get("traffic_percentage", 100.0),
            winner_variant_id=data.get("winner_variant_id", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExperimentResult:
    """
    Result of an experiment analysis.

    Attributes:
        experiment_id: Experiment identifier.
        winner_variant_id: ID of the winning variant.
        confidence: Confidence level (0-1).
        p_value: Statistical p-value.
        effect_size: Measured effect size.
        recommendation: Action recommendation.
        details: Additional analysis details.
    """

    experiment_id: str = ""
    winner_variant_id: str = ""
    confidence: float = 0.0
    p_value: float = 1.0
    effect_size: float = 0.0
    recommendation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "winner_variant_id": self.winner_variant_id,
            "confidence": self.confidence,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "recommendation": self.recommendation,
            "details": self.details,
        }
