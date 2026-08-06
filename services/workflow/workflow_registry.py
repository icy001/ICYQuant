"""Workflow Registry — versioned storage and discovery of workflow definitions.

The :class:`WorkflowRegistry` maintains a multi-version store of workflow
definitions. It supports:

* Registration with version control
* Multi-version lookup (latest, specific version, or grayscale)
* Deprecation marking
* Discovery by tags, owner, and status
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_definition import WorkflowDefinition, WorkflowStatus

logger = logging.getLogger(__name__)


class RegistryEntry:
    """A single entry in the registry, tracking a workflow and its versions."""

    def __init__(self, definition: WorkflowDefinition) -> None:
        self.name = definition.name
        self.versions: Dict[str, WorkflowDefinition] = {}
        self.add_version(definition)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_version(self, definition: WorkflowDefinition) -> None:
        self.versions[definition.version] = definition
        self.updated_at = datetime.utcnow()

    def get_latest(self) -> Optional[WorkflowDefinition]:
        """Return the latest non-deprecated version, preferring ACTIVE."""
        active = [v for v in self.versions.values() if v.status == WorkflowStatus.ACTIVE]
        if active:
            return active[-1]
        non_deprecated = [v for v in self.versions.values() if v.status != WorkflowStatus.DEPRECATED]
        if non_deprecated:
            return non_deprecated[-1]
        # Fallback to any version
        versions = list(self.versions.values())
        return versions[-1] if versions else None

    def get_version(self, version: str) -> Optional[WorkflowDefinition]:
        return self.versions.get(version)

    @property
    def version_count(self) -> int:
        return len(self.versions)


class WorkflowRegistry:
    """Versioned, thread-safe registry for workflow definitions.

    Supports multi-version storage, lookup, and discovery of workflow
    definitions.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, RegistryEntry] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, definition: WorkflowDefinition) -> str:
        """Register a workflow definition.

        Returns the workflow name (identifier).
        """
        name = definition.name
        with self._lock:
            if name in self._entries:
                self._entries[name].add_version(definition)
                logger.info("Registry: updated workflow %s version %s", name, definition.version)
            else:
                self._entries[name] = RegistryEntry(definition)
                logger.info("Registry: registered new workflow %s version %s", name, definition.version)
        return name

    async def deregister(self, workflow_id: str) -> None:
        """Remove a workflow entirely from the registry."""
        with self._lock:
            self._entries.pop(workflow_id, None)
            logger.info("Registry: deregistered workflow %s", workflow_id)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def get(
        self,
        workflow_id: str,
        *,
        version: Optional[str] = None,
    ) -> Optional[WorkflowDefinition]:
        """Retrieve a workflow definition by name and optional version."""
        with self._lock:
            entry = self._entries.get(workflow_id)
            if entry is None:
                return None
            if version:
                return entry.get_version(version)
            return entry.get_latest()

    async def get_latest(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Return the latest (preferred) version of a workflow."""
        return await self.get(workflow_id)

    async def list_versions(self, workflow_id: str) -> List[str]:
        """List all registered versions for a workflow."""
        with self._lock:
            entry = self._entries.get(workflow_id)
            if entry is None:
                return []
            return sorted(entry.versions.keys())

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def list_all(
        self,
        *,
        status: Optional[WorkflowStatus] = None,
        tag: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> List[WorkflowDefinition]:
        """List workflow definitions, optionally filtered."""
        results: List[WorkflowDefinition] = []
        with self._lock:
            for entry in self._entries.values():
                latest = entry.get_latest()
                if latest is None:
                    continue
                if status and latest.status != status:
                    continue
                if tag and tag not in latest.tags:
                    continue
                if owner and latest.owner != owner:
                    continue
                results.append(latest)
        return results

    async def list_names(self) -> List[str]:
        """Return all registered workflow names."""
        with self._lock:
            return sorted(self._entries.keys())

    async def exists(self, workflow_id: str) -> bool:
        """Check if a workflow is registered."""
        with self._lock:
            return workflow_id in self._entries

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def set_status(self, workflow_id: str, status: WorkflowStatus) -> bool:
        """Update the status of the latest version of a workflow."""
        with self._lock:
            entry = self._entries.get(workflow_id)
            if entry is None:
                return False
            latest = entry.get_latest()
            if latest is None:
                return False
            # Since WorkflowDefinition is frozen, create a new version entry
            new_def = WorkflowDefinition(
                name=latest.name,
                version=latest.version,
                nodes=list(latest.nodes),
                edges=list(latest.edges),
                config=latest.config,
                metadata=latest.metadata,
                status=status,
                tags=list(latest.tags),
                owner=latest.owner,
                updated_at=datetime.utcnow(),
            )
            entry.add_version(new_def)
            return True

    async def deprecate(self, workflow_id: str, message: str = "") -> bool:
        """Mark the latest version of a workflow as deprecated."""
        return await self.set_status(workflow_id, WorkflowStatus.DEPRECATED)

    async def archive(self, workflow_id: str) -> bool:
        """Archive a workflow."""
        return await self.set_status(workflow_id, WorkflowStatus.ARCHIVED)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def total_workflows(self) -> int:
        with self._lock:
            return len(self._entries)

    async def total_versions(self) -> int:
        with self._lock:
            return sum(entry.version_count for entry in self._entries.values())

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_workflows": len(self._entries),
                "total_versions": sum(e.version_count for e in self._entries.values()),
                "workflows": sorted(self._entries.keys()),
            }
