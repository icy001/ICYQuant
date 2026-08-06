"""
Dispatcher — distributes node execution tasks to workers based on load and affinity.

Selects the optimal worker for each node considering:
- Worker load (CPU, memory, queue depth)
- Node affinity hints
- Priority of the task
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.workflow.models.node import Node

logger = logging.getLogger(__name__)


class DispatchStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"
    AFFINITY = "affinity"


@dataclass
class DispatchResult:
    """Result of a node dispatch and execution."""

    success: bool
    node_id: str
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Dispatcher:
    """
    Dispatches node execution to workers.

    Acts as an abstraction layer between the scheduler and the worker pool.
    In the current implementation, executes nodes directly (single-process),
    but the interface is designed for future distributed worker pools.
    """

    def __init__(self, strategy: DispatchStrategy = DispatchStrategy.LEAST_LOADED):
        self.strategy = strategy
        self._node_handlers: Dict[str, Any] = {}
        self._dispatch_count: int = 0
        self._lock = asyncio.Lock()

    def register_handler(self, node_type: str, handler: Any) -> None:
        """Register a handler function for a specific node type."""
        self._node_handlers[node_type] = handler

    async def dispatch(self, node: Node) -> DispatchResult:
        """
        Dispatch a node for execution.

        In a distributed setup, this would select a worker and send the task.
        Currently executes locally via registered handlers.
        """
        import time

        start = time.monotonic()

        async with self._lock:
            self._dispatch_count += 1
            dispatch_id = self._dispatch_count

        try:
            # Resolve handler
            handler = self._node_handlers.get(node.node_type)
            if handler is None:
                # Default: execute node's own handler
                if hasattr(node, "execute") and callable(node.execute):
                    result = node.execute()
                    if asyncio.iscoroutine(result):
                        result = await result
                else:
                    raise ValueError(f"No handler registered for node type: {node.node_type}")
            else:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(node)
                else:
                    result = handler(node)

            duration = (time.monotonic() - start) * 1000
            return DispatchResult(
                success=True,
                node_id=node.node_id,
                output=result,
                duration_ms=duration,
                metadata={"dispatch_id": dispatch_id},
            )

        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            logger.error(f"Node {node.node_id} execution failed: {e}")
            return DispatchResult(
                success=False,
                node_id=node.node_id,
                error=str(e),
                duration_ms=duration,
                metadata={"dispatch_id": dispatch_id},
            )

    def select_worker(self, candidates: List[str]) -> Optional[str]:
        """Select a worker based on the configured strategy."""
        if not candidates:
            return None

        if self.strategy == DispatchStrategy.ROUND_ROBIN:
            idx = self._dispatch_count % len(candidates)
            return candidates[idx]
        elif self.strategy == DispatchStrategy.RANDOM:
            return random.choice(candidates)
        elif self.strategy == DispatchStrategy.LEAST_LOADED:
            # Placeholder: in a real system, query worker loads
            return candidates[0]
        else:
            return candidates[0]
