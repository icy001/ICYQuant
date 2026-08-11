"""
Agent execution context management.

Provides immutable context snapshot, mutable execution context,
and context propagation across agent operations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Context Status ──


class ContextStatus(str, Enum):
    """Execution context lifecycle status."""

    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# ── Agent Context ──


@dataclass
class AgentContext:
    """Immutable snapshot of agent execution context.

    Captures the full state at a point in time for traceability and recovery.
    """

    context_id: str
    session_id: str
    agent_id: str
    status: ContextStatus = ContextStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_context_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    ttl_seconds: Optional[int] = None

    # Runtime state (snapshot)
    state: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if context has exceeded TTL."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get context age in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def to_summary(self) -> Dict[str, Any]:
        """Generate context summary for logging and debugging."""
        return {
            "context_id": self.context_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "age_seconds": self.age_seconds,
            "parent_context_id": self.parent_context_id,
            "metadata_keys": list(self.metadata.keys()),
            "state_keys": list(self.state.keys()),
        }


# ── Execution Context ──


@dataclass
class ExecutionContext:
    """Mutable execution context for active agent operations.

    Carries planning state, reasoning chains, and intermediate results.
    """

    context_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    agent_id: str = ""
    plan: Optional[Any] = None  # Plan reference
    current_step: Optional[Any] = None  # Current execution step
    reasoning_chain: List[Dict[str, Any]] = field(default_factory=list)
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[float] = None
    status: ContextStatus = ContextStatus.CREATED

    # ── State Management ──

    def mark_active(self) -> None:
        """Transition context to active state."""
        self.status = ContextStatus.ACTIVE
        self.started_at = time.monotonic()

    def mark_completed(self) -> None:
        """Transition context to completed state."""
        self.status = ContextStatus.COMPLETED

    def mark_failed(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Transition context to failed state with error info."""
        self.status = ContextStatus.FAILED
        self.errors.append({
            "error": error,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Variable Management ──

    def set_variable(self, key: str, value: Any) -> None:
        """Set a context variable."""
        self.variables[key] = value
        logger.debug(f"Context [{self.context_id}]: variable set: {key}")

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self.variables.get(key, default)

    def remove_variable(self, key: str) -> None:
        """Remove a context variable."""
        self.variables.pop(key, None)

    # ── Reasoning Chain ──

    def add_reasoning_step(self, step: Dict[str, Any]) -> None:
        """Append a step to the reasoning chain."""
        self.reasoning_chain.append(step)

    def get_reasoning_chain(self) -> List[Dict[str, Any]]:
        """Get the full reasoning chain."""
        return list(self.reasoning_chain)

    # ── History ──

    def record_action(self, action: str, result: Any) -> None:
        """Record an executed action and its result."""
        self.execution_history.append({
            "action": action,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Snapshot ──

    def to_snapshot(self) -> AgentContext:
        """Create an immutable snapshot of current execution context."""
        return AgentContext(
            context_id=self.context_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            status=self.status,
            state={
                "current_step": str(self.current_step) if self.current_step else None,
                "reasoning_chain": list(self.reasoning_chain),
                "workflow_state": dict(self.workflow_state),
                "variables": dict(self.variables),
                "errors": list(self.errors),
            },
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get execution context summary."""
        elapsed = 0.0
        if self.started_at:
            elapsed = time.monotonic() - self.started_at
        return {
            "context_id": self.context_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "elapsed_seconds": elapsed,
            "reasoning_steps": len(self.reasoning_chain),
            "execution_steps": len(self.execution_history),
            "error_count": len(self.errors),
            "variable_count": len(self.variables),
        }
