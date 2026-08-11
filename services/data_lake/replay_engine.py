"""
Replay Engine — historical market data replay as real-time streams
for backtesting, strategy validation, and research.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from .replay_context import ReplayContext, ReplayClock, ReplayMarketData
from .replay_checkpoint import ReplayCheckpoint

logger = logging.getLogger(__name__)


class ReplayState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ReplayConfig:
    replay_id: str = "icyquant-replay-engine"
    default_speed: float = 1.0
    max_speed: float = 1000.0
    min_speed: float = 0.001
    buffer_size: int = 10_000
    prefetch_count: int = 5
    checkpoint_interval_seconds: float = 60.0
    heartbeat_interval_seconds: float = 5.0


class ReplayEngine:
    """
    Replay historical market data as real-time streams.

    Supports tick-level, order-book-level, and trade-level replay
    with configurable speed, checkpointing, and pause/resume.

    Usage::

        engine = ReplayEngine(storage, catalog, config)
        async for event in engine.replay("equity_ticks", start, end, speed=2.0):
            strategy.on_market_data(event)
    """

    def __init__(
        self,
        storage: Any = None,
        catalog: Any = None,
        config: Optional[ReplayConfig] = None,
    ) -> None:
        self._storage = storage
        self._catalog = catalog
        self.config = config or ReplayConfig()
        self._state = ReplayState.CREATED
        self._checkpoint = ReplayCheckpoint()
        self._active_replays: dict[str, ReplayContext] = {}

    async def start(self) -> None:
        self._state = ReplayState.RUNNING
        logger.info("Replay Engine started")

    async def stop(self) -> None:
        self._state = ReplayState.STOPPED
        for ctx in self._active_replays.values():
            ctx.stop()
        self._active_replays.clear()
        logger.info("Replay Engine stopped")

    async def replay(
        self,
        dataset: str,
        start: datetime,
        end: datetime,
        *,
        speed: float = 1.0,
        checkpoint: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        """
        Replay historical data as a real-time stream.

        Args:
            dataset: Dataset to replay.
            start: Start of replay window.
            end: End of replay window.
            speed: Replay speed multiplier.
            checkpoint: Resume from saved checkpoint ID.

        Yields:
            Market data events in chronological order.
        """
        speed = max(self.config.min_speed, min(speed, self.config.max_speed))

        context = ReplayContext(
            dataset=dataset,
            start=start,
            end=end,
            speed=speed,
            checkpoint_id=checkpoint,
        )

        replay_id = context.replay_id
        self._active_replays[replay_id] = context

        logger.info(
            "Starting replay: %s [%s → %s] speed=%.2fx",
            dataset, start.isoformat(), end.isoformat(), speed,
        )

        try:
            # Load data from storage
            data = await self._load_replay_data(dataset, start, end, context)
            context.total_events = len(data)

            clock = ReplayClock(start, speed)
            last_checkpoint = datetime.now(timezone.utc)

            for i, event in enumerate(data):
                if context.is_stopped:
                    break

                while context.is_paused and not context.is_stopped:
                    await asyncio.sleep(0.1)

                # Advance clock
                event_time = self._get_event_time(event)
                if event_time:
                    await clock.wait_until(event_time)

                context.current_position = i
                yield event

                # Auto-checkpoint
                now = datetime.now(timezone.utc)
                if (now - last_checkpoint).total_seconds() >= self.config.checkpoint_interval_seconds:
                    await self._checkpoint.create(
                        replay_id=replay_id,
                        dataset=dataset,
                        position=i,
                        event_time=event_time,
                    )
                    last_checkpoint = now

            context.mark_completed()
            logger.info("Replay completed: %s (%d events)", replay_id, context.total_events)

        except Exception:
            logger.exception("Replay error: %s", replay_id)
            context.mark_error()
            raise
        finally:
            self._active_replays.pop(replay_id, None)

    async def _load_replay_data(
        self,
        dataset: str,
        start: datetime,
        end: datetime,
        context: ReplayContext,
    ) -> list[Any]:
        """Load historical data for replay from storage."""
        if self._storage:
            return await self._storage.read(
                f"datasets/{dataset}",
                filters=[{"column": "timestamp", "op": "gte", "value": start}],
            )
        return []

    def _get_event_time(self, event: Any) -> Optional[datetime]:
        """Extract timestamp from an event."""
        if hasattr(event, "timestamp"):
            return event.timestamp
        if isinstance(event, dict):
            ts = event.get("timestamp") or event.get("event_time")
            if ts:
                return ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
        return None

    async def pause(self, replay_id: str) -> bool:
        """Pause an active replay."""
        ctx = self._active_replays.get(replay_id)
        if ctx:
            ctx.pause()
            return True
        return False

    async def resume(self, replay_id: str) -> bool:
        """Resume a paused replay."""
        ctx = self._active_replays.get(replay_id)
        if ctx:
            ctx.resume()
            return True
        return False

    async def stop_replay(self, replay_id: str) -> bool:
        """Stop an active replay."""
        ctx = self._active_replays.get(replay_id)
        if ctx:
            ctx.stop()
            return True
        return False

    async def list_checkpoints(self, dataset: str) -> list[dict[str, Any]]:
        """List available checkpoints for a dataset."""
        return await self._checkpoint.list_checkpoints(dataset)

    @property
    def state(self) -> ReplayState:
        return self._state

    @property
    def active_replays(self) -> dict[str, dict[str, Any]]:
        return {
            rid: ctx.summary()
            for rid, ctx in self._active_replays.items()
        }
