from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, Optional


class WorkflowContext:
    """Holds per-execution context for a running workflow.

    Stores variables, metadata, and node results scoped to a single workflow
    execution identified by ``execution_id``. All accessors are thread-safe.
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

    @property
    def workflow_id(self) -> str:
        """The workflow definition identifier this context belongs to."""
        return self._workflow_id

    @property
    def execution_id(self) -> str:
        """The unique execution identifier for this context."""
        return self._execution_id

    @property
    def trace_id(self) -> Optional[str]:
        """Optional distributed tracing identifier."""
        return self._trace_id

    @property
    def created_at(self) -> datetime:
        """Timestamp marking when the context was created."""
        return self._created_at

    @property
    def updated_at(self) -> Optional[datetime]:
        """Timestamp of the most recent mutation, or None if never modified."""
        return self._updated_at

    def _touch(self) -> None:
        """Mark the context as modified."""
        self._updated_at = datetime.utcnow()

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Return the value of a context variable, or ``default`` if absent."""
        with self._lock:
            return self._variables.get(key, default)

    def set_variable(self, key: str, value: Any) -> None:
        """Set a single context variable."""
        with self._lock:
            self._variables[key] = value
            self._touch()

    def get_variables(self) -> Dict[str, Any]:
        """Return a shallow copy of all context variables."""
        with self._lock:
            return dict(self._variables)

    def update_variables(self, variables: Dict[str, Any]) -> None:
        """Merge ``variables`` into the context variable map."""
        with self._lock:
            self._variables.update(variables)
            self._touch()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Return a metadata value, or ``default`` if absent."""
        with self._lock:
            return self._metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a single metadata entry."""
        with self._lock:
            self._metadata[key] = value
            self._touch()

    def get_node_result(self, node_id: str) -> Any:
        """Return the stored result for ``node_id``, or None if not yet recorded."""
        with self._lock:
            return self._node_results.get(node_id)

    def set_node_result(self, node_id: str, result: Any) -> None:
        """Store the execution result for a node."""
        with self._lock:
            self._node_results[node_id] = result
            self._touch()

    def get_all_node_results(self) -> Dict[str, Any]:
        """Return a shallow copy of all recorded node results."""
        with self._lock:
            return dict(self._node_results)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context to a plain dict suitable for persistence."""
        with self._lock:
            return {
                "workflow_id": self._workflow_id,
                "execution_id": self._execution_id,
                "trace_id": self._trace_id,
                "variables": dict(self._variables),
                "metadata": dict(self._metadata),
                "node_results": dict(self._node_results),
                "created_at": self._created_at.isoformat(),
                "updated_at": self._updated_at.isoformat() if self._updated_at else None,
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowContext:
        """Reconstruct a :class:`WorkflowContext` from a serialized dict."""
        context = cls(
            workflow_id=data["workflow_id"],
            execution_id=data["execution_id"],
            trace_id=data.get("trace_id"),
        )
        context._variables = dict(data.get("variables", {}))
        context._metadata = dict(data.get("metadata", {}))
        context._node_results = dict(data.get("node_results", {}))
        created_at = data.get("created_at")
        if created_at:
            context._created_at = datetime.fromisoformat(created_at)
        updated_at = data.get("updated_at")
        if updated_at:
            context._updated_at = datetime.fromisoformat(updated_at)
        return context

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time serializable snapshot of the context."""
        return self.to_dict()
