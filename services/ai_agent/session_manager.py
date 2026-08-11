"""
Session manager for multi-agent conversation and task sessions.

Manages session lifecycle, context preservation, and history tracking
across agent interactions with support for multi-agent concurrency.

Session model:
    Session → Context → Memory → Task → History
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.exceptions import ICYQuantError

from services.ai_agent.agent_context import AgentContext

logger = logging.getLogger(__name__)


# ── Session Types ──


class SessionStatus(str, Enum):
    """Session lifecycle status."""

    CREATED = "created"
    ACTIVE = "active"
    IDLE = "idle"
    COMPLETED = "completed"
    EXPIRED = "expired"
    TERMINATED = "terminated"


@dataclass
class Session:
    """An agent interaction session.

    Tracks conversation context, memory references, and execution
    history for a single user interaction or multi-step task.
    """

    session_id: str = field(default_factory=lambda: uuid4().hex)
    status: SessionStatus = SessionStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: Optional[datetime] = None
    ttl_seconds: Optional[int] = 3600  # 1 hour default
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    contexts: List[str] = field(default_factory=list)  # context_id references
    message_count: int = 0
    task_count: int = 0
    error_count: int = 0

    def touch(self) -> None:
        """Mark session as recently active."""
        self.last_active_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def add_context(self, context_id: str) -> None:
        """Associate a context snapshot with this session."""
        self.contexts.append(context_id)

    def increment_messages(self, count: int = 1) -> None:
        """Increment message counter."""
        self.message_count += count
        self.touch()

    def increment_tasks(self, count: int = 1) -> None:
        """Increment task counter."""
        self.task_count += count
        self.touch()

    @property
    def is_expired(self) -> bool:
        """Check if session has exceeded TTL."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Session age in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "message_count": self.message_count,
            "task_count": self.task_count,
            "error_count": self.error_count,
            "age_seconds": self.age_seconds,
            "tags": self.tags,
            "context_count": len(self.contexts),
        }


# ── Session Manager ──


class SessionManager:
    """Manager for agent session lifecycle and concurrency.

    Handles session creation, retrieval, expiry, and cleanup
    for multi-agent concurrent operations.

    Usage:
        manager = SessionManager(max_sessions=1000)
        session = await manager.create_session()
        retrieved = await manager.get_session(session.session_id)
        await manager.expire_session(session.session_id)
    """

    def __init__(self, max_sessions: int = 1000, cleanup_interval: float = 60.0) -> None:
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval
        self._sessions: Dict[str, Session] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._stats: Dict[str, int] = {
            "created": 0,
            "completed": 0,
            "expired": 0,
            "terminated": 0,
        }
        logger.info("SessionManager created")

    # ── Lifecycle ──

    async def start(self) -> None:
        """Start the session manager and background cleanup."""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionManager started")

    async def stop(self) -> None:
        """Stop the session manager and terminate all sessions."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Terminate all sessions
        for session_id in list(self._sessions.keys()):
            session = self._sessions[session_id]
            session.status = SessionStatus.TERMINATED
            self._stats["terminated"] += 1

        self._sessions.clear()
        logger.info("SessionManager stopped", extra={"stats": self._stats})

    # ── Session Operations ──

    async def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = 3600,
    ) -> Session:
        """Create a new session.

        Args:
            session_id: Optional explicit session ID.
            metadata: Session metadata.
            tags: Session tags for categorization.
            ttl_seconds: Time-to-live in seconds.

        Returns:
            New Session object.

        Raises:
            ICYQuantError: If max session limit is reached.
        """
        if len(self._sessions) >= self.max_sessions:
            raise ICYQuantError(
                f"Maximum session limit reached: {self.max_sessions}"
            )

        session = Session(
            session_id=session_id or uuid4().hex,
            metadata=metadata or {},
            tags=tags or [],
            ttl_seconds=ttl_seconds,
        )
        session.status = SessionStatus.ACTIVE
        self._sessions[session.session_id] = session
        self._stats["created"] += 1

        logger.info(f"Session created: {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            if session.is_expired:
                await self.expire_session(session_id)
                return None
            session.touch()
        return session

    async def complete_session(self, session_id: str) -> bool:
        """Mark a session as completed."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.status = SessionStatus.COMPLETED
        session.touch()
        self._stats["completed"] += 1
        logger.info(f"Session completed: {session_id}")
        return True

    async def expire_session(self, session_id: str) -> bool:
        """Expire a session and remove it."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.status = SessionStatus.EXPIRED
            self._stats["expired"] += 1
            logger.info(f"Session expired: {session_id}")
            return True
        return False

    async def terminate_session(self, session_id: str) -> bool:
        """Force terminate a session."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.status = SessionStatus.TERMINATED
            self._stats["terminated"] += 1
            logger.info(f"Session terminated: {session_id}")
            return True
        return False

    # ── Queries ──

    async def list_sessions(
        self,
        status: Optional[SessionStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return [s.to_dict() for s in sessions]

    def count_by_status(self) -> Dict[str, int]:
        """Count sessions grouped by status."""
        counts: Dict[str, int] = {}
        for session in self._sessions.values():
            counts[session.status.value] = counts.get(session.status.value, 0) + 1
        return counts

    # ── Cleanup ──

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                expired_ids = [
                    sid for sid, s in self._sessions.items() if s.is_expired
                ]
                for sid in expired_ids:
                    await self.expire_session(sid)
                if expired_ids:
                    logger.info(f"Cleaned up {len(expired_ids)} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Session cleanup error")

    # ── Stats ──

    def get_summary(self) -> Dict[str, Any]:
        """Get session manager summary."""
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self.max_sessions,
            "by_status": self.count_by_status(),
            "stats": dict(self._stats),
        }
