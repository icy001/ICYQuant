"""
Session Pool — Connection session pool for reusing exchange sessions
to reduce connection establishment overhead.

Exchange → Connection Pool → Acquire → Reuse → Release
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .exchange_session import ExchangeSession, SessionState, SessionType

logger = logging.getLogger(__name__)


@dataclass
class SessionPoolConfig:
    """Configuration for session pool behavior."""
    pool_id: str = "default"
    min_sessions: int = 1
    max_sessions: int = 10
    idle_timeout_seconds: float = 300.0
    max_session_age_seconds: float = 3600.0
    connection_timeout: float = 10.0
    health_check_interval: float = 30.0
    cleanup_interval: float = 60.0


class SessionPool:
    """
    Session pool for reusing exchange connections.

    Maintains a pool of ready-to-use sessions, allowing callers
    to acquire, use, and release sessions without re-establishing
    connections each time.

    Usage::

        pool = SessionPool(SessionPoolConfig(pool_id="binance_pool"))
        await pool.initialize()
        session = await pool.acquire("binance", SessionType.MARKET_DATA)
        # ... use session ...
        await pool.release(session)
    """

    def __init__(self, config: Optional[SessionPoolConfig] = None) -> None:
        self.config = config or SessionPoolConfig()
        self._sessions: dict[str, list[ExchangeSession]] = {}
        self._in_use: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the session pool."""
        logger.info("SessionPool '%s' initialized.", self.config.pool_id)

    async def start(self) -> None:
        """Start the pool background tasks."""
        if self.config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the pool and drain all sessions."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self.drain()
        logger.info("SessionPool '%s' stopped.", self.config.pool_id)

    # ---- Session Management ----

    async def acquire(
        self,
        exchange_id: str,
        session_type: SessionType = SessionType.MARKET_DATA,
        **kwargs: Any,
    ) -> Optional[ExchangeSession]:
        """Acquire a session from the pool."""
        async with self._lock:
            pool_key = f"{exchange_id}_{session_type.value}"
            available = self._sessions.get(pool_key, [])
            in_use = self._in_use.get(pool_key, set())

            # Try to find a healthy idle session
            for session in available:
                if session.session_id not in in_use and session.state == SessionState.CONNECTED:
                    in_use.add(session.session_id)
                    self._in_use[pool_key] = in_use
                    logger.debug("Acquired session %s from pool", session.session_id)
                    return session

        logger.debug("No available session in pool for %s/%s", exchange_id, session_type.value)
        return None

    async def release(self, session: ExchangeSession) -> bool:
        """Release a session back to the pool."""
        pool_key = f"{session.exchange_id}_{session.session_type.value}"
        async with self._lock:
            in_use = self._in_use.get(pool_key, set())
            in_use.discard(session.session_id)
            self._in_use[pool_key] = in_use

            available = self._sessions.setdefault(pool_key, [])
            if session not in available:
                available.append(session)

            session.last_activity = datetime.now(timezone.utc)
            logger.debug("Released session %s to pool", session.session_id)
            return True

    async def add_session(self, session: ExchangeSession) -> None:
        """Add a new session to the pool."""
        pool_key = f"{session.exchange_id}_{session.session_type.value}"
        async with self._lock:
            available = self._sessions.setdefault(pool_key, [])
            if len(available) < self.config.max_sessions:
                available.append(session)
                logger.debug("Added session %s to pool", session.session_id)

    async def remove_session(self, session: ExchangeSession) -> bool:
        """Remove a session from the pool."""
        pool_key = f"{session.exchange_id}_{session.session_type.value}"
        async with self._lock:
            available = self._sessions.get(pool_key, [])
            if session in available:
                available.remove(session)
                in_use = self._in_use.get(pool_key, set())
                in_use.discard(session.session_id)
                return True
            return False

    async def drain(self) -> None:
        """Drain all sessions from the pool."""
        async with self._lock:
            for pool_key, sessions in self._sessions.items():
                for session in sessions:
                    if session.state == SessionState.CONNECTED:
                        session.state = SessionState.CLOSING
                sessions.clear()
            self._in_use.clear()
            logger.info("SessionPool drained.")

    # ---- Pool Status ----

    async def get_status(self) -> dict[str, Any]:
        """Get pool status summary."""
        total_available = sum(len(s) for s in self._sessions.values())
        total_in_use = sum(len(u) for u in self._in_use.values())

        pools = {}
        for key, sessions in self._sessions.items():
            in_use_count = len(self._in_use.get(key, set()))
            pools[key] = {
                "available": len(sessions),
                "in_use": in_use_count,
                "total": len(sessions) + in_use_count,
            }

        return {
            "pool_id": self.config.pool_id,
            "total_available": total_available,
            "total_in_use": total_in_use,
            "config": {
                "min_sessions": self.config.min_sessions,
                "max_sessions": self.config.max_sessions,
                "idle_timeout_seconds": self.config.idle_timeout_seconds,
            },
            "pools": pools,
        }

    async def _cleanup_loop(self) -> None:
        """Background task to clean up idle and expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Session pool cleanup error")

    async def _cleanup_idle_sessions(self) -> None:
        """Remove idle and expired sessions."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            for pool_key, sessions in list(self._sessions.items()):
                in_use = self._in_use.get(pool_key, set())
                for session in list(sessions):
                    if session.session_id in in_use:
                        continue
                    # Check idle timeout
                    if session.last_activity:
                        idle_seconds = (now - session.last_activity).total_seconds()
                        if idle_seconds > self.config.idle_timeout_seconds:
                            sessions.remove(session)
                            logger.debug("Removed idle session %s", session.session_id)
                    # Check max age
                    age_seconds = (now - session.created_at).total_seconds()
                    if age_seconds > self.config.max_session_age_seconds:
                        if session in sessions:
                            sessions.remove(session)
                            logger.debug("Removed expired session %s", session.session_id)
