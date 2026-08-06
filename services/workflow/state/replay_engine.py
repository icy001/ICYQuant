"""Replay engine — replay workflow execution from stored events.

Supports: full workflow replay, node replay, replay until time/event.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from .event_store import EventStore, StoredEvent
from .event_sourcing import EventSourcingEngine
from .workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class ReplayEngine:
    """Replay workflow execution from event history.

    Replay modes:
      - Replay Workflow: full execution replay
      - Replay Node: single node replay
      - Replay Until Time: replay up to a timestamp
      - Replay Until Event: replay up to a specific event
    """

    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        event_sourcing: Optional[EventSourcingEngine] = None,
    ):
        self._event_store = event_store or EventStore()
        self._event_sourcing = event_sourcing or EventSourcingEngine(self._event_store)

    # ---- Replay modes -------------------------------------------------------

    async def replay_workflow(self, execution_id: str) -> Optional[WorkflowState]:
        """Replay the full workflow execution."""
        logger.info("Replaying full workflow: %s", execution_id)
        return await self._event_sourcing.rebuild_state(execution_id)

    async def replay_node(
        self, execution_id: str, node_id: str
    ) -> List[StoredEvent]:
        """Replay events for a single node."""
        events = await self._event_store.get_node_events(execution_id, node_id)
        logger.info("Replaying node %s/%s: %d events", execution_id, node_id, len(events))
        return events

    async def replay_until_time(
        self, execution_id: str, until: datetime
    ) -> Optional[WorkflowState]:
        """Replay workflow state as it was at a specific timestamp."""
        logger.info("Replaying %s until %s", execution_id, until.isoformat())
        return await self._event_sourcing.get_state_at_time(execution_id, until)

    async def replay_until_event(
        self, execution_id: str, event_id: str
    ) -> Optional[WorkflowState]:
        """Replay workflow state just before a specific event."""
        logger.info("Replaying %s before event %s", execution_id, event_id)
        return await self._event_sourcing.get_state_before_event(execution_id, event_id)

    # ---- Streaming replay ---------------------------------------------------

    async def stream_replay(
        self, execution_id: str, since_version: int = 0
    ) -> AsyncIterator[StoredEvent]:
        """Stream events for replay, useful for incremental consumers."""
        events = await self._event_store.get_events(execution_id, since_version=since_version)
        for event in events:
            yield event

    async def replay_from_journal(self, execution_id: str) -> Optional[WorkflowState]:
        """Replay state entirely from journal entries."""
        logger.info("Replaying %s from journal", execution_id)
        return await self._event_sourcing.rebuild_from_journal(execution_id)

    # ---- Analysis -----------------------------------------------------------

    async def analyze_timeline(
        self, execution_id: str
    ) -> Dict[str, Any]:
        """Generate a timeline analysis of the execution."""
        events = await self._event_store.get_events(execution_id)
        if not events:
            return {"execution_id": execution_id, "events": 0}

        start = events[0].timestamp
        end = events[-1].timestamp
        duration = (end - start).total_seconds()

        node_timings = {}
        for e in events:
            if e.node_id and e.event_type == "node_state_changed":
                if e.node_id not in node_timings:
                    node_timings[e.node_id] = {"start": e.timestamp, "end": e.timestamp}
                node_timings[e.node_id]["end"] = e.timestamp

        return {
            "execution_id": execution_id,
            "total_events": len(events),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_seconds": duration,
            "nodes": {
                nid: {
                    "start": ts["start"].isoformat(),
                    "end": ts["end"].isoformat(),
                    "duration": (ts["end"] - ts["start"]).total_seconds(),
                }
                for nid, ts in node_timings.items()
            },
        }
