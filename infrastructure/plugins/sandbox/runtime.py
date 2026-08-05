"""Sandbox runtime state management.

Provides the :class:`SandboxRuntime` dataclass that captures the
full lifecycle state of an isolated plugin execution environment,
including process/thread identifiers, resource limits, and
security configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SandboxRuntime:
    """Runtime state descriptor for a sandboxed plugin execution.

    Tracks the full lifecycle of a sandbox from creation through
    destruction, including resource limits, isolation metadata,
    and the security policy applied to the plugin.

    Attributes:
        plugin_id: Unique identifier for the plugin.
        status: Current lifecycle status (created/running/stopped/destroyed).
        created_at: Timestamp when the sandbox was created.
        started_at: Timestamp when the sandbox was started, if running.
        pid: Process ID when using process isolation.
        thread_id: Thread ID when using thread isolation.
        memory_limit: Maximum memory allowed in bytes.
        cpu_limit: Maximum CPU usage allowed as a percentage (0-100).
        filesystem_root: Root path for filesystem access within the sandbox.
        allowed_network_hosts: List of host patterns the plugin may access.
        allowed_permissions: List of permission strings granted to the plugin.
        allowed_capabilities: List of capability strings granted to the plugin.
    """

    plugin_id: str
    status: str = "created"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    pid: Optional[int] = None
    thread_id: Optional[int] = None
    memory_limit: int = 256 * 1024 * 1024
    cpu_limit: float = 50.0
    filesystem_root: str = ""
    allowed_network_hosts: List[str] = field(default_factory=list)
    allowed_permissions: List[str] = field(default_factory=list)
    allowed_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the runtime state to a dictionary.

        Returns:
            A dictionary representation of the runtime state with
            datetime fields serialized as ISO 8601 strings.
        """
        return {
            "plugin_id": self.plugin_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "pid": self.pid,
            "thread_id": self.thread_id,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "filesystem_root": self.filesystem_root,
            "allowed_network_hosts": list(self.allowed_network_hosts),
            "allowed_permissions": list(self.allowed_permissions),
            "allowed_capabilities": list(self.allowed_capabilities),
        }

    def is_active(self) -> bool:
        """Check whether the sandbox is currently active.

        Returns:
            True if the sandbox status is 'created' or 'running',
            False otherwise.
        """
        return self.status in ("created", "running")

    async def start(self) -> None:
        """Transition the sandbox to the running state.

        Sets ``status`` to ``'running'`` and records the
        ``started_at`` timestamp.
        """
        self.status = "running"
        self.started_at = datetime.now()

    async def stop(self) -> None:
        """Transition the sandbox to the stopped state.

        Sets ``status`` to ``'stopped'``.
        """
        self.status = "stopped"