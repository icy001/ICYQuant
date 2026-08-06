"""Workflow execution context — shared state across all nodes in a workflow run.

The :class:`WorkflowContext` holds per-execution data including variables,
metadata, node results, and trace identifiers. It is the primary communication
mechanism between workflow nodes.

All public accessors are thread-safe, allowing concurrent reads/writes from
parallel node execution.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class WorkflowContext:
    """Thread-safe per-execution context shared across all workflow nodes.

    Stores:
    * **Variables** — input/output/global/temporary values
    * **Metadata** — execution metadata (status, timestamps, labels)
    * **Node results** — output of each executed node keyed by node_id
    * **Trace context** — workflow_id, execution_id, trace_id

    Usage::

        ctx = WorkflowContext(workflow_id="order_exec", execution_id="abc-123")
        ctx.set_variable("order_id", "ORD-456")
        ctx.set_node_result("validate_order", {"valid": True})
    """

    def __init__(
        self,
        workflow_id: str,
        execution_id: str,
        trace_id: Optional[str] = None,
    ) -> None:
        self._workflow_id = workflow_id
        self._execution_id = execution_id
        self._trace_id = trace_id
        self._variables: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}
        self._node_results: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._created_at = datetime.utcnow()
        self._updated_at: Optional[datetime] = None
        self._status: str = "pending"

    # ------------------------------------------------------------------
    # Identity properties
    # ------------------------------------------------------------------

    @property
    def workflow_id(self) -> str:
        return self._workflow_id

    @property
    def execution_id(self) -> str:
        return self._execution_id

    @property
    def trace_id(self) -> Optional[str]:
        return self._trace_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> Optional[datetime]:
        return self._updated_at

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def set_status(self, status: str) -> None:
        with self._lock:
            self._status = status
            self._touch()

    # ------------------------------------------------------------------
    # Variable management
    # ------------------------------------------------------------------

    def get_variable(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._variables.get(key, default)

    def set_variable(self, key: str, value: Any) -> None:
        with self._lock:
            self._variables[key] = value
            self._touch()

    def get_variables(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._variables)

    def update_variables(self, variables: Dict[str, Any]) -> None:
        with self._lock:
            self._variables.update(variables)
            self._touch()

    def delete_variable(self, key: str) -> bool:
        with self._lock:
            if key in self._variables:
                del self._variables[key]
                self._touch()
                return True
            return False

    def has_variable(self, key: str) -> bool:
        with self._lock:
            return key in self._variables

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        with self._lock:
            self._metadata[key] = value
            self._touch()

    def get_all_metadata(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._metadata)

    # ------------------------------------------------------------------
    # Node results
    # ------------------------------------------------------------------

    def get_node_result(self, node_id: str) -> Any:
        with self._lock:
            return self._node_results.get(node_id)

    def set_node_result(self, node_id: str, result: Any) -> None:
        with self._lock:
            self._node_results[node_id] = result
            self._touch()

    def get_all_node_results(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._node_results)

    def clear_node_result(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._node_results:
                del self._node_results[node_id]
                self._touch()
                return True
            return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workflow_id": self._workflow_id,
                "execution_id": self._execution_id,
                "trace_id": self._trace_id,
                "status": self._status,
                "variables": dict(self._variables),
                "metadata": dict(self._metadata),
                "node_results": dict(self._node_results),
                "created_at": self._created_at.isoformat(),
                "updated_at": self._updated_at.isoformat() if self._updated_at else None,
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowContext:
        ctx = cls(
            workflow_id=data["workflow_id"],
            execution_id=data["execution_id"],
            trace_id=data.get("trace_id"),
        )
        ctx._variables = dict(data.get("variables", {}))
        ctx._metadata = dict(data.get("metadata", {}))
        ctx._node_results = dict(data.get("node_results", {}))
        ctx._status = data.get("status", "pending")
        created_at = data.get("created_at")
        if created_at:
            ctx._created_at = datetime.fromisoformat(created_at)
        updated_at = data.get("updated_at")
        if updated_at:
            ctx._updated_at = datetime.fromisoformat(updated_at)
        return ctx

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time serializable snapshot of the context."""
        return self.to_dict()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _touch(self) -> None:
        self._updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"WorkflowContext(workflow_id={self._workflow_id!r}, "
            f"execution_id={self._execution_id!r}, status={self._status!r})"
        )
