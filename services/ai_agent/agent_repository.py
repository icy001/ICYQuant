"""
Agent state persistence repository.

Provides CRUD operations, filtering, and archiving for agent states,
configurations, and execution records.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Agent Record ──


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    REGISTERED = "registered"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"
    ARCHIVED = "archived"


@dataclass
class AgentRecord:
    """Persistent record of an agent instance."""

    agent_id: str
    agent_type: str
    name: str
    status: AgentStatus = AgentStatus.REGISTERED
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: Optional[datetime] = None
    version: str = "1.0.0"
    execution_count: int = 0
    error_count: int = 0

    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active_at = datetime.now(timezone.utc)

    def increment_execution(self) -> None:
        """Increment execution counter."""
        self.execution_count += 1
        self.touch()

    def increment_error(self) -> None:
        """Increment error counter."""
        self.error_count += 1
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "status": self.status.value,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "version": self.version,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
        }


# ── Agent Repository ──


class AgentRepository:
    """Repository for agent record persistence and querying.

    Provides in-memory storage with filtering and archiving capabilities.
    In production, this delegates to a database adapter.

    Usage:
        repo = AgentRepository()
        repo.save(AgentRecord(...))
        agents = repo.find_by_status(AgentStatus.ACTIVE)
    """

    def __init__(self) -> None:
        self._store: Dict[str, AgentRecord] = {}
        self._archive: Dict[str, AgentRecord] = {}
        logger.info("AgentRepository initialized")

    # ── CRUD Operations ──

    def save(self, record: AgentRecord) -> AgentRecord:
        """Save or update an agent record."""
        record.updated_at = datetime.now(timezone.utc)
        self._store[record.agent_id] = record
        logger.debug(f"Saved agent record: {record.agent_id}")
        return record

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        """Get agent by ID."""
        return self._store.get(agent_id)

    def get_all(self) -> List[AgentRecord]:
        """Get all active (non-archived) agent records."""
        return list(self._store.values())

    def get_or_create(
        self,
        agent_id: str,
        agent_type: str,
        name: str,
        **kwargs: Any,
    ) -> AgentRecord:
        """Get existing agent or create a new record."""
        if agent_id in self._store:
            return self._store[agent_id]

        record = AgentRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            name=name,
            **kwargs,
        )
        return self.save(record)

    def delete(self, agent_id: str) -> bool:
        """Remove an agent record entirely (hard delete)."""
        if agent_id in self._store:
            del self._store[agent_id]
            logger.info(f"Deleted agent record: {agent_id}")
            return True
        return False

    def archive(self, agent_id: str) -> bool:
        """Archive an agent record (soft delete)."""
        record = self._store.pop(agent_id, None)
        if record:
            record.status = AgentStatus.ARCHIVED
            self._archive[agent_id] = record
            logger.info(f"Archived agent record: {agent_id}")
            return True
        return False

    def restore(self, agent_id: str) -> bool:
        """Restore an archived agent record."""
        record = self._archive.pop(agent_id, None)
        if record:
            record.status = AgentStatus.IDLE
            self._store[agent_id] = record
            logger.info(f"Restored agent record: {agent_id}")
            return True
        return False

    # ── Queries ──

    def find_by_type(self, agent_type: str) -> List[AgentRecord]:
        """Find agents by type."""
        return [r for r in self._store.values() if r.agent_type == agent_type]

    def find_by_status(self, status: AgentStatus) -> List[AgentRecord]:
        """Find agents by status."""
        return [r for r in self._store.values() if r.status == status]

    def find_by_tag(self, tag: str) -> List[AgentRecord]:
        """Find agents by tag."""
        return [r for r in self._store.values() if tag in r.tags]

    def find_active(self) -> List[AgentRecord]:
        """Find all currently active agents."""
        return [
            r for r in self._store.values()
            if r.status in (AgentStatus.ACTIVE, AgentStatus.BUSY)
        ]

    def find_idle(self) -> List[AgentRecord]:
        """Find all idle agents available for work."""
        return [r for r in self._store.values() if r.status == AgentStatus.IDLE]

    # ── Status Updates ──

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status."""
        record = self._store.get(agent_id)
        if record:
            record.status = status
            record.updated_at = datetime.now(timezone.utc)
            logger.debug(f"Updated agent [{agent_id}] status to {status.value}")
            return True
        return False

    def update_config(self, agent_id: str, config: Dict[str, Any]) -> bool:
        """Update agent configuration."""
        record = self._store.get(agent_id)
        if record:
            record.config.update(config)
            record.updated_at = datetime.now(timezone.utc)
            return True
        return False

    # ── Summary ──

    def get_summary(self) -> Dict[str, Any]:
        """Get repository summary statistics."""
        all_records = list(self._store.values())
        status_counts: Dict[str, int] = {}
        for r in all_records:
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

        return {
            "total_active": len(all_records),
            "total_archived": len(self._archive),
            "by_status": status_counts,
            "total_executions": sum(r.execution_count for r in all_records),
            "total_errors": sum(r.error_count for r in all_records),
        }
