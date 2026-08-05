"""Hedge request management for ICYQuant Service Mesh.

Provides ``HedgeManager`` for sending secondary requests after
a timeout threshold, with the fastest response winning.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HedgeManager:
    """Manages hedge request strategies."""

    def __init__(
        self,
        hedge_delay_ms: int = 50,
        max_hedges: int = 2,
    ) -> None:
        self._hedge_delay_ms = hedge_delay_ms
        self._max_hedges = max_hedges
        self._lock = threading.RLock()
        self._hedge_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._primary_win_count = 0
        self._hedge_win_count = 0

    async def execute_with_hedging(
        self,
        primary_fn: Callable,
        hedge_fns: Optional[List[Callable]] = None,
        timeout_s: float = 5.0,
    ) -> Dict[str, Any]:
        """Execute with hedging: primary + delayed hedges."""
        with self._lock:
            self._hedge_count += 1

        hedge_fns = hedge_fns or []
        hedge_delay = self._hedge_delay_ms / 1000.0

        primary_task = asyncio.create_task(
            self._run_with_timeout(primary_fn, timeout_s)
        )
        tasks = [("primary", primary_task)]

        for i, fn in enumerate(hedge_fns[: self._max_hedges]):
            await asyncio.sleep(hedge_delay)
            task = asyncio.create_task(
                self._run_with_timeout(fn, timeout_s)
            )
            tasks.append((f"hedge_{i}", task))

        winner = None
        winner_name = ""
        start = time.monotonic()

        for name, task in tasks:
            try:
                result = await asyncio.wait_for(
                    task, timeout=timeout_s
                )
                if result is not None and result.get(
                    "status", 0
                ) < 500:
                    winner = result
                    winner_name = name
                    break
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        duration = time.monotonic() - start

        # Cancel remaining tasks
        for name, task in tasks:
            if not task.done():
                task.cancel()

        with self._lock:
            if winner:
                self._success_count += 1
                if winner_name == "primary":
                    self._primary_win_count += 1
                else:
                    self._hedge_win_count += 1
            else:
                self._failure_count += 1

        return {
            "success": winner is not None,
            "result": winner,
            "winner": winner_name,
            "duration_s": duration,
            "hedges_used": len(tasks) - 1,
        }

    async def _run_with_timeout(
        self, fn: Callable, timeout_s: float
    ) -> Any:
        try:
            result = await asyncio.wait_for(
                fn(), timeout=timeout_s
            )
            return result
        except asyncio.TimeoutError:
            return {"status": 504, "error": "timeout"}
        except Exception as exc:
            return {"status": 500, "error": str(exc)}

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = (
                self._success_count + self._failure_count
            )
            return {
                "hedge_count": self._hedge_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "primary_win_count": self._primary_win_count,
                "hedge_win_count": self._hedge_win_count,
                "success_rate": (
                    self._success_count / total
                    if total > 0
                    else 0.0
                ),
                "hedge_win_rate": (
                    self._hedge_win_count / total
                    if total > 0
                    else 0.0
                ),
            }
