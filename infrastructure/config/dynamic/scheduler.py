"""
Configuration reload scheduler.

Periodically triggers configuration reload at
configured intervals, supporting:
- Fixed interval scheduling
- Cron-like expressions
- Manual trigger
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional


class ReloadScheduler:
    """
    Scheduled configuration reload.

    Supports periodic reload execution with
    configurable intervals and lifecycle
    management.

    Usage:
        scheduler = ReloadScheduler(
            reload_func=my_reload,
            interval=30.0,  # seconds
        )
        scheduler.start()
        # ... later
        scheduler.stop()
    """

    def __init__(
        self,
        reload_func: Callable,
        interval: float = 30.0,
        immediate: bool = False,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize reload scheduler.

        Args:
            reload_func: Function to call on each reload.
            interval: Reload interval in seconds.
            immediate: If True, run immediately on start.
            loop: Event loop for async scheduling.
        """
        self._reload_func = reload_func
        self._interval = interval
        self._immediate = immediate
        self._loop = loop

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._next_run: Optional[datetime] = None
        self._run_count = 0
        self._error_count = 0
        self._last_run_duration = 0.0
        self._lock = threading.Lock()

    @property
    def interval(
        self,
    ) -> float:
        """Get current interval."""
        return self._interval

    @interval.setter
    def interval(
        self,
        value: float,
    ) -> None:
        """Set reload interval."""
        self._interval = max(1.0, value)

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def next_run(
        self,
    ) -> Optional[datetime]:
        """Get next scheduled run time."""
        return self._next_run

    @property
    def stats(
        self,
    ) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "running": self._running,
            "interval": self._interval,
            "run_count": self._run_count,
            "error_count": self._error_count,
            "last_duration": self._last_run_duration,
            "next_run": self._next_run.isoformat() if self._next_run else None,
        }

    def start(
        self,
    ) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._loop = self._loop or asyncio.get_event_loop()
        self._running = True

        if self._immediate:
            self._task = self._loop.create_task(self._run_immediate())
        else:
            self._task = self._loop.create_task(self._scheduler_loop())

    def stop(
        self,
        timeout: float = 5.0,
    ) -> None:
        """
        Stop the scheduler gracefully.

        Args:
            timeout: Maximum wait time in seconds.
        """
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                if self._loop:
                    self._loop.run_until_complete(
                        asyncio.wait_for(self._task, timeout=timeout)
                    )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    async def _scheduler_loop(
        self,
    ) -> None:
        """Main scheduler loop."""
        while self._running:
            self._next_run = datetime.utcnow()
            await self._execute_reload()
            await asyncio.sleep(self._interval)

    async def _run_immediate(
        self,
    ) -> None:
        """Run immediately, then start loop."""
        await self._execute_reload()
        if self._running:
            self._task = self._loop.create_task(self._scheduler_loop())

    async def _execute_reload(
        self,
    ) -> None:
        """Execute a reload cycle."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(self._reload_func):
                await self._reload_func()
            else:
                loop = self._loop or asyncio.get_event_loop()
                await loop.run_in_executor(None, self._reload_func)

            self._run_count += 1
        except Exception:
            self._error_count += 1
        finally:
            self._last_run_duration = time.time() - start

    def trigger(
        self,
    ) -> None:
        """Manually trigger a reload."""
        if self._loop:
            self._loop.create_task(self._execute_reload())

    def reset_stats(
        self,
    ) -> None:
        """Reset statistics."""
        self._run_count = 0
        self._error_count = 0
        self._last_run_duration = 0.0
