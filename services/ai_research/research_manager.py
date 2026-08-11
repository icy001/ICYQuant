"""
ICYQuant Research Manager — lifecycle management for research sessions and resources.

Handles session CRUD, resource allocation, cleanup policies, and
operational state management across all active research contexts.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ManagerConfig:
    max_sessions: int = 100
    session_ttl_minutes: int = 480  # 8 hours
    cleanup_interval_seconds: int = 600
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchManager:
    """Manages the lifecycle of research resources.

    Responsibilities:
        - Session lifecycle (create, get, close, expire)
        - Resource usage tracking
        - Periodic cleanup of expired sessions
        - Quota enforcement
    """

    def __init__(self, config: Optional[ManagerConfig] = None) -> None:
        self._config = config or ManagerConfig()
        self._sessions: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._total_created = 0
        self._total_closed = 0

    def register_session(self, session_id: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Register a new research session, returning its ID."""
        if len(self._sessions) >= self._config.max_sessions:
            self._evict_oldest()

        self._sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(timezone.utc),
            "last_active": datetime.now(timezone.utc),
            "status": "active",
            "metadata": metadata or {},
        }
        # Move to end (most recently used)
        self._sessions.move_to_end(session_id)
        self._total_created += 1
        logger.debug("Session %s registered", session_id)
        return session_id

    def touch_session(self, session_id: str) -> None:
        """Update last-active timestamp for a session."""
        if session_id in self._sessions:
            self._sessions[session_id]["last_active"] = datetime.now(timezone.utc)
            self._sessions.move_to_end(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a session and remove it from management."""
        if session_id in self._sessions:
            self._sessions[session_id]["status"] = "closed"
            self._sessions[session_id]["closed_at"] = datetime.now(timezone.utc)
            self._total_closed += 1
            logger.debug("Session %s closed", session_id)
            return True
        return False

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session metadata by ID."""
        return self._sessions.get(session_id)

    def list_active_sessions(self) -> list[dict[str, Any]]:
        """List all currently active sessions."""
        return [
            s for s in self._sessions.values()
            if s.get("status") == "active"
        ]

    def cleanup_expired(self) -> int:
        """Remove sessions that have exceeded the TTL."""
        now = datetime.now(timezone.utc)
        ttl = timedelta(minutes=self._config.session_ttl_minutes)
        expired_ids = [
            sid for sid, s in self._sessions.items()
            if s.get("status") == "active" and (now - s["last_active"]) > ttl
        ]
        for sid in expired_ids:
            self.close_session(sid)
            del self._sessions[sid]
        if expired_ids:
            logger.info("Cleaned up %d expired sessions", len(expired_ids))
        return len(expired_ids)

    def _evict_oldest(self) -> None:
        """Evict the oldest inactive session when at capacity."""
        for sid, s in list(self._sessions.items()):
            if s.get("status") == "active":
                # Keep only the first (oldest) active session's key
                pass
        # Evict the first entry (oldest by insertion order)
        if self._sessions:
            oldest_id = next(iter(self._sessions))
            self.close_session(oldest_id)
            del self._sessions[oldest_id]
            logger.info("Evicted oldest session %s due to capacity", oldest_id)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.get("status") == "active")

    @property
    def total_created(self) -> int:
        return self._total_created

    @property
    def total_closed(self) -> int:
        return self._total_closed
