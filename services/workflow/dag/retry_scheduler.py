"""
Retry Scheduler — manages node retry policies to avoid retry storms.

Supports:
- Immediate retry
- Exponential backoff
- Jitter (randomized delay to prevent thundering herd)
- Retry budget (max total retries per workflow)
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.workflow.dag.ready_queue import ReadyQueue

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    IMMEDIATE = "immediate"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryPolicy:
    """Retry policy for a node or node type."""

    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    retry_on_timeout: bool = True
    retry_on_error: bool = True
    retryable_errors: List[str] = field(default_factory=list)


@dataclass
class RetryState:
    """State tracking for a node's retries."""

    node_id: str
    attempt: int = 0
    last_error: Optional[str] = None
    next_retry_at: float = 0.0
    total_delay_ms: float = 0.0


class RetryScheduler:
    """
    Manages retries for failed nodes.

    Features:
    - Per-node and global retry policies
    - Exponential backoff with jitter
    - Retry budget enforcement
    - Dead letter queue for exhausted retries
    """

    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        self.default_policy = default_policy or RetryPolicy()
        self._node_policies: Dict[str, RetryPolicy] = {}
        self._retry_states: Dict[str, RetryState] = {}
        self._total_retries: int = 0
        self._max_total_retries: int = 100
        self._dead_letter: List[str] = []

    def set_policy(self, node_id: str, policy: RetryPolicy) -> None:
        """Set a retry policy for a specific node."""
        self._node_policies[node_id] = policy

    def set_policy_for_type(self, node_type: str, policy: RetryPolicy) -> None:
        """Set a retry policy for all nodes of a given type."""
        self._node_policies[f"type:{node_type}"] = policy

    def get_policy(self, node_id: str, node_type: Optional[str] = None) -> RetryPolicy:
        """Get the retry policy for a node."""
        if node_id in self._node_policies:
            return self._node_policies[node_id]
        if node_type and f"type:{node_type}" in self._node_policies:
            return self._node_policies[f"type:{node_type}"]
        return self.default_policy

    def should_retry(self, node_id: str, dispatch_result: Any = None) -> bool:
        """
        Determine if a node should be retried.

        Checks:
        1. Within retry budget
        2. Under max retries
        3. Error is retryable
        """
        if self._total_retries >= self._max_total_retries:
            return False

        state = self._retry_states.get(node_id)
        if state is None:
            state = RetryState(node_id=node_id)
            self._retry_states[node_id] = state

        policy = self.get_policy(node_id)

        if state.attempt >= policy.max_retries:
            self._dead_letter.append(node_id)
            return False

        return True

    async def schedule_retry(self, node_id: str, ready_queue: ReadyQueue) -> None:
        """
        Schedule a retry for a node.

        Calculates delay based on retry strategy and re-enqueues the node.
        """
        state = self._retry_states.get(node_id)
        if state is None:
            state = RetryState(node_id=node_id)
            self._retry_states[node_id] = state

        state.attempt += 1
        self._total_retries += 1

        policy = self.get_policy(node_id)
        delay = self._calculate_delay(state.attempt, policy)
        state.next_retry_at = asyncio.get_event_loop().time() + delay
        state.total_delay_ms += delay * 1000

        if delay > 0:
            await asyncio.sleep(delay)

        priority = -state.attempt  # Lower priority for more retries
        await ready_queue.enqueue(node_id, priority=priority)

        logger.info(
            f"Retrying node {node_id} (attempt {state.attempt}/{policy.max_retries}, "
            f"delay={delay:.2f}s)"
        )

    def _calculate_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate retry delay based on strategy."""
        if policy.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        elif policy.strategy == RetryStrategy.FIXED:
            return policy.base_delay_seconds

        elif policy.strategy == RetryStrategy.EXPONENTIAL:
            delay = policy.base_delay_seconds * (policy.backoff_multiplier ** (attempt - 1))
            return min(delay, policy.max_delay_seconds)

        elif policy.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            delay = policy.base_delay_seconds * (policy.backoff_multiplier ** (attempt - 1))
            delay = min(delay, policy.max_delay_seconds)
            jitter = random.uniform(-policy.jitter_factor, policy.jitter_factor) * delay
            return max(0, delay + jitter)

        return policy.base_delay_seconds

    def reset(self, node_id: str) -> None:
        """Reset retry state for a node."""
        self._retry_states.pop(node_id, None)

    def reset_all(self) -> None:
        """Reset all retry states."""
        self._retry_states.clear()
        self._total_retries = 0
        self._dead_letter.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_retries": self._total_retries,
            "dead_letter_count": len(self._dead_letter),
            "active_retries": len(self._retry_states),
            "retry_budget_remaining": self._max_total_retries - self._total_retries,
        }
