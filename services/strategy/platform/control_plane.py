"""
Strategy Control Plane — Central command authority for all production strategies.

Handles registration, deployment orchestration, version management,
lifecycle governance, and execution coordination across the platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ControlCommand(str, Enum):
    """Commands issued through the control plane."""
    REGISTER = "register"
    DEPLOY = "deploy"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RESTART = "restart"
    ROLLBACK = "rollback"
    CANARY = "canary"
    PROMOTE = "promote"
    ARCHIVE = "archive"
    DELETE = "delete"
    SCALE = "scale"
    RECONFIGURE = "reconfigure"


@dataclass
class ControlResult:
    """Result of a control plane command execution."""
    command: ControlCommand
    strategy_id: str
    success: bool
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class StrategyRegistration:
    """Strategy registration record."""
    strategy_id: str
    name: str
    version: str
    owner: str
    status: str = "registered"
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ControlPlane:
    """
    Central control plane for all production strategies.

    Acts as the single source of truth for strategy state, handling
    registration, deployment orchestration, and lifecycle commands.

    Usage::

        cp = ControlPlane(audit_center=audit, event_bridge=events)
        await cp.initialize()
        await cp.execute_command(strategy_id, ControlCommand.DEPLOY, {...})
    """

    def __init__(
        self,
        audit_center: Any = None,
        event_bridge: Any = None,
    ) -> None:
        self._audit_center = audit_center
        self._event_bridge = event_bridge
        self._registrations: dict[str, StrategyRegistration] = {}
        self._command_handlers: dict[ControlCommand, Callable] = {}
        self._command_history: list[ControlResult] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the control plane."""
        self._register_default_handlers()
        logger.info("ControlPlane initialized.")

    async def start(self) -> None:
        """Start the control plane."""
        logger.info("ControlPlane started.")

    async def stop(self) -> None:
        """Stop the control plane."""
        logger.info("ControlPlane stopped.")

    # ---- Registration ----

    async def register(self, registration: StrategyRegistration) -> ControlResult:
        """Register a strategy in the control plane."""
        async with self._lock:
            if registration.strategy_id in self._registrations:
                return ControlResult(
                    command=ControlCommand.REGISTER,
                    strategy_id=registration.strategy_id,
                    success=False,
                    message=f"Strategy already registered: {registration.strategy_id}",
                )

            self._registrations[registration.strategy_id] = registration
            result = ControlResult(
                command=ControlCommand.REGISTER,
                strategy_id=registration.strategy_id,
                success=True,
                message=f"Strategy registered: {registration.strategy_id}",
            )

            await self._emit_event("strategy.registered", {
                "strategy_id": registration.strategy_id,
                "name": registration.name,
                "version": registration.version,
            })
            await self._audit("strategy.register", f"Registered {registration.strategy_id}")

        self._command_history.append(result)
        return result

    async def unregister(self, strategy_id: str) -> ControlResult:
        """Remove a strategy from the control plane."""
        async with self._lock:
            if strategy_id not in self._registrations:
                return ControlResult(
                    command=ControlCommand.DELETE,
                    strategy_id=strategy_id,
                    success=False,
                    message=f"Strategy not found: {strategy_id}",
                )
            del self._registrations[strategy_id]
            result = ControlResult(
                command=ControlCommand.DELETE,
                strategy_id=strategy_id,
                success=True,
                message=f"Strategy unregistered: {strategy_id}",
            )
        self._command_history.append(result)
        return result

    async def get_registration(self, strategy_id: str) -> Optional[StrategyRegistration]:
        """Get a strategy registration record."""
        return self._registrations.get(strategy_id)

    async def list_registrations(self) -> list[StrategyRegistration]:
        """List all registered strategies."""
        return list(self._registrations.values())

    # ---- Command Execution ----

    async def execute_command(
        self,
        strategy_id: str,
        command: ControlCommand,
        params: Optional[dict[str, Any]] = None,
    ) -> ControlResult:
        """Execute a control command for a strategy."""
        handler = self._command_handlers.get(command)
        if not handler:
            return ControlResult(
                command=command,
                strategy_id=strategy_id,
                success=False,
                message=f"Unknown command: {command}",
            )

        try:
            result = await handler(strategy_id, params or {})
            await self._emit_event(f"strategy.{command.value}", {
                "strategy_id": strategy_id,
                "result": result.success,
                "message": result.message,
            })
            await self._audit(f"strategy.{command.value}", result.message)
            self._command_history.append(result)
            return result
        except Exception as e:
            logger.error(f"Command {command} failed for {strategy_id}: {e}")
            result = ControlResult(
                command=command,
                strategy_id=strategy_id,
                success=False,
                error=str(e),
                message=f"Command failed: {e}",
            )
            self._command_history.append(result)
            return result

    async def get_command_history(
        self,
        strategy_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ControlResult]:
        """Get command execution history, optionally filtered by strategy."""
        results = self._command_history
        if strategy_id:
            results = [r for r in results if r.strategy_id == strategy_id]
        return results[-limit:]

    # ---- Internal ----

    def _register_default_handlers(self) -> None:
        """Register default command handlers."""
        self._command_handlers[ControlCommand.REGISTER] = self._handle_register
        self._command_handlers[ControlCommand.DEPLOY] = self._handle_deploy
        self._command_handlers[ControlCommand.START] = self._handle_start
        self._command_handlers[ControlCommand.PAUSE] = self._handle_pause
        self._command_handlers[ControlCommand.RESUME] = self._handle_resume
        self._command_handlers[ControlCommand.STOP] = self._handle_stop
        self._command_handlers[ControlCommand.ROLLBACK] = self._handle_rollback

    async def _handle_register(self, strategy_id: str, params: dict) -> ControlResult:
        registration = StrategyRegistration(
            strategy_id=strategy_id,
            name=params.get("name", strategy_id),
            version=params.get("version", "0.1.0"),
            owner=params.get("owner", "unknown"),
            metadata=params.get("metadata", {}),
        )
        return await self.register(registration)

    async def _handle_deploy(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.DEPLOY,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not registered: {strategy_id}",
            )
        self._registrations[strategy_id].status = "deployed"
        return ControlResult(
            command=ControlCommand.DEPLOY,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy deployed: {strategy_id}",
        )

    async def _handle_start(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.START,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not found: {strategy_id}",
            )
        self._registrations[strategy_id].status = "running"
        return ControlResult(
            command=ControlCommand.START,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy started: {strategy_id}",
        )

    async def _handle_pause(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.PAUSE,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not found: {strategy_id}",
            )
        self._registrations[strategy_id].status = "paused"
        return ControlResult(
            command=ControlCommand.PAUSE,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy paused: {strategy_id}",
        )

    async def _handle_resume(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.RESUME,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not found: {strategy_id}",
            )
        self._registrations[strategy_id].status = "running"
        return ControlResult(
            command=ControlCommand.RESUME,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy resumed: {strategy_id}",
        )

    async def _handle_stop(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.STOP,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not found: {strategy_id}",
            )
        self._registrations[strategy_id].status = "stopped"
        return ControlResult(
            command=ControlCommand.STOP,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy stopped: {strategy_id}",
        )

    async def _handle_rollback(self, strategy_id: str, params: dict) -> ControlResult:
        if strategy_id not in self._registrations:
            return ControlResult(
                command=ControlCommand.ROLLBACK,
                strategy_id=strategy_id,
                success=False,
                message=f"Strategy not found: {strategy_id}",
            )
        target_version = params.get("target_version", "previous")
        self._registrations[strategy_id].version = target_version
        return ControlResult(
            command=ControlCommand.ROLLBACK,
            strategy_id=strategy_id,
            success=True,
            message=f"Strategy rolled back to {target_version}: {strategy_id}",
        )

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bridge:
            try:
                await self._event_bridge.emit(event_type, payload)
            except Exception as e:
                logger.error(f"Event emit failed: {e}")

    async def _audit(self, category: str, message: str) -> None:
        if self._audit_center:
            try:
                await self._audit_center.record(category=category, message=message)
            except Exception as e:
                logger.error(f"Audit failed: {e}")
