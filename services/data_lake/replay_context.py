"""
Replay Context — runtime state management for active replay sessions
including clock simulation, position tracking, and pause/resume.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayMarketData:
    """Wrapper for market data events during replay."""
    event: Any
    replay_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    original_timestamp: Optional[datetime] = None
    sequence_number: int = 0


class ReplayClock:
    """
    Simulated clock for replay sessions.

    Controls the pacing of replay events based on the configured
    speed multiplier. Supports wall-clock synchronization for
    realistic time-based replay.
    """

    def __init__(self, start_time: datetime, speed: float = 1.0) -> None:
        self.start_time = start_time
        self.speed = speed
        self._wall_clock_start = asyncio.get_event_loop().time()
        self._last_event_time: Optional[datetime] = None

    async def wait_until(self, target_time: datetime) -> None:
        """
        Wait until the simulated clock reaches target_time.

        Adjusts wait based on speed multiplier.
        """
        if self._last_event_time is None:
            self._last_event_time = target_time
            return

        delta = (target_time - self._last_event_time).total_seconds()
        self._last_event_time = target_time

        if delta > 0 and self.speed > 0:
            wait_seconds = delta / self.speed
            if wait_seconds > 0:
                await asyncio.sleep(min(wait_seconds, 60.0))  # Cap at 60s

    @property
    def elapsed_wall_seconds(self) -> float:
        return asyncio.get_event_loop().time() - self._wall_clock_start

    @property
    def elapsed_simulated_seconds(self) -> float:
        return self.elapsed_wall_seconds * self.speed


class ReplayContext:
    """
    Runtime context for an active replay session.

    Tracks position, speed, pause/resume state, checkpoints,
    and provides progress reporting.
    """

    def __init__(
        self,
        dataset: str,
        start: datetime,
        end: datetime,
        speed: float = 1.0,
        checkpoint_id: Optional[str] = None,
    ) -> None:
        self.replay_id = f"replay-{uuid.uuid4().hex[:12]}"
        self.dataset = dataset
        self.start = start
        self.end = end
        self.speed = speed
        self.checkpoint_id = checkpoint_id

        self.current_position: int = 0
        self.total_events: int = 0
        self._paused = False
        self._stopped = False
        self._completed = False
        self._error: Optional[str] = None

        self.started_at = datetime.now(timezone.utc)
        self.last_event_at: Optional[datetime] = None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def is_completed(self) -> bool:
        return self._completed

    @property
    def progress_pct(self) -> float:
        if self.total_events == 0:
            return 0.0
        return (self.current_position / self.total_events) * 100

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True

    def mark_completed(self) -> None:
        self._completed = True

    def mark_error(self, error: str = "") -> None:
        self._error = error or "Unknown error"

    def summary(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "dataset": self.dataset,
            "position": f"{self.current_position}/{self.total_events}",
            "progress_pct": round(self.progress_pct, 2),
            "speed": self.speed,
            "paused": self._paused,
            "completed": self._completed,
            "started_at": self.started_at.isoformat(),
        }
