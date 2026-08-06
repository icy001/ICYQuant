"""
Parallel Executor — executes multiple nodes concurrently using a worker pool.

Supports:
- Fork-Join pattern (fan-out, fan-in)
- AsyncIO-based concurrency
- Multi-threaded execution (reserved)
- Distributed execution (reserved)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from services.workflow.dag.worker_pool import WorkerPool, WorkerConfig
from services.workflow.models.node import Node

logger = logging.getLogger(__name__)


@dataclass
class ParallelResult:
    """Result of a parallel execution batch."""

    success: bool
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    completed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


class ParallelExecutor:
    """
    Executes nodes in parallel using a worker pool.

    Implements the Fork-Join pattern:
    1. Fork: submit all nodes to the worker pool
    2. Join: wait for all to complete, collect results
    """

    def __init__(
        self,
        worker_pool: Optional[WorkerPool] = None,
        max_concurrency: int = 10,
    ):
        self.worker_pool = worker_pool or WorkerPool(
            WorkerConfig(max_workers=max_concurrency)
        )
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_parallel(
        self,
        nodes: List[Node],
        executor_fn: Optional[Callable[[Node], Coroutine]] = None,
    ) -> ParallelResult:
        """
        Execute a batch of nodes in parallel.

        Args:
            nodes: Nodes to execute.
            executor_fn: Async function that executes a single node.

        Returns:
            ParallelResult with per-node results and errors.
        """
        if not nodes:
            return ParallelResult(success=True)

        async def _execute_with_semaphore(node: Node) -> tuple:
            async with self._semaphore:
                try:
                    if executor_fn:
                        result = await executor_fn(node)
                    elif hasattr(node, "execute") and callable(node.execute):
                        result = node.execute()
                        if asyncio.iscoroutine(result):
                            result = await result
                    else:
                        result = None
                    return (node.node_id, True, result, None)
                except Exception as e:
                    return (node.node_id, False, None, str(e))

        tasks = [_execute_with_semaphore(node) for node in nodes]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        result = ParallelResult(success=True)
        for item in results_list:
            if isinstance(item, Exception):
                result.success = False
                continue
            node_id, ok, output, error = item
            if ok:
                result.results[node_id] = output
                result.completed.append(node_id)
            else:
                result.success = False
                result.errors[node_id] = error or "Unknown error"
                result.failed.append(node_id)

        return result

    async def execute_staged(
        self,
        stages: List[List[Node]],
        executor_fn: Optional[Callable[[Node], Coroutine]] = None,
    ) -> List[ParallelResult]:
        """
        Execute nodes in stages (sequential across stages, parallel within).

        Args:
            stages: List of stages, each containing nodes to execute in parallel.
            executor_fn: Async function that executes a single node.

        Returns:
            List of ParallelResult, one per stage.
        """
        stage_results = []
        for stage_nodes in stages:
            result = await self.execute_parallel(stage_nodes, executor_fn)
            stage_results.append(result)
            if not result.success:
                # Stop on first stage failure
                break
        return stage_results

    async def shutdown(self) -> None:
        """Shutdown the worker pool."""
        await self.worker_pool.shutdown()
