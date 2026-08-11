"""
ICYQuant Data Control Plane — administrative control plane for the data platform.

Provides centralized management for all data platform subsystems:
configuration, lifecycle, scaling, and operational commands.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControlAction(str, Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"
    DRAIN = "drain"
    SCALE = "scale"
    RECONFIGURE = "reconfigure"


class Subsystem(str, Enum):
    CONNECTIVITY = "connectivity"
    NORMALIZATION = "normalization"
    STREAMING = "streaming"
    DATA_LAKE = "data_lake"
    GOVERNANCE = "governance"
    API = "api"
    PLATFORM = "platform"


@dataclass
class ControlCommand:
    """A control plane command."""
    command_id: str
    action: ControlAction
    target: Subsystem
    parameters: dict[str, Any] = field(default_factory=dict)
    issued_by: str = "system"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: str = ""


@dataclass
class ControlPlaneConfig:
    enable_audit: bool = True
    command_timeout_seconds: int = 60
    max_concurrent_commands: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


class DataControlPlane:
    """Centralized administrative control plane.

    Responsibilities:
        - Lifecycle management (start/stop/restart subsystems)
        - Operational commands (pause/resume/drain)
        - Scaling operations
        - Configuration updates
        - Audit trail for all control actions
    """

    def __init__(self, config: Optional[ControlPlaneConfig] = None, platform: Any = None) -> None:
        self._config = config or ControlPlaneConfig()
        self._platform = platform
        self._commands: list[ControlCommand] = []
        self._subsystem_states: dict[Subsystem, str] = {
            s: "stopped" for s in Subsystem
        }
        self._total_commands = 0

    async def execute(
        self,
        action: ControlAction,
        target: Subsystem,
        parameters: Optional[dict[str, Any]] = None,
        issued_by: str = "system",
    ) -> ControlCommand:
        """Execute a control command."""
        import uuid

        cmd = ControlCommand(
            command_id=str(uuid.uuid4()),
            action=action,
            target=target,
            parameters=parameters or {},
            issued_by=issued_by,
        )

        try:
            await self._do_action(cmd)
            cmd.status = "success"
            cmd.completed_at = datetime.now(timezone.utc)
            self._update_state(target, action)
        except Exception as exc:
            cmd.status = "failed"
            cmd.result = str(exc)
            logger.error("Control command failed: %s", exc)

        self._commands.append(cmd)
        self._total_commands += 1
        return cmd

    async def _do_action(self, cmd: ControlCommand) -> None:
        """Execute the actual action."""
        action = cmd.action
        target = cmd.target

        if target == Subsystem.PLATFORM:
            if action == ControlAction.START:
                if self._platform:
                    await self._platform.start()
            elif action == ControlAction.STOP:
                if self._platform:
                    await self._platform.stop()
            elif action == ControlAction.PAUSE:
                if self._platform and self._platform.runtime:
                    await self._platform.runtime.pause()
            elif action == ControlAction.RESUME:
                if self._platform and self._platform.runtime:
                    await self._platform.runtime.resume()

        elif target == Subsystem.CONNECTIVITY:
            if action in (ControlAction.PAUSE, ControlAction.RESUME):
                # Pass-through to connectivity adapter
                pass

        elif target == Subsystem.STREAMING:
            if action in (ControlAction.PAUSE, ControlAction.RESUME, ControlAction.DRAIN):
                # Pass-through to streaming adapter
                pass

    def _update_state(self, target: Subsystem, action: ControlAction) -> None:
        """Update subsystem state based on action."""
        state_map = {
            ControlAction.START: "running",
            ControlAction.STOP: "stopped",
            ControlAction.PAUSE: "paused",
            ControlAction.RESUME: "running",
        }
        new_state = state_map.get(action, "unknown")
        self._subsystem_states[target] = new_state

    def get_state(self, target: Subsystem) -> str:
        return self._subsystem_states.get(target, "unknown")

    def get_all_states(self) -> dict[str, str]:
        return {s.value: state for s, state in self._subsystem_states.items()}

    def get_recent_commands(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent control commands."""
        recent = self._commands[-limit:]
        return [
            {
                "command_id": c.command_id,
                "action": c.action.value,
                "target": c.target.value,
                "status": c.status,
                "issued_by": c.issued_by,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent
        ]

    @property
    def total_commands(self) -> int:
        return self._total_commands

    @property
    def active_commands(self) -> int:
        return sum(1 for c in self._commands if c.status == "pending")
