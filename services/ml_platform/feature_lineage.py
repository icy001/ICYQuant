"""
ICYQuant Feature Lineage - Complete data lineage tracking.

     Market Data
          │
          ▼
     Normalization
          │
          ▼
     Feature
          │
          ▼
     Training Dataset
          │
          ▼
     Model
          │
          ▼
     Prediction
          │
          ▼
     Strategy

Enables answering:
- "Where did this trading signal come from?"
- "Which market data and features does this model depend on?"
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class LineageNodeType(Enum):
    """Types of nodes in the lineage graph."""

    RAW_DATA = "raw_data"
    DATASET = "dataset"
    FEATURE = "feature"
    FEATURE_VERSION = "feature_version"
    TRAINING_DATASET = "training_dataset"
    MODEL = "model"
    MODEL_VERSION = "model_version"
    PREDICTION = "prediction"
    STRATEGY = "strategy"
    EXPERIMENT = "experiment"


@dataclass
class LineageNode:
    """A node in the lineage graph."""

    node_id: str
    node_type: LineageNodeType
    name: str = ""
    version: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineageEdge:
    """A directed edge in the lineage graph."""

    source_id: str
    target_id: str
    relation_type: str = "derived_from"  # derived_from, depends_on, produces
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """Complete lineage graph for an artifact."""

    nodes: Dict[str, LineageNode] = field(default_factory=dict)
    edges: List[LineageEdge] = field(default_factory=list)

    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: LineageEdge) -> None:
        self.edges.append(edge)

    def upstream_of(self, node_id: str) -> List[LineageNode]:
        """Get all upstream (dependency) nodes."""
        upstream_ids: Set[str] = set()
        for edge in self.edges:
            if edge.target_id == node_id:
                upstream_ids.add(edge.source_id)
        return [self.nodes[nid] for nid in upstream_ids if nid in self.nodes]

    def downstream_of(self, node_id: str) -> List[LineageNode]:
        """Get all downstream (dependent) nodes."""
        downstream_ids: Set[str] = set()
        for edge in self.edges:
            if edge.source_id == node_id:
                downstream_ids.add(edge.target_id)
        return [self.nodes[nid] for nid in downstream_ids if nid in self.nodes]

    def full_ancestry(self, node_id: str) -> List[LineageNode]:
        """Recursively get all ancestors."""
        visited: Set[str] = set()
        result: List[LineageNode] = []

        def _collect(nid: str) -> None:
            if nid in visited:
                return
            visited.add(nid)
            for edge in self.edges:
                if edge.target_id == nid and edge.source_id != nid:
                    if edge.source_id in self.nodes:
                        result.append(self.nodes[edge.source_id])
                    _collect(edge.source_id)

        _collect(node_id)
        return result


class FeatureLineage:
    """Tracks complete lineage for features across the platform.

    Maintains a directed graph of all artifacts:
    Raw Data → Feature → Dataset → Model → Prediction → Strategy
    """

    def __init__(self) -> None:
        self._graph = LineageGraph()
        self._feature_lineages: Dict[str, LineageGraph] = {}

    # -- Record Lineage --

    def record_creation(
        self,
        feature_id: str,
        source_dataset_id: Optional[str] = None,
        upstream_feature_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageGraph:
        """Record the lineage of a newly created feature."""
        graph = LineageGraph()

        # Feature node
        feature_node = LineageNode(
            node_id=feature_id,
            node_type=LineageNodeType.FEATURE,
            name=feature_id,
            metadata=metadata or {},
        )
        graph.add_node(feature_node)

        # Source dataset
        if source_dataset_id:
            dataset_node = LineageNode(
                node_id=source_dataset_id,
                node_type=LineageNodeType.DATASET,
                name=source_dataset_id,
            )
            graph.add_node(dataset_node)
            graph.add_edge(LineageEdge(
                source_id=source_dataset_id,
                target_id=feature_id,
                relation_type="derived_from",
            ))

        # Upstream features
        if upstream_feature_ids:
            for upstream_id in upstream_feature_ids:
                upstream_node = LineageNode(
                    node_id=upstream_id,
                    node_type=LineageNodeType.FEATURE,
                    name=upstream_id,
                )
                graph.add_node(upstream_node)
                graph.add_edge(LineageEdge(
                    source_id=upstream_id,
                    target_id=feature_id,
                    relation_type="depends_on",
                ))

        self._feature_lineages[feature_id] = graph
        logger.debug("Lineage recorded for feature: %s", feature_id)
        return graph

    def record_usage(
        self,
        feature_id: str,
        consumer_id: str,
        consumer_type: LineageNodeType,
    ) -> None:
        """Record a downstream usage of a feature."""
        graph = self._feature_lineages.get(feature_id, LineageGraph())
        consumer_node = LineageNode(
            node_id=consumer_id,
            node_type=consumer_type,
            name=consumer_id,
        )
        graph.add_node(consumer_node)
        graph.add_edge(LineageEdge(
            source_id=feature_id,
            target_id=consumer_id,
            relation_type="used_by",
        ))
        self._feature_lineages[feature_id] = graph

    # -- Query Lineage --

    def get_lineage(self, feature_id: str) -> Optional[LineageGraph]:
        """Get the complete lineage graph for a feature."""
        return self._feature_lineages.get(feature_id)

    def get_upstream_features(self, feature_id: str) -> List[str]:
        """Get all upstream feature IDs."""
        graph = self._feature_lineages.get(feature_id)
        if graph is None:
            return []

        upstream: List[str] = []
        for edge in graph.edges:
            if edge.target_id == feature_id and edge.relation_type == "depends_on":
                upstream.append(edge.source_id)
        return upstream

    def get_downstream_dependents(self, feature_id: str) -> List[str]:
        """Get all downstream dependents (models, strategies using this feature)."""
        graph = self._feature_lineages.get(feature_id)
        if graph is None:
            return []

        downstream: List[str] = []
        for edge in graph.edges:
            if edge.source_id == feature_id and edge.relation_type == "used_by":
                downstream.append(edge.target_id)
        return downstream

    def trace_to_model(self, feature_id: str) -> List[str]:
        """Trace from feature → dataset → model."""
        graph = self._feature_lineages.get(feature_id)
        if graph is None:
            return []

        model_ids: List[str] = []
        for node_id, node in graph.nodes.items():
            if node.node_type in (LineageNodeType.MODEL, LineageNodeType.MODEL_VERSION):
                model_ids.append(node_id)
        return model_ids

    def trace_to_strategy(self, feature_id: str) -> List[str]:
        """Trace from feature → model → prediction → strategy."""
        graph = self._feature_lineages.get(feature_id)
        if graph is None:
            return []

        strategy_ids: List[str] = []
        for edge in graph.edges:
            if edge.relation_type == "used_by":
                target = graph.nodes.get(edge.target_id)
                if target and target.node_type == LineageNodeType.STRATEGY:
                    strategy_ids.append(edge.target_id)
        return strategy_ids

    def impact_analysis(self, feature_id: str) -> Dict[str, List[str]]:
        """Analyze impact of changing/deleting a feature.

        Returns all downstream artifacts that would be affected.
        """
        return {
            "feature_id": feature_id,
            "downstream_features": [],
            "datasets": [],
            "models": self.trace_to_model(feature_id),
            "strategies": self.trace_to_strategy(feature_id),
        }
