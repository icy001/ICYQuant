"""Tool definition model — the canonical schema for any tool registered in the platform.

Pipeline:
    ToolDefinition (declarative)
        -> Validation
        -> Execution
        -> Observation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Types ──

@dataclass
class ToolInput:
    """Schema for a single tool input parameter."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None


@dataclass
class ToolOutput:
    """Schema for a single tool output field."""

    name: str
    type: str = "string"
    description: str = ""


# ── ToolDefinition ──

@dataclass
class ToolDefinition:
    """Canonical tool schema used for registration, discovery, and execution.

    Supports:
        - Declarative input/output schema
        - Versioned capability tagging
        - Permission assignment
        - Runtime configuration
        - Custom handler binding

    Usage:
        definition = ToolDefinition(
            name="backtest.run",
            description="Run a backtest",
            inputs=[ToolInput(name="strategy_id", required=True)],
            permission="research.execute",
        )
        registry.register(definition)
    """

    name: str
    description: str = ""
    version: str = "1.0.0"

    # ── Schema ──
    inputs: List[ToolInput] = field(default_factory=list)
    outputs: List[ToolOutput] = field(default_factory=list)

    # ── Classification ──
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    capability: str = ""

    # ── Security ──
    permission: str = "default.read"
    risk_level: str = "low"  # low | medium | high | critical

    # ── Runtime ──
    timeout_seconds: float = 30.0
    max_retries: int = 0
    is_idempotent: bool = False
    is_streaming: bool = False
    rate_limit_per_second: Optional[float] = None

    # ── Handler ──
    handler: Optional[Callable[..., Any]] = None

    # ── Metadata ──
    tool_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deprecated: bool = False
    deprecation_message: str = ""

    # ── Helpers ──

    @property
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema representation of inputs."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for inp in self.inputs:
            prop: Dict[str, Any] = {"type": inp.type, "description": inp.description}
            if inp.default is not None:
                prop["default"] = inp.default
            if inp.enum is not None:
                prop["enum"] = inp.enum
            if inp.minimum is not None:
                prop["minimum"] = inp.minimum
            if inp.maximum is not None:
                prop["maximum"] = inp.maximum
            if inp.pattern is not None:
                prop["pattern"] = inp.pattern
            properties[inp.name] = prop
            if inp.required:
                required.append(inp.name)
        schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    @property
    def output_schema(self) -> Dict[str, Any]:
        """JSON Schema representation of outputs."""
        properties: Dict[str, Any] = {}
        for out in self.outputs:
            properties[out.name] = {"type": out.type, "description": out.description}
        return {"type": "object", "properties": properties}

    @property
    def is_active(self) -> bool:
        """Whether the tool is active (not deprecated)."""
        return not self.deprecated

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "tags": self.tags,
            "capability": self.capability,
            "permission": self.permission,
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "is_idempotent": self.is_idempotent,
            "is_streaming": self.is_streaming,
            "deprecated": self.deprecated,
            "deprecation_message": self.deprecation_message,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    def validate_input(self, params: Dict[str, Any]) -> List[str]:
        """Validate input parameters against schema.

        Args:
            params: The input parameters to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors: List[str] = []
        for inp in self.inputs:
            if inp.required and inp.name not in params:
                errors.append(f"Missing required input: {inp.name}")
                continue
            if inp.name not in params:
                continue
            value = params[inp.name]
            if inp.type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Input '{inp.name}' must be a number, got {type(value).__name__}")
            elif inp.type == "integer" and not isinstance(value, int):
                errors.append(f"Input '{inp.name}' must be an integer, got {type(value).__name__}")
            elif inp.type == "boolean" and not isinstance(value, bool):
                errors.append(f"Input '{inp.name}' must be a boolean, got {type(value).__name__}")
            if inp.enum is not None and value not in inp.enum:
                errors.append(f"Input '{inp.name}' must be one of {inp.enum}, got {value}")
            if inp.minimum is not None and isinstance(value, (int, float)) and value < inp.minimum:
                errors.append(f"Input '{inp.name}' must be >= {inp.minimum}, got {value}")
            if inp.maximum is not None and isinstance(value, (int, float)) and value > inp.maximum:
                errors.append(f"Input '{inp.name}' must be <= {inp.maximum}, got {value}")
        return errors

    def __hash__(self) -> int:
        return hash(self.tool_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ToolDefinition):
            return False
        return self.tool_id == other.tool_id
