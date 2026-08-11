"""
ICYQuant Lineage Tracker - End-to-end ML artifact lineage.

Tracks the complete provenance chain:

    Data → Feature → Dataset → Experiment → Model → Prediction → Strategy

Enables answering:
- "What data was this model trained on?"
- "Which features does this model use?"
- "What experiments produced this model?"
- "Which models contribute to this strategy?"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of tracked artifacts."""

    DATASET = "dataset"
    FEATURE = "feature"
    FEATURE_VIEW = "feature_view"
    EXPERIMENT = "experiment"
    EXPERIMENT_RUN = "experiment_run"
    MODEL = "model"
    MODEL_VERSION = "model_version"
    PREDICTION = "prediction"
    STRATEGY = "strategy"
    SIGNAL = "signal"


class RelationType(Enum):
    """Types of lineage relationships."""

    DERIVED_FROM = "derived_from"
    DEPENDS_ON = "depends_on"
    PRODUCES = "produces"
    USES = "uses"
    TRAINS = "trains"
    EVALUATES = "evaluates"
    SERVES = "serves"


@dataclass
class LineageRecord:
    """A single lineage relationship record."""

    source_id: str            # upstream artifact
    source_type: ArtifactType
    target_id: str            # downstream artifact
    target_type: ArtifactType
    relation: RelationType
    metadata: Dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=datetime.utcnow)


class LineageTracker:
    """Tracks lineage across all ML artifacts.

    Maintains a graph of artifact relationships for:
    - Auditing: "What data produced this signal?"
    - Impact analysis: "What depends on this feature?"
    - Debugging: "What's in the chain when predictions degrade?"
    - Governance: "Is this model using approved features?"
    """

    def __init__(self) -> None:
        self._records: List[LineageRecord] = []
        self._source_index: Dict[str, List[LineageRecord]] = {}  # source_id -> records
        self._target_index: Dict[str, List[LineageRecord]] = {}  # target_id -> records

    # -- Record --

    def record(
        self,
        source_id: str,
        source_type: ArtifactType,
        target_id: str,
        target_type: ArtifactType,
        relation: RelationType = RelationType.DERIVED_FROM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageRecord:
        """Record a lineage relationship between two artifacts."""
        record = LineageRecord(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            relation=relation,
            metadata=metadata or {},
        )

        self._records.append(record)

        # Index
        if source_id not in self._source_index:
            self._source_index[source_id] = []
        self._source_index[source_id].append(record)

        if target_id not in self._target_index:
            self._target_index[target_id] = []
        self._target_index[target_id].append(record)

        logger.debug("Lineage recorded: %s(%s) --[%s]--> %s(%s)",
                      source_id, source_type.value, relation.value, target_id, target_type.value)
        return record

    # -- Trace --

    def trace_upstream(self, artifact_id: str, max_depth: int = 10) -> List[LineageRecord]:
        """Trace all upstream artifacts (what led to this artifact)."""
        visited: Set[str] = set()
        results: List[LineageRecord] = []

        def _trace(current_id: str, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)

            # Find records where current is the target
            upstream = self._target_index.get(current_id, [])
            for record in upstream:
                results.append(record)
                _trace(record.source_id, depth + 1)

        _trace(artifact_id, 0)
        return results

    def trace_downstream(self, artifact_id: str, max_depth: int = 10) -> List[LineageRecord]:
        """Trace all downstream artifacts (what depends on this artifact)."""
        visited: Set[str] = set()
        results: List[LineageRecord] = []

        def _trace(current_id: str, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)

            downstream = self._source_index.get(current_id, [])
            for record in downstream:
                results.append(record)
                _trace(record.target_id, depth + 1)

        _trace(artifact_id, 0)
        return results

    # -- Specific Traces --

    def trace_to_model(self, feature_id: str) -> List[str]:
        """Trace from a feature to all models using it."""
        records = self.trace_downstream(feature_id)
        model_ids: List[str] = []
        for record in records:
            if record.target_type in (ArtifactType.MODEL, ArtifactType.MODEL_VERSION):
                model_ids.append(record.target_id)
        return model_ids

    def trace_to_strategy(self, model_id: str) -> List[str]:
        """Trace from a model to all strategies it feeds into."""
        records = self.trace_downstream(model_id)
        strategy_ids: List[str] = []
        for record in records:
            if record.target_type == ArtifactType.STRATEGY:
                strategy_ids.append(record.target_id)
        return strategy_ids

    def get_model_lineage(self, model_id: str) -> Dict[str, Any]:
        """Get complete lineage for a model.

        Returns everything from data → features → dataset → experiment → model.
        """
        upstream = self.trace_upstream(model_id)
        downstream = self.trace_downstream(model_id)

        return {
            "model_id": model_id,
            "training_dataset": next(
                (r.source_id for r in upstream if r.source_type == ArtifactType.DATASET),
                None,
            ),
            "features": [
                r.source_id for r in upstream
                if r.source_type == ArtifactType.FEATURE
            ],
            "experiment": next(
                (r.source_id for r in upstream if r.source_type == ArtifactType.EXPERIMENT),
                None,
            ),
            "strategies": [
                r.target_id for r in downstream
                if r.target_type == ArtifactType.STRATEGY
            ],
            "full_upstream_count": len(upstream),
            "full_downstream_count": len(downstream),
        }

    # -- Impact Analysis --

    def impact_analysis(self, artifact_id: str) -> Dict[str, Any]:
        """Analyze impact of changing/deleting an artifact.

        Returns all downstream artifacts that would be affected.
        """
        downstream = self.trace_downstream(artifact_id)

        affected: Dict[str, List[str]] = {}
        for record in downstream:
            key = record.target_type.value
            if key not in affected:
                affected[key] = []
            if record.target_id not in affected[key]:
                affected[key].append(record.target_id)

        return {
            "artifact_id": artifact_id,
            "affected_artifacts": affected,
            "total_affected": len(downstream),
            "affected_types": list(affected.keys()),
        }

    def count(self) -> int:
        return len(self._records)
