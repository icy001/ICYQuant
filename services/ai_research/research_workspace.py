"""
ICYQuant Research Workspace — multi-session research environment.

Manages multiple concurrent research sessions, workspace-level context
sharing, and cross-session resource organization.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ai_research.research_session import ResearchSession, SessionStatus

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceConfig:
    max_sessions: int = 50
    enable_cross_session_context: bool = True
    auto_archive_after_hours: int = 24
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchWorkspace:
    """Multi-session research workspace.

    Responsibilities:
        - Manage multiple concurrent research sessions
        - Cross-session context sharing
        - Workspace-level artifact organization
        - Session lifecycle management
    """

    def __init__(self, config: Optional[WorkspaceConfig] = None) -> None:
        self._config = config or WorkspaceConfig()
        self._sessions: dict[str, ResearchSession] = {}
        self._shared_context: dict[str, Any] = {}
        self._workspace_id = str(uuid.uuid4())
        self._created_at = datetime.now(timezone.utc)

    def create_session(self, user_id: str, title: str = "") -> ResearchSession:
        """Create a new research session."""
        if len(self._sessions) >= self._config.max_sessions:
            self._evict_oldest_archived()

        session = ResearchSession(user_id=user_id, title=title)
        self._sessions[session.session_id] = session
        logger.debug("Session %s created in workspace %s", session.session_id, self._workspace_id)
        return session

    def get_or_create_session(self, user_id: str) -> ResearchSession:
        """Get the most recent active session for a user, or create one."""
        for session in reversed(list(self._sessions.values())):
            if session.user_id == user_id and session.is_active:
                return session
        return self.create_session(user_id)

    def get_session(self, session_id: str) -> Optional[ResearchSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def add_session(self, session: ResearchSession) -> None:
        """Register an externally-created session."""
        self._sessions[session.session_id] = session

    def close_session(self, session_id: str) -> bool:
        """Close and archive a session."""
        session = self._sessions.get(session_id)
        if session:
            session.complete()
            return True
        return False

    def archive_session(self, session_id: str) -> bool:
        """Archive a completed session."""
        session = self._sessions.get(session_id)
        if session:
            session.archive()
            return True
        return False

    def set_shared_context(self, key: str, value: Any) -> None:
        """Set workspace-level shared context."""
        if self._config.enable_cross_session_context:
            self._shared_context[key] = value

    def get_shared_context(self, key: str) -> Any:
        """Get workspace-level shared context."""
        return self._shared_context.get(key)

    def list_active_sessions(self) -> list[ResearchSession]:
        """Return all currently active sessions."""
        return [s for s in self._sessions.values() if s.is_active]

    def list_sessions_by_user(self, user_id: str) -> list[ResearchSession]:
        """Return all sessions for a given user."""
        return [s for s in self._sessions.values() if s.user_id == user_id]

    def _evict_oldest_archived(self) -> None:
        """Evict the oldest archived session when at capacity."""
        archived = [s for s in self._sessions.values() if s.status == SessionStatus.ARCHIVED]
        if archived:
            oldest = min(archived, key=lambda s: s.updated_at)
            del self._sessions[oldest.session_id]
            logger.info("Evicted archived session %s from workspace", oldest.session_id)
        else:
            # Fallback: evict the oldest completed session
            completed = [s for s in self._sessions.values() if s.status == SessionStatus.COMPLETED]
            if completed:
                oldest = min(completed, key=lambda s: s.updated_at)
                del self._sessions[oldest.session_id]
                logger.info("Evicted completed session %s from workspace", oldest.session_id)

    @property
    def active_session_count(self) -> int:
        return len(self.list_active_sessions())

    @property
    def total_session_count(self) -> int:
        return len(self._sessions)

    @property
    def workspace_id(self) -> str:
        return self._workspace_id
