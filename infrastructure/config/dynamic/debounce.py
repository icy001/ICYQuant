"""
Debounce utility.

Implements debounce logic for configuration change
events, preventing excessive reloads when multiple
files change in quick succession.

Supports:
- Timed debounce (wait for quiet period)
- Leading/trailing edge control
- Async debounce for coroutine functions
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable, Optional


class Debounce:
    """
    Thread-safe debounce utility.

    Delays execution of a function until after a
    specified wait time has elapsed since the last
    call. This prevents rapid-fire reloads from
    multiple simultaneous file changes.

    Usage:
        debouncer = Debounce(wait_time=0.5)

        def on_change():
            print("Reloading...")

        debounced = debouncer.debounce(on_change)

        # Multiple rapid calls only trigger once
        debounced()
        debounced()
        debounced()
        # 0.5s later, on_change is called once
    """

    def __init__(
        self,
        wait_time: float = 0.5,
        immediate: bool = False,
    ) -> None:
        """
        Initialize debounce.

        Args:
            wait_time: Seconds to wait after last call.
            immediate: If True, trigger on leading edge
                       (first call) instead of trailing.
        """
        self._wait_time = wait_time
        self._immediate = immediate
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def debounce(
        self,
        func: Callable,
    ) -> Callable:
        """
        Wrap a function with debounce logic.

        Args:
            func: Function to debounce.

        Returns:
            Debounced wrapper.
        """
        timer = self._timer

        def debounced(*args: Any, **kwargs: Any) -> None:
            nonlocal timer

            def call_it():
                self._timer = None
                func(*args, **kwargs)

            with self._lock:
                if self._timer is not None:
                    self._timer.cancel()

                if self._immediate:
                    if self._timer is None:
                        self._timer = threading.Timer(
                            0, call_it
                        )
                        self._timer.start()
                else:
                    self._timer = threading.Timer(
                        self._wait_time, call_it
                    )
                    self._timer.start()

        return debounced

    def cancel(
        self,
    ) -> None:
        """Cancel any pending debounced call."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def flush(
        self,
    ) -> None:
        """Immediately execute any pending debounced call."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class AsyncDebounce:
    """
    Async debounce utility.

    Same logic as Debounce but for async functions
    running in an event loop.

    Usage:
        debouncer = AsyncDebounce(wait_time=0.5)

        async def on_change():
            await reload_config()

        debounced = debouncer.debounce(on_change)
        await debounced()
    """

    def __init__(
        self,
        wait_time: float = 0.5,
        immediate: bool = False,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize async debounce.

        Args:
            wait_time: Seconds to wait after last call.
            immediate: Trigger on leading edge.
            loop: Event loop to use.
        """
        self._wait_time = wait_time
        self._immediate = immediate
        self._loop = loop
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._last_call: float = 0

    def debounce(
        self,
        func: Callable,
    ) -> Callable:
        """
        Wrap an async function with debounce logic.

        Args:
            func: Async function to debounce.

        Returns:
            Debounced async wrapper.
        """
        async def debounced(*args: Any, **kwargs: Any) -> None:
            loop = self._loop or asyncio.get_event_loop()
            now = time.time()

            async def execute():
                await asyncio.sleep(self._wait_time)
                func(*args, **kwargs)

            async def immediate_execute():
                func(*args, **kwargs)

            async with self._lock:
                if self._task is not None and not self._task.done():
                    self._task.cancel()

                if self._immediate:
                    if self._task is None:
                        self._task = loop.create_task(immediate_execute())
                else:
                    self._task = loop.create_task(execute())

        return debounced

    async def cancel(
        self,
    ) -> None:
        """Cancel any pending debounced call."""
        async with self._lock:
            if self._task is not None and not self._task.done():
                self._task.cancel()
                self._task = None

    async def flush(
        self,
    ) -> None:
        """Immediately execute any pending debounced call."""
        async with self._lock:
            if self._task is not None and not self._task.done():
                self._task.cancel()
                self._task = None
