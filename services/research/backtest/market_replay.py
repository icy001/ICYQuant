"""Market Replay — historical market data replay engine.

Replays tick, bar, and daily data with configurable speed, pause/resume,
and time-jump capabilities for event-driven backtesting.

Modes::

    Tick → 1m → 5m → 15m → 1h → Daily

Features:
* Speed multiplier (1x, 10x, 100x, max)
* Single-step debugging
* Time jumping (skip to specific date)
* Pausable/resumable replay
* Bar-by-bar iteration
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from .backtest_context import BacktestContext

logger = logging.getLogger(__name__)


class ReplayMode(str, Enum):
    """Market replay frequency modes."""

    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR = "1h"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ReplayState:
    """Current replay state."""

    current_date: Optional[str] = None
    current_bar: Optional[Dict[str, Any]] = None
    position: int = 0
    total_bars: int = 0
    speed: float = 1.0
    paused: bool = False
    complete: bool = False
    started_at: Optional[float] = None


class MarketReplay:
    """Historical market data replay engine.

    Provides async iteration over historical data with:
    * Multi-frequency support (tick through weekly)
    * Speed control for fast-forward
    * Single-step debugging
    * Time-range filtering
    * Pause/resume capability
    """

    def __init__(
        self,
        mode: ReplayMode = ReplayMode.DAILY,
        speed: float = 1.0,
        warm_up_bars: int = 0,
    ) -> None:
        self._mode = mode
        self._speed = speed
        self._warm_up_bars = warm_up_bars
        self._data: List[Dict[str, Any]] = []
        self._state = ReplayState()
        self._ctx: Optional[BacktestContext] = None

    # ── initialization ─────────────────────────────────────────────────────

    async def initialize(self, ctx: Optional[BacktestContext] = None) -> None:
        """Initialize the replay engine with context and data.

        Args:
            ctx: Backtest context with frequency, start/end dates.
        """
        self._ctx = ctx
        if ctx:
            self._mode = ReplayMode(ctx.frequency)

        self._state = ReplayState(
            speed=self._speed,
            started_at=time.monotonic(),
        )
        logger.info("Market Replay initialized (mode=%s, speed=%.1fx)", self._mode.value, self._speed)

    async def load_data(self, data: List[Dict[str, Any]]) -> None:
        """Load historical market data for replay.

        Each bar should contain:
        * timestamp (str) — ISO 8601 datetime
        * symbol (str) — ticker symbol
        * open, high, low, close, volume (float)
        * vwap (float, optional)
        """
        # Sort by timestamp
        self._data = sorted(data, key=lambda b: b.get("timestamp", ""))
        self._state.total_bars = len(self._data)
        self._state.position = 0
        logger.info("Loaded %d bars for market replay", len(self._data))

    # ── replay loop ────────────────────────────────────────────────────────

    async def replay(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator yielding replay events one at a time.

        Yields:
            Dict with:
            * timestamp — current bar timestamp
            * data — bar OHLCV data
            * metadata — replay state info
            * position — bar index

        Usage::

            async for event in replay.replay():
                engine.process(event)
        """
        if not self._data:
            logger.warning("No data loaded for replay")
            return

        self._state.paused = False
        self._state.complete = False

        for i in range(self._state.position, len(self._data)):
            bar = self._data[i]
            self._state.position = i
            self._state.current_bar = bar
            self._state.current_date = bar.get("timestamp", "")

            # Check for pause
            while self._state.paused:
                await asyncio.sleep(0.1)

            # Warm-up: skip first N bars without yielding
            if i < self._warm_up_bars:
                continue

            event = {
                "timestamp": bar.get("timestamp", ""),
                "data": bar,
                "metadata": {
                    "position": i,
                    "total": len(self._data),
                    "progress": i / max(len(self._data) - 1, 1),
                    "mode": self._mode.value,
                    "speed": self._state.speed,
                },
            }
            yield event

            # Apply speed control (1x speed = no artificial delay)
            if self._speed != float("inf"):
                await self._simulate_delay()

        self._state.complete = True
        logger.info("Market replay complete (%d bars)", len(self._data))

    async def replay_range(
        self, start: int, end: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Replay a specific range of bars.

        Args:
            start: Start bar index.
            end: End bar index (exclusive). None = to end.
        """
        end = end or len(self._data)
        self._state.position = start

        for i in range(start, min(end, len(self._data))):
            bar = self._data[i]
            self._state.position = i
            self._state.current_bar = bar

            event = {
                "timestamp": bar.get("timestamp", ""),
                "data": bar,
                "metadata": {
                    "position": i,
                    "total": len(self._data),
                    "progress": (i - start) / max(end - start - 1, 1),
                },
            }
            yield event

            if self._speed != float("inf"):
                await self._simulate_delay()

    # ── control ────────────────────────────────────────────────────────────

    def pause(self) -> None:
        """Pause the replay."""
        self._state.paused = True
        logger.info("Market replay paused")

    def resume(self) -> None:
        """Resume the replay."""
        self._state.paused = False
        logger.info("Market replay resumed")

    def set_speed(self, speed: float) -> None:
        """Set replay speed multiplier.

        Args:
            speed: Speed multiplier (1.0 = real-time, 100.0 = 100x, float('inf') = max speed).
        """
        self._state.speed = speed
        logger.info("Market replay speed set to %.1fx", speed)

    async def jump_to(self, bar_index: int) -> None:
        """Jump to a specific bar index."""
        if 0 <= bar_index < len(self._data):
            self._state.position = bar_index
            self._state.current_bar = self._data[bar_index]
            self._state.current_date = self._state.current_bar.get("timestamp", "")
            logger.info("Jumped to bar %d (%s)", bar_index, self._state.current_date)
        else:
            raise IndexError(f"Bar index {bar_index} out of range [0, {len(self._data) - 1}]")

    async def jump_to_date(self, date_str: str) -> None:
        """Jump to the first bar on or after a specific date.

        Args:
            date_str: ISO date string (e.g., '2024-01-15').
        """
        for i, bar in enumerate(self._data):
            ts = bar.get("timestamp", "")
            if ts >= date_str:
                await self.jump_to(i)
                return
        logger.warning("No bar found on or after %s", date_str)

    async def reset(self) -> None:
        """Reset the replay to the beginning."""
        self._state.position = 0
        self._state.paused = False
        self._state.complete = False
        logger.info("Market replay reset")

    # ── query ──────────────────────────────────────────────────────────────

    def get_state(self) -> ReplayState:
        """Get current replay state."""
        return self._state

    def get_current_bar(self) -> Optional[Dict[str, Any]]:
        """Get the current bar data."""
        return self._state.current_bar

    def get_progress(self) -> float:
        """Get replay progress (0.0 to 1.0)."""
        if self._state.total_bars == 0:
            return 0.0
        return self._state.position / max(self._state.total_bars - 1, 1)

    def get_stats(self) -> Dict[str, Any]:
        """Return replay statistics."""
        elapsed = time.monotonic() - self._state.started_at if self._state.started_at else 0
        bars_per_sec = self._state.position / elapsed if elapsed > 0 else 0

        return {
            "mode": self._mode.value,
            "speed": self._state.speed,
            "position": self._state.position,
            "total_bars": self._state.total_bars,
            "progress": self.get_progress(),
            "paused": self._state.paused,
            "complete": self._state.complete,
            "elapsed_seconds": elapsed,
            "bars_per_second": bars_per_sec,
            "eta_seconds": (self._state.total_bars - self._state.position) / bars_per_sec if bars_per_sec > 0 else 0,
        }

    # ── internals ──────────────────────────────────────────────────────────

    async def _simulate_delay(self) -> None:
        """Simulate real-time delay based on speed multiplier."""
        if self._speed <= 0:
            return
        # For 1x daily mode, a reasonable delay is arbitrary (e.g., 1ms per bar)
        # In a real system, this would match the original time gaps
        delay = 0.001 / self._speed  # 1ms at 1x, 0.01ms at 100x
        await asyncio.sleep(delay)
