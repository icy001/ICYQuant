"""Session Orchestrator — manages multi-turn agent sessions with context preservation.

The SessionOrchestrator coordinates multi-turn interactions across agents,
preserving conversation context, managing session state, and enabling seamless
handoff between agents within a single user session.

Key capabilities:
    - Session lifecycle (create, resume, close, expire)
    - Multi-agent coordination within a session
    - Context preservation across turns
    - Session-level memory isolation
    - Idle timeout and automatic cleanup
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """States of a managed session."""
    ACTIVE = "active"
    IDLE = "idle"
    CLOSING = "closing"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass
class SessionTurn:
    """A single turn within a session."""
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    request: Dict[str, Any] = field(default_factory=dict)
    response: Optional[Dict[str, Any]] = None
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at) * 1000


@dataclass
class Session:
    """A multi-turn agent interaction session."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    user_id: str = ""
    state: SessionState = SessionState.ACTIVE
    turns: List[SessionTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    active_agents: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionOrchestrator:
    """Orchestrates multi-turn agent sessions with context preservation.

    Manages session lifecycle, coordinates multiple agents within a session,
    and preserves conversation context across turns.

    Usage:
        so = SessionOrchestrator(idle_timeout_sec=1800)
        await so.initialize()
        session = await so.create_session(user_id="user_1")
        await so.add_turn(session.session_id, agent_id, request)
        await so.close_session(session.session_id)
    """

    def __init__(self, idle_timeout_sec: float = 1800.0, max_sessions: int = 10000) -> None:
        self._idle_timeout_sec = idle_timeout_sec
        self._max_sessions = max_sessions
        self._sessions: Dict[str, Session] = {}
        self._initialized: bool = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        logger.info("SessionOrchestrator created (timeout=%ds, max=%d)", idle_timeout_sec, max_sessions)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionOrchestrator initialized")

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            for session in self._sessions.values():
                session.state = SessionState.CLOSED
            self._sessions.clear()
        self._initialized = False
        logger.info("SessionOrchestrator shutdown complete")

    async def create_session(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Session:
        """Create a new session for a user."""
        async with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise RuntimeError(f"Maximum sessions reached ({self._max_sessions})")
            session = Session(user_id=user_id, metadata=metadata or {})
            self._sessions[session.session_id] = session
            logger.info("SessionOrchestrator: created session %s for user %s", session.session_id, user_id)
            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def add_turn(self, session_id: str, agent_id: str, request: Dict[str, Any], response: Optional[Dict[str, Any]] = None) -> Optional[SessionTurn]:
        """Record a turn in a session."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.state not in (SessionState.ACTIVE, SessionState.IDLE):
                logger.warning("SessionOrchestrator: session %s not available", session_id)
                return None

            turn = SessionTurn(agent_id=agent_id, request=request, response=response)
            if response:
                turn.completed_at = time.monotonic()
            session.turns.append(turn)
            session.last_active = time.monotonic()
            session.state = SessionState.ACTIVE

            if agent_id not in session.active_agents:
                session.active_agents.append(agent_id)

            return turn

    async def update_context(self, session_id: str, context_updates: Dict[str, Any]) -> bool:
        """Update session-level context."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.context.update(context_updates)
            return True

    async def close_session(self, session_id: str) -> bool:
        """Close a session gracefully."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.state = SessionState.CLOSED
            logger.info("SessionOrchestrator: closed session %s", session_id)
            return True

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(60)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("SessionOrchestrator cleanup error: %s", e)

    async def _cleanup_expired(self) -> None:
        """Remove sessions that have been idle too long."""
        now = time.monotonic()
        async with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if s.state == SessionState.IDLE and (now - s.last_active) > self._idle_timeout_sec
            ]
            for sid in expired:
                self._sessions[sid].state = SessionState.EXPIRED
                del self._sessions[sid]
            if expired:
                logger.info("SessionOrchestrator: cleaned up %d expired sessions", len(expired))

    def get_summary(self) -> Dict[str, Any]:
        states: Dict[str, int] = {}
        for s in self._sessions.values():
            states[s.state.value] = states.get(s.state.value, 0) + 1
        return {
            "initialized": self._initialized,
            "total_sessions": len(self._sessions),
            "by_state": states,
            "idle_timeout_sec": self._idle_timeout_sec,
        }
