"""Workflow Serializer — serializes workflow definitions and snapshots.

Supports JSON, YAML, and binary (reserved) formats for:
* API responses
* Snapshot persistence
* Cluster synchronization
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import yaml

from .workflow_definition import WorkflowDefinition
from .workflow_snapshot import WorkflowSnapshot
from .workflow_context import WorkflowContext

logger = logging.getLogger(__name__)


class SerializationFormat:
    JSON = "json"
    YAML = "yaml"
    BINARY = "binary"  # reserved


class WorkflowSerializer:
    """Unified serializer for workflow objects.

    Handles conversion between workflow objects and their serialized
    representations (JSON, YAML).
    """

    # ------------------------------------------------------------------
    # Workflow Definition
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_definition(
        definition: WorkflowDefinition,
        *,
        fmt: str = SerializationFormat.JSON,
        indent: int = 2,
    ) -> str:
        """Serialize a workflow definition to a string."""
        data = definition.to_dict()
        if fmt == SerializationFormat.JSON:
            return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        elif fmt == SerializationFormat.YAML:
            return yaml.safe_dump(data, indent=indent, allow_unicode=True, sort_keys=False)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

    @staticmethod
    def deserialize_definition(
        raw: str,
        *,
        fmt: str = SerializationFormat.JSON,
    ) -> WorkflowDefinition:
        """Deserialize a workflow definition from a string."""
        from .workflow_builder import WorkflowBuilder

        if fmt == SerializationFormat.JSON:
            data = json.loads(raw)
        elif fmt == SerializationFormat.YAML:
            data = yaml.safe_load(raw)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

        return WorkflowBuilder.from_dict(data)

    @staticmethod
    def serialize_definition_to_dict(definition: WorkflowDefinition) -> Dict[str, Any]:
        """Serialize a workflow definition to a plain dict."""
        return definition.to_dict()

    # ------------------------------------------------------------------
    # Workflow Snapshot
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_snapshot(
        snapshot: WorkflowSnapshot,
        *,
        fmt: str = SerializationFormat.JSON,
        indent: int = 2,
    ) -> str:
        """Serialize a workflow snapshot to a string."""
        data = snapshot.to_dict()
        if fmt == SerializationFormat.JSON:
            return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        elif fmt == SerializationFormat.YAML:
            return yaml.safe_dump(data, indent=indent, allow_unicode=True, sort_keys=False)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

    @staticmethod
    def deserialize_snapshot(
        raw: str,
        *,
        fmt: str = SerializationFormat.JSON,
    ) -> WorkflowSnapshot:
        """Deserialize a workflow snapshot from a string."""
        if fmt == SerializationFormat.JSON:
            data = json.loads(raw)
        elif fmt == SerializationFormat.YAML:
            data = yaml.safe_load(raw)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

        return WorkflowSnapshot.from_dict(data)

    # ------------------------------------------------------------------
    # Workflow Context
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_context(
        context: WorkflowContext,
        *,
        fmt: str = SerializationFormat.JSON,
        indent: int = 2,
    ) -> str:
        """Serialize a workflow context to a string."""
        data = context.to_dict()
        if fmt == SerializationFormat.JSON:
            return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        elif fmt == SerializationFormat.YAML:
            return yaml.safe_dump(data, indent=indent, allow_unicode=True, sort_keys=False)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

    @staticmethod
    def deserialize_context(
        raw: str,
        *,
        fmt: str = SerializationFormat.JSON,
    ) -> WorkflowContext:
        """Deserialize a workflow context from a string."""
        if fmt == SerializationFormat.JSON:
            data = json.loads(raw)
        elif fmt == SerializationFormat.YAML:
            data = yaml.safe_load(raw)
        else:
            raise ValueError(f"Unsupported serialization format: {fmt}")

        return WorkflowContext.from_dict(data)

    # ------------------------------------------------------------------
    # Batch serialization
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_definitions_batch(
        definitions: list[WorkflowDefinition],
        *,
        fmt: str = SerializationFormat.JSON,
    ) -> str:
        """Serialize multiple workflow definitions."""
        data = [d.to_dict() for d in definitions]
        if fmt == SerializationFormat.JSON:
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)
        else:
            return yaml.safe_dump(data, indent=2, allow_unicode=True, sort_keys=False)
