"""
Window Manager — unified lifecycle manager for all window types
in the streaming platform with watermark integration.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Re-export WindowResult for convenience
from .tumbling_window import TumblingWindow, WindowResult
from .sliding_window import SlidingWindow
from .session_window import SessionWindow
from .global_window import GlobalWindow, TriggerType


class WindowType(str, Enum):
    TUMBLING = "tumbling"
    SLIDING = "sliding"
    SESSION = "session"
    GLOBAL = "global"


@dataclass
class WindowConfig:
    """Configuration for a managed window."""
    window_id: str
    window_type: WindowType
    size_ms: int = 60000
    slide_ms: int = 10000
    gap_ms: int = 300000
    trigger_type: TriggerType = TriggerType.COUNT
    trigger_value: int = 10000
    aggregator: Optional[Callable[[list[Any]], Any]] = None
    extract_key: Optional[Callable[[Any], str]] = None
    max_late_ms: int = 0


class WindowManager:
    """
    Unified lifecycle manager for all window types.

    Creates and manages tumbling, sliding, session, and global windows
    with integrated watermark-based emission.

    Usage::

        mgr = WindowManager()
        await mgr.create_window("trades_1min", WindowConfig(
            window_id="trades_1min",
            window_type=WindowType.TUMBLING,
            size_ms=60000,
        ))
        mgr.add_event("trades_1min", event_time, trade_event)
        results = mgr.emit_ready_windows(watermark_ms)
    """

    def __init__(self) -> None:
        self._windows: dict[str, Any] = {}
        self._configs: dict[str, WindowConfig] = {}
        self._total_emitted = 0

    async def create_window(self, window_id: str, config: WindowConfig) -> Any:
        """Create a managed window."""
        if config.window_type == WindowType.TUMBLING:
            window = TumblingWindow(
                size_ms=config.size_ms,
                aggregator=config.aggregator,
                max_late_ms=config.max_late_ms,
            )
        elif config.window_type == WindowType.SLIDING:
            window = SlidingWindow(
                size_ms=config.size_ms,
                slide_ms=config.slide_ms,
                aggregator=config.aggregator,
                max_late_ms=config.max_late_ms,
            )
        elif config.window_type == WindowType.SESSION:
            window = SessionWindow(
                gap_ms=config.gap_ms,
                extract_key=config.extract_key,
                aggregator=config.aggregator,
                max_late_ms=config.max_late_ms,
            )
        elif config.window_type == WindowType.GLOBAL:
            window = GlobalWindow(
                trigger_type=config.trigger_type,
                trigger_value=config.trigger_value,
                aggregator=config.aggregator,
            )
        else:
            raise ValueError(f"Unknown window type: {config.window_type}")

        self._windows[window_id] = window
        self._configs[window_id] = config
        logger.info(
            "Window created: %s (%s, size=%dms)", window_id, config.window_type.value, config.size_ms,
        )
        return window

    def add_event(self, window_id: str, event_time_ms: float, event: Any) -> None:
        """Add an event to a managed window."""
        window = self._windows.get(window_id)
        if window is None:
            logger.warning("Window not found: %s", window_id)
            return
        window.add_event(event_time_ms, event)

    def emit_ready_windows(self, watermark_ms: float) -> dict[str, list[WindowResult]]:
        """Emit results from all ready windows."""
        results: dict[str, list[WindowResult]] = {}
        for window_id, window in self._windows.items():
            config = self._configs.get(window_id)

            if isinstance(window, (TumblingWindow, SlidingWindow)):
                ready = window.get_ready_windows(watermark_ms)
            elif isinstance(window, SessionWindow):
                ready = window.get_ready_sessions(watermark_ms)
            elif isinstance(window, GlobalWindow):
                ready = window.check_trigger(watermark_ms)
            else:
                ready = []

            if ready:
                results[window_id] = ready
                self._total_emitted += sum(r.event_count for r in ready)

        return results

    async def delete_window(self, window_id: str) -> bool:
        """Delete a managed window."""
        if window_id in self._windows:
            del self._windows[window_id]
            del self._configs[window_id]
            return True
        return False

    async def list_windows(self) -> list[dict[str, Any]]:
        """List all managed windows."""
        return [
            {
                "window_id": wid,
                "type": self._configs[wid].window_type.value,
                "event_count": getattr(win, "total_events", getattr(win, "event_count", 0)),
            }
            for wid, win in self._windows.items()
        ]

    @property
    def window_count(self) -> int:
        return len(self._windows)

    @property
    def total_emitted(self) -> int:
        return self._total_emitted

    async def summary(self) -> dict[str, Any]:
        """Get window manager summary."""
        return {
            "total_windows": len(self._windows),
            "total_emitted": self._total_emitted,
            "windows": await self.list_windows(),
        }
