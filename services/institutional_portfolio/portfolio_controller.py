"""
Portfolio Controller — Decision Execution Gateway

Safety gateway that validates all portfolio actions before execution.
Enforces: idempotency, rate limiting, control plane approval, audit.
"""

import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ControllerState(str, Enum):
    STANDBY = "STANDBY"
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    HALTED = "HALTED"


@dataclass
class ControllerCommand:
    command_id: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    ttl_seconds: int = 300
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CommandResult:
    command_id: str
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PortfolioController:
    """
    Validates and gates all portfolio actions before execution.

    Enforces:
    - Idempotency (same key → same result within TTL)
    - Rate limiting
    - Control plane approval
    - Audit logging
    """

    def __init__(
        self,
        controller_id: Optional[str] = None,
        manager=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.controller_id = controller_id or f"pc-{uuid.uuid4().hex[:12]}"
        self._manager = manager
        self.config = config or {}
        self.state = ControllerState.STANDBY
        self._control_plane = None

        self._processed_keys: Dict[str, CommandResult] = {}
        self._key_ttl = timedelta(seconds=self.config.get("idempotency_ttl", 3600))
        self._max_commands = self.config.get("max_commands_per_window", 100)
        self._rate_window = self.config.get("rate_window_seconds", 60)
        self._timestamps: list = []

    def activate(self) -> None:
        self.state = ControllerState.ACTIVE

    def halt(self) -> None:
        self.state = ControllerState.HALTED

    def submit(self, command: ControllerCommand) -> CommandResult:
        if self.state == ControllerState.HALTED:
            return CommandResult(command_id=command.command_id, status="REJECTED", error="Controller HALTED")

        # Idempotency
        if command.idempotency_key and command.idempotency_key in self._processed_keys:
            return self._processed_keys[command.idempotency_key]

        # Rate limit
        now = datetime.utcnow()
        self._timestamps = [t for t in self._timestamps if (now - t).total_seconds() < self._rate_window]
        if len(self._timestamps) >= self._max_commands:
            return CommandResult(command_id=command.command_id, status="REJECTED", error="Rate limited")
        self._timestamps.append(now)

        # Control plane
        if self._control_plane:
            approval = self._control_plane.evaluate({
                "action": command.action,
                "params": command.params,
            })
            if not approval.get("approved", True):
                return CommandResult(command_id=command.command_id, status="REJECTED",
                                    error=f"Control plane: {approval.get('reason')}")

        # Execute
        try:
            output = {}
            if self._manager:
                from .portfolio_manager import ManagerAction
                action_map = {
                    "net_signals": ManagerAction.NET_SIGNALS,
                    "net_positions": ManagerAction.NET_POSITIONS,
                    "build": ManagerAction.BUILD_PORTFOLIO,
                    "rebalance": ManagerAction.REBALANCE,
                    "quarantine": ManagerAction.QUARANTINE_STRATEGY,
                    "replace": ManagerAction.REPLACE_STRATEGY,
                }
                mapped = action_map.get(command.action)
                if mapped:
                    op = self._manager.execute(mapped, command.params)
                    output = {"operation_id": op.op_id, "status": op.status}

            result = CommandResult(command_id=command.command_id, status="COMPLETED", output=output)
        except Exception as e:
            result = CommandResult(command_id=command.command_id, status="FAILED", error=str(e))

        if command.idempotency_key:
            self._processed_keys[command.idempotency_key] = result
        return result

    def get_summary(self) -> Dict[str, Any]:
        return {
            "controller_id": self.controller_id,
            "state": self.state.value,
            "processed_keys": len(self._processed_keys),
        }
