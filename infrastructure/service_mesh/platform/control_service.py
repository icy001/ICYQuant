"""Mesh Control Service for the Service Mesh Platform.

Provides ``MeshControlService`` as the unified controller for
mesh platform operations including configuration, policy,
security, runtime, and upgrade orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics
from .diagnostics import PlatformDiagnostics

logger = logging.getLogger(__name__)


class ControlAction(str):
    """Control actions for the mesh platform."""

    CONFIGURATION = "configuration"
    POLICY = "policy"
    SECURITY = "security"
    RUNTIME = "runtime"
    UPGRADE = "upgrade"
    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    INJECTION = "injection"
    CLUSTER = "cluster"


class ControlCommand:
    """A control command to be executed by the control service."""

    def __init__(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        command_id: Optional[str] = None,
    ) -> None:
        self.action = action
        self.params = params or {}
        self.command_id = command_id or f"cmd-{time.monotonic_ns()}"
        self.created_at = datetime.utcnow()
        self.result: Optional[Dict[str, Any]] = None
        self.executed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "action": self.action,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "executed": self.executed,
            "result": self.result,
        }


class MeshControlService:
    """Unified controller for the mesh platform."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
        diagnostics: Optional[PlatformDiagnostics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._diagnostics = diagnostics or PlatformDiagnostics()
        self._handlers: Dict[str, Callable] = {}
        self._sync_handlers: Dict[str, Callable] = {}
        self._command_history: List[ControlCommand] = []
        self._max_history = 200
        self._command_count = 0
        self._running = False
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_handler(
            ControlAction.CONFIGURATION,
            self._handle_configuration,
        )
        self.register_handler(
            ControlAction.POLICY,
            self._handle_policy,
        )
        self.register_handler(
            ControlAction.SECURITY,
            self._handle_security,
        )
        self.register_handler(
            ControlAction.RUNTIME,
            self._handle_runtime,
        )
        self.register_handler(
            ControlAction.UPGRADE,
            self._handle_upgrade,
        )
        self.register_handler(
            ControlAction.SNAPSHOT,
            self._handle_snapshot,
        )
        self.register_handler(
            ControlAction.RESTORE,
            self._handle_restore,
        )

    def register_handler(
        self,
        action: str,
        handler: Callable,
    ) -> None:
        self._handlers[action] = handler

    def register_sync_handler(
        self,
        action: str,
        handler: Callable,
    ) -> None:
        self._sync_handlers[action] = handler

    async def execute(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a control action."""
        command = ControlCommand(action, params)
        handler = self._handlers.get(action)

        if handler is None:
            command.result = {
                "success": False,
                "error": f"No handler for action: {action}",
            }
            command.executed = True
            self._add_to_history(command)
            return command.result

        try:
            result = handler(params)
            if asyncio.iscoroutine(result):
                result = await result
            command.result = result
            self._metrics.increment_counter(
                "icyquant_mesh_control_commands_total",
                labels={"action": action},
            )
            self._telemetry.log_platform_event(
                "control_command_executed",
                action,
                {"command_id": command.command_id},
            )
        except Exception as exc:
            command.result = {
                "success": False,
                "error": str(exc),
                "action": action,
            }
            self._telemetry.log_error(
                "control_service",
                "command_failed",
                str(exc),
                {"action": action},
            )
            self._diagnostics.report_issue(
                "critical",
                "control_service",
                "command_failed",
                str(exc),
                {"action": action},
            )

        command.executed = True
        self._add_to_history(command)
        return command.result or {"success": True}

    async def synchronize(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronize state for a control action."""
        handler = self._sync_handlers.get(action)
        if handler is None:
            return {
                "success": True,
                "synced": False,
                "message": f"No sync handler for: {action}",
            }

        try:
            result = handler(params)
            if asyncio.iscoroutine(result):
                result = await result
            return {
                "success": True,
                "synced": True,
                "action": action,
                "result": result,
            }
        except Exception as exc:
            self._telemetry.log_error(
                "control_service",
                "sync_failed",
                str(exc),
                {"action": action},
            )
            return {
                "success": False,
                "synced": False,
                "error": str(exc),
            }

    async def start(self) -> Dict[str, Any]:
        self._running = True
        self._telemetry.log_platform_event(
            "control_service_started", "control_service",
        )
        return {"success": True}

    async def stop(self) -> Dict[str, Any]:
        self._running = False
        self._telemetry.log_platform_event(
            "control_service_stopped", "control_service",
        )
        return {"success": True}

    @property
    def is_running(self) -> bool:
        return self._running

    def _add_to_history(self, command: ControlCommand) -> None:
        self._command_count += 1
        with self._lock:
            self._command_history.append(command)
            if len(self._command_history) > self._max_history:
                self._command_history = (
                    self._command_history[-self._max_history:]
                )

    def get_command_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                cmd.to_dict()
                for cmd in self._command_history[-limit:]
            ]

    # Default handlers
    def _handle_configuration(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "configuration",
            "applied": bool(params),
        }

    def _handle_policy(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "policy",
            "updated": bool(params),
        }

    def _handle_security(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "security",
            "status": "verified",
        }

    def _handle_runtime(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "runtime",
            "operation": params.get("operation", "status")
            if params
            else "status",
        }

    def _handle_upgrade(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "upgrade",
            "status": "initiated",
        }

    def _handle_snapshot(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "snapshot",
            "snapshot_id": f"snap-{time.monotonic_ns()}",
        }

    def _handle_restore(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "restore",
            "restored": True,
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "command_count": self._command_count,
                "handler_count": len(self._handlers),
                "sync_handler_count": len(self._sync_handlers),
                "history_size": len(self._command_history),
            }

    def __repr__(self) -> str:
        return (
            f"MeshControlService(handlers={len(self._handlers)}, "
            f"running={self._running})"
        )
