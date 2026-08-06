"""Node definition model — atomic workflow step."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class NodeType(str, enum.Enum):
    """Types of workflow nodes."""

    TASK = "task"
    DECISION = "decision"
    FORK = "fork"
    JOIN = "join"
    START = "start"
    END = "end"
    SUB_WORKFLOW = "sub_workflow"
    PARALLEL = "parallel"
    WAIT = "wait"
    SCRIPT = "script"
    SERVICE = "service"


class NodeStatus(str, enum.Enum):
    """Node execution status."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class NodeConfig:
    """Immutable node configuration."""

    max_retries: int = 0
    retry_delay_seconds: float = 1.0
    timeout_seconds: Optional[float] = None
    async_execution: bool = False
    continue_on_failure: bool = False
    condition: Optional[str] = None
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NodeDefinition:
    """Immutable node definition — a single step in a workflow."""

    node_id: str
    node_type: NodeType = NodeType.TASK
    name: Optional[str] = None
    description: Optional[str] = None
    handler: Optional[str] = None
    config: NodeConfig = field(default_factory=NodeConfig)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    _handler_fn: Optional[Callable] = field(default=None, repr=False, compare=False)

    @property
    def display_name(self) -> str:
        return self.name or self.node_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "handler": self.handler,
            "config": {
                "max_retries": self.config.max_retries,
                "retry_delay_seconds": self.config.retry_delay_seconds,
                "timeout_seconds": self.config.timeout_seconds,
                "async_execution": self.config.async_execution,
                "continue_on_failure": self.config.continue_on_failure,
                "condition": self.config.condition,
                "input_mapping": self.config.input_mapping,
                "output_mapping": self.config.output_mapping,
            },
            "inputs": self.inputs,
            "outputs": self.outputs,
            "metadata": self.metadata,
            "labels": self.labels,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"NodeDefinition(node_id={self.node_id!r}, type={self.node_type.value})"
