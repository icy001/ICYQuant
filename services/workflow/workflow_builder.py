"""Workflow Builder — fluent API for constructing workflow definitions.

The :class:`WorkflowBuilder` provides a readable, chainable API for building
:class:`WorkflowDefinition` instances. It supports defining nodes, edges,
transitions, configuration, and metadata through a builder pattern.

Usage::

    workflow = (
        WorkflowBuilder("order_execution", version="1.0.0")
            .node("validate", node_type=NodeType.TASK, handler="validate_order")
            .node("risk_check", node_type=NodeType.DECISION, handler="check_risk")
            .node("execute", node_type=NodeType.TASK, handler="execute_order")
            .edge("validate", "risk_check")
            .edge("risk_check", "execute")
            .config(max_retries=3, timeout_seconds=300)
            .tag("trading")
            .owner("quant-team")
            .build()
    )
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from .workflow_definition import WorkflowDefinition, WorkflowConfig, WorkflowStatus
from .models.node import NodeDefinition, NodeType, NodeConfig
from .models.edge import EdgeDefinition, EdgeType
from .models.metadata import WorkflowMetadata

logger = logging.getLogger(__name__)


class WorkflowBuilder:
    """Fluent builder for :class:`WorkflowDefinition`.

    Supports construction via chained method calls or from YAML/JSON
    configuration files.
    """

    def __init__(self, name: str, *, version: str = "1.0.0") -> None:
        self._name = name
        self._version = version
        self._nodes: List[NodeDefinition] = []
        self._edges: List[EdgeDefinition] = []
        self._config = WorkflowConfig()
        self._metadata = WorkflowMetadata(name=name, version=version)
        self._tags: List[str] = []
        self._owner: Optional[str] = None
        self._status = WorkflowStatus.DRAFT

    # ------------------------------------------------------------------
    # Node definition
    # ------------------------------------------------------------------

    def node(
        self,
        node_id: str,
        *,
        node_type: NodeType = NodeType.TASK,
        name: Optional[str] = None,
        description: Optional[str] = None,
        handler: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        max_retries: int = 0,
        retry_delay_seconds: float = 1.0,
        timeout_seconds: Optional[float] = None,
        async_execution: bool = False,
        continue_on_failure: bool = False,
        condition: Optional[str] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowBuilder:
        """Add a node to the workflow."""
        node = NodeDefinition(
            node_id=node_id,
            node_type=node_type,
            name=name or node_id,
            description=description,
            handler=handler,
            inputs=inputs or {},
            outputs=outputs or {},
            config=NodeConfig(
                max_retries=max_retries,
                retry_delay_seconds=retry_delay_seconds,
                timeout_seconds=timeout_seconds,
                async_execution=async_execution,
                continue_on_failure=continue_on_failure,
                condition=condition,
                input_mapping=input_mapping or {},
                output_mapping=output_mapping or {},
            ),
            labels=labels or {},
            tags=tags or [],
            metadata=metadata or {},
        )
        self._nodes.append(node)
        return self

    def start_node(self, node_id: str = "start", **kwargs) -> WorkflowBuilder:
        """Add a START node."""
        return self.node(node_id, node_type=NodeType.START, **kwargs)

    def end_node(self, node_id: str = "end", **kwargs) -> WorkflowBuilder:
        """Add an END node."""
        return self.node(node_id, node_type=NodeType.END, **kwargs)

    def task_node(self, node_id: str, handler: str, **kwargs) -> WorkflowBuilder:
        """Add a TASK node with a handler."""
        return self.node(node_id, node_type=NodeType.TASK, handler=handler, **kwargs)

    def decision_node(self, node_id: str, condition: str, **kwargs) -> WorkflowBuilder:
        """Add a DECISION node with a condition."""
        return self.node(node_id, node_type=NodeType.DECISION, condition=condition, **kwargs)

    def fork_node(self, node_id: str, **kwargs) -> WorkflowBuilder:
        """Add a FORK node."""
        return self.node(node_id, node_type=NodeType.FORK, **kwargs)

    def join_node(self, node_id: str, **kwargs) -> WorkflowBuilder:
        """Add a JOIN node."""
        return self.node(node_id, node_type=NodeType.JOIN, **kwargs)

    # ------------------------------------------------------------------
    # Edge definition
    # ------------------------------------------------------------------

    def edge(
        self,
        source_id: str,
        target_id: str,
        *,
        edge_type: EdgeType = EdgeType.NORMAL,
        condition: Optional[str] = None,
        label: Optional[str] = None,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowBuilder:
        """Add a directed edge between two nodes."""
        edge_id = f"{source_id}->{target_id}"
        # De-duplicate: if edge already exists, skip
        if any(e.source_id == source_id and e.target_id == target_id for e in self._edges):
            return self
        edge = EdgeDefinition(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            condition=condition,
            label=label,
            weight=weight,
            metadata=metadata or {},
        )
        self._edges.append(edge)
        return self

    def conditional_edge(
        self,
        source_id: str,
        target_id: str,
        condition: str,
        **kwargs,
    ) -> WorkflowBuilder:
        """Add a conditional edge (branching)."""
        return self.edge(source_id, target_id, edge_type=EdgeType.CONDITIONAL, condition=condition, **kwargs)

    def error_edge(self, source_id: str, target_id: str, **kwargs) -> WorkflowBuilder:
        """Add an error-handling edge."""
        return self.edge(source_id, target_id, edge_type=EdgeType.ERROR, **kwargs)

    def timeout_edge(self, source_id: str, target_id: str, **kwargs) -> WorkflowBuilder:
        """Add a timeout edge."""
        return self.edge(source_id, target_id, edge_type=EdgeType.TIMEOUT, **kwargs)

    def chain(self, *node_ids: str) -> WorkflowBuilder:
        """Add sequential edges between a chain of nodes.

        Example: ``builder.chain("A", "B", "C")`` creates edges A→B and B→C.
        """
        for i in range(len(node_ids) - 1):
            self.edge(node_ids[i], node_ids[i + 1])
        return self

    def fan_out(self, source_id: str, *target_ids: str) -> WorkflowBuilder:
        """Create edges from one source to multiple targets.

        Example: ``builder.fan_out("fork", "A", "B", "C")`` creates edges fork→A, fork→B, fork→C.
        """
        for target_id in target_ids:
            self.edge(source_id, target_id)
        return self

    def fan_in(self, *source_ids: str, target_id: str) -> WorkflowBuilder:
        """Create edges from multiple sources to one target.

        Example: ``builder.fan_in("A", "B", "C", target_id="join")`` creates edges A→join, B→join, C→join.
        """
        for source_id in source_ids:
            self.edge(source_id, target_id)
        return self

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def config(
        self,
        *,
        max_retries: Optional[int] = None,
        retry_delay_seconds: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        parallel_node_limit: Optional[int] = None,
        checkpoint_enabled: Optional[bool] = None,
        snapshot_on_complete: Optional[bool] = None,
        telemetry_enabled: Optional[bool] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> WorkflowBuilder:
        """Set workflow-level configuration."""
        kwargs: Dict[str, Any] = {
            "max_retries": self._config.max_retries,
            "retry_delay_seconds": self._config.retry_delay_seconds,
            "timeout_seconds": self._config.timeout_seconds,
            "parallel_node_limit": self._config.parallel_node_limit,
            "checkpoint_enabled": self._config.checkpoint_enabled,
            "snapshot_on_complete": self._config.snapshot_on_complete,
            "telemetry_enabled": self._config.telemetry_enabled,
            "labels": dict(self._config.labels),
        }
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        if retry_delay_seconds is not None:
            kwargs["retry_delay_seconds"] = retry_delay_seconds
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        if parallel_node_limit is not None:
            kwargs["parallel_node_limit"] = parallel_node_limit
        if checkpoint_enabled is not None:
            kwargs["checkpoint_enabled"] = checkpoint_enabled
        if snapshot_on_complete is not None:
            kwargs["snapshot_on_complete"] = snapshot_on_complete
        if telemetry_enabled is not None:
            kwargs["telemetry_enabled"] = telemetry_enabled
        if labels is not None:
            kwargs["labels"] = dict(labels)
        self._config = WorkflowConfig(**kwargs)
        return self

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def description(self, text: str) -> WorkflowBuilder:
        self._metadata = WorkflowMetadata(
            name=self._metadata.name,
            version=self._metadata.version,
            description=text,
            author=self._metadata.author,
            tags=self._metadata.tags,
            labels=self._metadata.labels,
            deprecated=self._metadata.deprecated,
            deprecation_message=self._metadata.deprecation_message,
            custom=self._metadata.custom,
        )
        return self

    def author(self, author: str) -> WorkflowBuilder:
        self._metadata = WorkflowMetadata(
            name=self._metadata.name,
            version=self._metadata.version,
            description=self._metadata.description,
            author=author,
            tags=self._metadata.tags,
            labels=self._metadata.labels,
            deprecated=self._metadata.deprecated,
            deprecation_message=self._metadata.deprecation_message,
            custom=self._metadata.custom,
        )
        return self

    def tag(self, *tags: str) -> WorkflowBuilder:
        self._tags.extend(tags)
        return self

    def owner(self, owner: str) -> WorkflowBuilder:
        self._owner = owner
        return self

    def label(self, key: str, value: str) -> WorkflowBuilder:
        self._config.labels[key] = value
        return self

    def custom_metadata(self, key: str, value: Any) -> WorkflowBuilder:
        self._metadata.custom[key] = value
        return self

    def deprecated(self, message: str = "") -> WorkflowBuilder:
        self._metadata = WorkflowMetadata(
            name=self._metadata.name,
            version=self._metadata.version,
            description=self._metadata.description,
            author=self._metadata.author,
            tags=self._metadata.tags,
            labels=self._metadata.labels,
            deprecated=True,
            deprecation_message=message,
            custom=self._metadata.custom,
        )
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> WorkflowDefinition:
        """Construct the immutable :class:`WorkflowDefinition`."""
        from datetime import datetime
        return WorkflowDefinition(
            name=self._name,
            version=self._version,
            nodes=list(self._nodes),
            edges=list(self._edges),
            config=self._config,
            metadata=self._metadata,
            status=self._status,
            tags=list(self._tags),
            owner=self._owner,
            updated_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Static constructors
    # ------------------------------------------------------------------

    @staticmethod
    def from_yaml(path: Union[str, Path]) -> WorkflowDefinition:
        """Build a WorkflowDefinition from a YAML file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return WorkflowBuilder._from_dict(data)

    @staticmethod
    def from_json(path: Union[str, Path]) -> WorkflowDefinition:
        """Build a WorkflowDefinition from a JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return WorkflowBuilder._from_dict(data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> WorkflowDefinition:
        """Build a WorkflowDefinition from a dictionary."""
        return WorkflowBuilder._from_dict(data)

    @staticmethod
    def _from_dict(data: Dict[str, Any]) -> WorkflowDefinition:
        builder = WorkflowBuilder(
            name=data["name"],
            version=data.get("version", "1.0.0"),
        )

        # Nodes
        for node_data in data.get("nodes", []):
            builder.node(
                node_id=node_data["node_id"],
                node_type=NodeType(node_data.get("node_type", "task")),
                name=node_data.get("name"),
                description=node_data.get("description"),
                handler=node_data.get("handler"),
                inputs=node_data.get("inputs", {}),
                outputs=node_data.get("outputs", {}),
                max_retries=node_data.get("max_retries", 0),
                timeout_seconds=node_data.get("timeout_seconds"),
                condition=node_data.get("condition"),
            )

        # Edges
        for edge_data in data.get("edges", []):
            builder.edge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=EdgeType(edge_data.get("edge_type", "normal")),
                condition=edge_data.get("condition"),
                label=edge_data.get("label"),
                weight=edge_data.get("weight", 1.0),
            )

        # Config
        config_data = data.get("config", {})
        if config_data:
            builder.config(**config_data)

        # Metadata
        if "description" in data:
            builder.description(data["description"])
        if "author" in data:
            builder.author(data["author"])
        if "tags" in data:
            builder.tag(*data["tags"])
        if "owner" in data:
            builder.owner(data["owner"])

        return builder.build()
