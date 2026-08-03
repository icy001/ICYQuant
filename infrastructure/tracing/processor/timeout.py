"""Timeout control for export operations."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional


class TimeoutController:
    """
    Export timeout controller.

    Provides configurable timeout for
    export operations with cancellation,
    retry, and fallback support.

    Usage:
        controller = TimeoutController(timeout=30.0)
        result = await controller.execute(export_fn, spans)
    """

    def __init__(
        self,
        timeout: float = 30.0,
        on_timeout: Optional[Callable] = None,
    ) -> None:
        self._timeout = timeout
        self._on_timeout = on_timeout
        self._timeout_count: int = 0
        self._success_count: int = 0

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

    async def execute(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Execute a function with timeout.

        Args:
            fn: Async function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            True on success, False on timeout.
        """

        try:
            result = await asyncio.wait_for(
                fn(*args, **kwargs),
                timeout=self._timeout,
            )
            self._success_count += 1
            return result
        except asyncio.TimeoutError:
            self._timeout_count += 1
            if self._on_timeout:
                try:
                    await self._on_timeout(*args, **kwargs)
                except Exception:
                    pass
            return False

    def get_stats(self) -> dict:
        return {
            "timeout": self._timeout,
            "timeout_count": self._timeout_count,
            "success_count": self._success_count,
        }
