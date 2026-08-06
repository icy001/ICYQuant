"""Workflow Repository — persistent storage for workflow definitions and snapshots.

The :class:`WorkflowRepository` provides CRUD operations for workflow
definitions, execution instances, and snapshots. It abstracts the underlying
storage backend (PostgreSQL, object storage, etc.).

Supported backends:
* In-memory (dict-based, for development/testing)
* PostgreSQL (via SQLAlchemy)
* Object storage (reserved for future)
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_definition import WorkflowDefinition
from .workflow_snapshot import WorkflowSnapshot
from .workflow_serializer import WorkflowSerializer

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Persistent storage for workflow definitions, instances, and snapshots.

    The default implementation is in-memory (dict-based). For production use,
    a PostgreSQL-backed implementation should be used.
    """

    def __init__(self, *, backend: str = "memory") -> None:
        self._backend = backend
        self._lock = threading.RLock()

        # In-memory stores
        self._definitions: Dict[str, Dict[str, WorkflowDefinition]] = {}  # name → version → definition
        self._instances: Dict[str, Dict[str, Any]] = {}  # execution_id → instance data
        self._snapshots: Dict[str, List[WorkflowSnapshot]] = {}  # execution_id → snapshots

    # ------------------------------------------------------------------
    # Definition CRUD
    # ------------------------------------------------------------------

    async def save_definition(self, definition: WorkflowDefinition) -> None:
        """Persist a workflow definition."""
        with self._lock:
            if definition.name not in self._definitions:
                self._definitions[definition.name] = {}
            self._definitions[definition.name][definition.version] = definition
            logger.debug("Repository: saved definition %s v%s", definition.name, definition.version)

    async def load_definition(
        self,
        workflow_id: str,
        *,
        version: Optional[str] = None,
    ) -> Optional[WorkflowDefinition]:
        """Load a workflow definition."""
        with self._lock:
            versions = self._definitions.get(workflow_id, {})
            if not versions:
                return None
            if version:
                return versions.get(version)
            # Return latest version
            return list(versions.values())[-1]

    async def list_definitions(self) -> List[WorkflowDefinition]:
        """List all stored workflow definitions (latest version each)."""
        with self._lock:
            results = []
            for versions in self._definitions.values():
                if versions:
                    results.append(list(versions.values())[-1])
            return results

    async def delete_definition(self, workflow_id: str, *, version: Optional[str] = None) -> bool:
        """Delete a workflow definition."""
        with self._lock:
            if version:
                versions = self._definitions.get(workflow_id, {})
                if version in versions:
                    del versions[version]
                    if not versions:
                        del self._definitions[workflow_id]
                    return True
                return False
            else:
                return self._definitions.pop(workflow_id, None) is not None

    async def definition_exists(self, workflow_id: str, *, version: Optional[str] = None) -> bool:
        """Check if a definition exists."""
        with self._lock:
            versions = self._definitions.get(workflow_id, {})
            if not versions:
                return False
            if version:
                return version in versions
            return True

    # ------------------------------------------------------------------
    # Instance storage
    # ------------------------------------------------------------------

    async def save_instance(self, execution_id: str, data: Dict[str, Any]) -> None:
        """Persist execution instance data."""
        with self._lock:
            data["saved_at"] = datetime.utcnow().isoformat()
            self._instances[execution_id] = data

    async def load_instance(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load execution instance data."""
        with self._lock:
            return self._instances.get(execution_id)

    async def list_instances(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List execution instances, optionally filtered."""
        with self._lock:
            results = []
            for data in self._instances.values():
                if workflow_id and data.get("workflow_id") != workflow_id:
                    continue
                if status and data.get("status") != status:
                    continue
                results.append(dict(data))
                if len(results) >= limit:
                    break
            return results

    # ------------------------------------------------------------------
    # Snapshot storage
    # ------------------------------------------------------------------

    async def save_snapshot(self, snapshot: WorkflowSnapshot) -> None:
        """Persist a workflow execution snapshot."""
        with self._lock:
            if snapshot.execution_id not in self._snapshots:
                self._snapshots[snapshot.execution_id] = []
            self._snapshots[snapshot.execution_id].append(snapshot)
            logger.debug("Repository: saved snapshot %s for execution %s",
                         snapshot.snapshot_id, snapshot.execution_id)

    async def load_latest_snapshot(self, execution_id: str) -> Optional[WorkflowSnapshot]:
        """Load the most recent snapshot for an execution."""
        with self._lock:
            snapshots = self._snapshots.get(execution_id, [])
            return snapshots[-1] if snapshots else None

    async def list_snapshots(self, execution_id: str) -> List[WorkflowSnapshot]:
        """List all snapshots for an execution."""
        with self._lock:
            return list(self._snapshots.get(execution_id, []))

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def save_all_definitions(self, definitions: List[WorkflowDefinition]) -> None:
        """Persist multiple workflow definitions."""
        for definition in definitions:
            await self.save_definition(definition)

    async def count_definitions(self) -> int:
        """Return the total number of stored definitions (across all versions)."""
        with self._lock:
            return sum(len(versions) for versions in self._definitions.values())

    async def count_instances(self) -> int:
        """Return the total number of stored execution instances."""
        with self._lock:
            return len(self._instances)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": self._backend,
                "definition_count": sum(len(v) for v in self._definitions.values()),
                "instance_count": len(self._instances),
                "snapshot_count": sum(len(s) for s in self._snapshots.values()),
            }
