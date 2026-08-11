"""
Paper Manager
=============
Coordinates paper trading sessions, manages lifecycle, and publishes
events to external consumers (monitoring, dashboards, alerts).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ManagerEvent(str, Enum):
    """Paper trading manager events."""
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"
    SESSION_TERMINATED = "session_terminated"
    SESSION_ERROR = "session_error"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    TRADE_EXECUTED = "trade_executed"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    EVALUATION_COMPLETE = "evaluation_complete"
    PROMOTION_INITIATED = "promotion_initiated"


@dataclass
class ManagerEventData:
    """Event payload for paper trading manager events."""
    event: ManagerEvent
    session_id: str = ""
    strategy_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperManager:
    """Coordinates paper trading sessions and publishes events."""

    def __init__(self):
        self._engine: Optional["PaperTradingEngine"] = None
        self._sessions: Dict[str, "PaperSession"] = {}
        self._listeners: Dict[ManagerEvent, List[Callable[[ManagerEventData], Any]]] = {}
        self._event_log: List[ManagerEventData] = []
        self._max_event_log = 1000
        self.is_initialized = False

    def wire(self, engine: Optional[Any] = None) -> None:
        """Wire to the paper trading engine."""
        self._engine = engine
        logger.info("PaperManager wired")

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("PaperManager initialized")

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    async def register_session(self, session: Any) -> None:
        """Register a paper trading session."""
        self._sessions[session.session_id] = session
        await self._emit(ManagerEvent.SESSION_CREATED, session.session_id,
                         getattr(session, 'strategy_id', ''),
                         {"session": session.to_dict() if hasattr(session, 'to_dict') else {}})

    async def start_session(self, session_id: str) -> None:
        """Start a registered session."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("Cannot start unknown session: %s", session_id)
            return
        session.started_at = datetime.now(timezone.utc)
        session.status = "running"
        await self._emit(ManagerEvent.SESSION_STARTED, session_id,
                         getattr(session, 'strategy_id', ''))

    async def complete_session(self, session_id: str) -> None:
        """Mark a session as complete."""
        session = self._sessions.get(session_id)
        if session:
            session.complete()
        await self._emit(ManagerEvent.SESSION_COMPLETED, session_id,
                         getattr(session, 'strategy_id', ''))

    # ------------------------------------------------------------------
    # Order Events
    # ------------------------------------------------------------------

    async def on_order_submitted(self, session_id: str, strategy_id: str,
                                 order: Any) -> None:
        """Notify that an order was submitted."""
        await self._emit(ManagerEvent.ORDER_SUBMITTED, session_id, strategy_id,
                         {"order_id": getattr(order, 'order_id', '')})

    async def on_order_filled(self, session_id: str, strategy_id: str,
                              trade: Any) -> None:
        """Notify that an order was filled."""
        await self._emit(ManagerEvent.ORDER_FILLED, session_id, strategy_id,
                         {"trade_id": getattr(trade, 'trade_id', ''),
                          "instrument": getattr(trade, 'instrument', ''),
                          "quantity": getattr(trade, 'quantity', 0)})

    async def on_kill_switch(self, session_id: str, strategy_id: str,
                             reason: str = "") -> None:
        """Notify that kill switch was triggered."""
        await self._emit(ManagerEvent.KILL_SWITCH_TRIGGERED, session_id, strategy_id,
                         {"reason": reason})

    # ------------------------------------------------------------------
    # Event System
    # ------------------------------------------------------------------

    def subscribe(self, event: ManagerEvent,
                  callback: Callable[[ManagerEventData], Any]) -> None:
        """Subscribe to a manager event."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def unsubscribe(self, event: ManagerEvent,
                    callback: Callable[[ManagerEventData], Any]) -> None:
        """Unsubscribe from a manager event."""
        if event in self._listeners and callback in self._listeners[event]:
            self._listeners[event].remove(callback)

    async def _emit(self, event: ManagerEvent, session_id: str,
                    strategy_id: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit an event to all listeners."""
        event_data = ManagerEventData(
            event=event,
            session_id=session_id,
            strategy_id=strategy_id,
            data=data or {},
        )
        self._event_log.append(event_data)
        if len(self._event_log) > self._max_event_log:
            self._event_log = self._event_log[-self._max_event_log:]

        callbacks = self._listeners.get(event, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event_data)
                else:
                    cb(event_data)
            except Exception:
                logger.exception("Listener callback failed for event %s", event)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def active_sessions(self) -> List[str]:
        return [sid for sid, s in self._sessions.items()
                if getattr(s, 'status', '') in ('initialized', 'running')]

    def session_count(self) -> int:
        return len(self._sessions)

    def recent_events(self, limit: int = 50) -> List[ManagerEventData]:
        return self._event_log[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": len(self.active_sessions()),
            "events_logged": len(self._event_log),
            "listener_count": sum(len(v) for v in self._listeners.values()),
        }
