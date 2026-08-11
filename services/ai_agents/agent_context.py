"""
ICYQuant Agent Context — execution context for individual agents.

Provides each agent with a scoped execution context including session
info, memory access, tool permissions, and communication channels.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Execution context for a single agent instance."""
    agent_id: str
    session_id: str = ""
    request_id: str = ""
    user_id: str = ""

    # Permissions
    allowed_tools: list[str] = field(default_factory=list)
    allowed_data_sources: list[str] = field(default_factory=list)

    # References
    shared_memory: Any = None
    communication_bus: Any = None

    # State
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def can_use_tool(self, tool_name: str) -> bool:
        return not self.allowed_tools or tool_name in self.allowed_tools

    def can_access_data(self, source: str) -> bool:
        return not self.allowed_data_sources or source in self.allowed_data_sources
