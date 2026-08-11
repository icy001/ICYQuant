"""Tool Context — execution context for tool invocations.

Pipeline:
    AgentContext -> ToolContext (scoped, immutable snapshot)
        -> Tool Execution
        -> Result + Observation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── ToolContext ──

@dataclass
class ToolContext:
    """Execution context passed to every tool invocation.

    Provides tools with the information they need: agent identity,
    session, permissions, tracing, and caller intent. Immutable by
    design — tools receive a frozen snapshot of the current context.

    Supports:
        - Agent identity and session tracking
        - Permission scope
        - Trace propagation
        - Call chain tracking
        - Execution limits

    Usage:
        ctx = ToolContext(
            agent_id="agent-001",
            session_id="session-abc",
            granted_permissions={"research.execute"},
        )
    """

    # ── Identity ──
    agent_id: str = ""
    agent_role: str = ""
    session_id: str = ""
    user_id: str = ""

    # ── Execution ──
    execution_id: str = field(default_factory=lambda: uuid4().hex)
    parent_execution_id: Optional[str] = None
    call_depth: int = 0
    max_call_depth: int = 10

    # ── Permissions ──
    granted_permissions: set = field(default_factory=set)
    permission_scope: str = ""

    # ── Tracing ──
    trace_id: str = ""
    span_id: str = ""

    # ── Intent ──
    intent: str = ""
    plan_id: Optional[str] = None
    step_id: Optional[str] = None

    # ── Limits ──
    timeout_seconds: float = 30.0
    max_retries: int = 3
    rate_limit_key: str = ""

    # ── Metadata ──
    labels: Dict[str, str] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Properties ──

    @property
    def can_execute(self, permission: str) -> bool:
        """Check if the context grants a specific permission.

        Args:
            permission: The permission to check.

        Returns:
            True if the permission is granted.
        """
        if not self.granted_permissions:
            return False
        return permission in self.granted_permissions

    @property
    def is_nested_call(self) -> bool:
        """Whether this is a nested (tool-within-tool) call."""
        return self.parent_execution_id is not None

    @property
    def exceeded_max_depth(self) -> bool:
        """Whether the call depth has exceeded the maximum."""
        return self.call_depth >= self.max_call_depth

    # ── Child Context ──

    def create_child(self, tool_name: str = "") -> "ToolContext":
        """Create a child context for nested tool calls.

        Args:
            tool_name: The child tool name for labeling.

        Returns:
            A new ToolContext with incremented depth.
        """
        return ToolContext(
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            session_id=self.session_id,
            user_id=self.user_id,
            parent_execution_id=self.execution_id,
            call_depth=self.call_depth + 1,
            max_call_depth=self.max_call_depth,
            granted_permissions=self.granted_permissions.copy(),
            permission_scope=self.permission_scope,
            trace_id=self.trace_id,
            intent=self.intent,
            plan_id=self.plan_id,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            labels={**self.labels, "parent_tool": tool_name} if tool_name else dict(self.labels),
        )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "call_depth": self.call_depth,
            "granted_permissions": list(self.granted_permissions),
            "permission_scope": self.permission_scope,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "intent": self.intent,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
        }

    def __hash__(self) -> int:
        return hash(self.execution_id)
