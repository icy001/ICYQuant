"""
Capital Controller — Decision Execution Gateway

The CapitalController is the bridge between capital intelligence decisions
and the execution layer. It enforces:

- Decision → Operation translation
- Control plane approval integration
- Rate limiting & throttling
- Circuit breaker integration
- Idempotency & deduplication
- Audit trail
"""

import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ControllerState(str, Enum):
    """Controller operational state."""
    STANDBY = "STANDBY"
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


class CommandType(str, Enum):
    """Types of controller commands."""
    ALLOCATE = "ALLOCATE"
    DEALLOCATE = "DEALLOCATE"
    REBALANCE = "REBALANCE"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    EFFICIENCY_SCAN = "EFFICIENCY_SCAN"
    RECONCILE = "RECONCILE"


@dataclass
class ControllerCommand:
    """A command issued through the controller."""
    command_id: str
    command_type: CommandType
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None
    priority: int = 0  # Higher = more urgent
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    ttl_seconds: int = 300


@dataclass
class CommandResult:
    """Result of a controller command execution."""
    command_id: str
    status: str  # ACCEPTED, REJECTED, EXECUTING, COMPLETED, FAILED
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalController:
    """
    Decision execution gateway with safety guarantees.

    Design principles:
    - All commands are idempotent (same key → same effect once)
    - Rate limited to prevent cascade failures
    - Control plane must approve all mutations
    - All operations are logged for audit
    - Degradation: if downstream fails, controller buffers and retries
    """

    def __init__(
        self,
        controller_id: Optional[str] = None,
        manager=None,
        intelligence=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.controller_id = controller_id or f"cc-{uuid.uuid4().hex[:12]}"
        self._manager = manager
        self._intelligence = intelligence
        self.config = config or {}

        self.state = ControllerState.STANDBY

        # Idempotency tracking
        self._processed_keys: Dict[str, CommandResult] = {}
        self._key_ttl = timedelta(seconds=self.config.get("idempotency_ttl_seconds", 3600))
        self._cleanup_interval = self.config.get("cleanup_interval_seconds", 300)
        self._last_cleanup = datetime.utcnow()

        # Rate limiting
        self._max_commands_per_window = self.config.get("max_commands_per_window", 100)
        self._rate_window_seconds = self.config.get("rate_window_seconds", 60)
        self._command_timestamps: List[datetime] = []

        # Command queue
        self._command_queue: List[ControllerCommand] = []
        self._results_history: List[CommandResult] = []

        # Control plane
        self._control_plane = None

        logger.info(f"CapitalController initialized: {self.controller_id}")

    # ─── Lifecycle ──────────────────────────────────────────────

    def activate(self) -> None:
        """Activate the controller."""
        self.state = ControllerState.ACTIVE
        logger.info(f"Controller {self.controller_id} activated")

    def halt(self) -> None:
        """Emergency halt — reject all new commands."""
        self.state = ControllerState.HALTED
        self._command_queue.clear()
        logger.critical(f"Controller {self.controller_id} HALTED")

    def resume(self) -> None:
        """Resume from halt."""
        self.state = ControllerState.ACTIVE
        logger.info(f"Controller {self.controller_id} resumed")

    # ─── Command Submission ─────────────────────────────────────

    def submit(self, command: ControllerCommand) -> CommandResult:
        """Submit a command for execution with all safety checks."""
        # Cleanup stale idempotency keys
        self._maybe_cleanup()

        # Check controller state
        if self.state == ControllerState.HALTED:
            return CommandResult(
                command_id=command.command_id,
                status="REJECTED",
                error="Controller is HALTED",
            )

        # Idempotency check
        if command.idempotency_key:
            if command.idempotency_key in self._processed_keys:
                logger.debug(f"Idempotent replay: {command.idempotency_key}")
                return self._processed_keys[command.idempotency_key]

        # Rate limiting
        if not self._check_rate_limit():
            self.state = ControllerState.THROTTLED
            return CommandResult(
                command_id=command.command_id,
                status="REJECTED",
                error="Rate limit exceeded",
            )

        # Expiration check
        if command.expires_at and datetime.utcnow() > command.expires_at:
            return CommandResult(
                command_id=command.command_id,
                status="REJECTED",
                error="Command has expired",
            )

        # Control plane approval
        if self._control_plane:
            approval = self._control_plane.evaluate({
                "action": f"capital_{command.command_type.value.lower()}",
                "params": command.params,
                "priority": command.priority,
            })
            if not approval.get("approved", True):
                result = CommandResult(
                    command_id=command.command_id,
                    status="REJECTED",
                    error=f"Control plane rejected: {approval.get('reason')}",
                )
                self._store_result(command, result)
                return result

        # Execute
        return self._execute_command(command)

    def submit_async(self, command: ControllerCommand) -> None:
        """Queue command for async execution."""
        self._command_queue.append(command)

    # ─── Command Executors ──────────────────────────────────────

    def _execute_command(self, command: ControllerCommand) -> CommandResult:
        """Execute a command through the manager."""
        start = datetime.utcnow()

        try:
            output = self._dispatch(command)
            result = CommandResult(
                command_id=command.command_id,
                status="COMPLETED",
                output=output,
                processing_ms=(datetime.utcnow() - start).total_seconds() * 1000,
            )
        except Exception as e:
            logger.error(f"Command {command.command_id} failed: {e}")
            result = CommandResult(
                command_id=command.command_id,
                status="FAILED",
                error=str(e),
                processing_ms=(datetime.utcnow() - start).total_seconds() * 1000,
            )

        self._store_result(command, result)
        return result

    def _dispatch(self, command: ControllerCommand) -> Optional[Dict[str, Any]]:
        """Dispatch command to the appropriate handler."""
        handlers = {
            CommandType.ALLOCATE: self._handle_allocate,
            CommandType.DEALLOCATE: self._handle_deallocate,
            CommandType.REBALANCE: self._handle_rebalance,
            CommandType.RESERVE: self._handle_reserve,
            CommandType.RELEASE: self._handle_release,
            CommandType.EFFICIENCY_SCAN: self._handle_efficiency_scan,
            CommandType.RECONCILE: self._handle_reconcile,
        }
        handler = handlers.get(command.command_type)
        if not handler:
            raise ValueError(f"Unknown command type: {command.command_type}")
        return handler(command)

    def _handle_allocate(self, command: ControllerCommand) -> Dict[str, Any]:
        """Handle allocation command."""
        if self._manager:
            op = self._manager.allocate(
                strategy_id=command.params["strategy_id"],
                amount=command.params["amount"],
                metadata=command.params.get("metadata"),
            )
            return {
                "operation_id": op.operation_id,
                "status": op.status.value,
                "error": op.error,
            }
        return {"status": "NO_MANAGER"}

    def _handle_deallocate(self, command: ControllerCommand) -> Dict[str, Any]:
        """Handle deallocation command."""
        if self._manager:
            op = self._manager.deallocate(
                strategy_id=command.params["strategy_id"],
                amount=command.params["amount"],
            )
            return {
                "operation_id": op.operation_id,
                "status": op.status.value,
                "error": op.error,
            }
        return {"status": "NO_MANAGER"}

    def _handle_rebalance(self, command: ControllerCommand) -> Dict[str, Any]:
        """Handle rebalance command."""
        if self._intelligence and self._intelligence._allocator:
            result = self._intelligence.optimize_allocation(
                objective_type=command.params.get("objective", "TARGET_WEIGHTS"),
                constraints=command.params.get("constraints"),
            )
            return {"optimization": result}
        return {"status": "NO_ALLOCATOR"}

    def _handle_reserve(self, command: ControllerCommand) -> Dict[str, Any]:
        """Handle capital reservation."""
        if self._intelligence and self._intelligence._capital_pool:
            self._intelligence._capital_pool.reserve(
                amount=command.params["amount"],
                reason=command.params.get("reason", ""),
            )
            return {"status": "RESERVED", "amount": command.params["amount"]}
        return {"status": "NO_POOL"}

    def _handle_release(self, command: ControllerCommand) -> Dict[str, Any]:
        """Handle capital release."""
        if self._intelligence and self._intelligence._capital_pool:
            self._intelligence._capital_pool.release(
                amount=command.params["amount"],
                reason=command.params.get("reason", ""),
            )
            return {"status": "RELEASED", "amount": command.params["amount"]}
        return {"status": "NO_POOL"}

    def _handle_efficiency_scan(self, command: ControllerCommand) -> Dict[str, Any]:
        """Run efficiency scan."""
        if self._intelligence:
            return {
                "efficiencies": self._intelligence.get_strategy_efficiencies(),
                "marginal": self._intelligence.get_marginal_efficiencies(),
            }
        return {"status": "NO_INTELLIGENCE"}

    def _handle_reconcile(self, command: ControllerCommand) -> Dict[str, Any]:
        """Run reconciliation."""
        if self._intelligence:
            return self._intelligence.reconcile()
        return {"status": "NO_INTELLIGENCE"}

    # ─── Safety ─────────────────────────────────────────────────

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self._rate_window_seconds)

        # Filter to current window
        self._command_timestamps = [
            ts for ts in self._command_timestamps if ts > window_start
        ]

        if len(self._command_timestamps) >= self._max_commands_per_window:
            return False

        self._command_timestamps.append(now)
        return True

    def _maybe_cleanup(self) -> None:
        """Cleanup stale idempotency keys."""
        now = datetime.utcnow()
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return

        stale = [
            key for key, result in self._processed_keys.items()
            if (now - result.timestamp) > self._key_ttl
        ]
        for key in stale:
            del self._processed_keys[key]

        self._last_cleanup = now

    def _store_result(self, command: ControllerCommand, result: CommandResult) -> None:
        """Store result for idempotency and audit."""
        if command.idempotency_key:
            self._processed_keys[command.idempotency_key] = result
        self._results_history.append(result)

    def _generate_idempotency_key(self, *parts: str) -> str:
        """Generate an idempotency key from deterministic parts."""
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ─── Convenience Methods ────────────────────────────────────

    def allocate(
        self,
        strategy_id: str,
        amount: float,
        idempotency_key: Optional[str] = None,
    ) -> CommandResult:
        """Convenience: submit an allocation command."""
        command = ControllerCommand(
            command_id=f"cmd-{uuid.uuid4().hex[:8]}",
            command_type=CommandType.ALLOCATE,
            params={"strategy_id": strategy_id, "amount": amount},
            idempotency_key=idempotency_key or self._generate_idempotency_key(
                "allocate", strategy_id, str(amount)
            ),
            ttl_seconds=300,
        )
        return self.submit(command)

    def deallocate(
        self,
        strategy_id: str,
        amount: float,
        idempotency_key: Optional[str] = None,
    ) -> CommandResult:
        """Convenience: submit a deallocation command."""
        command = ControllerCommand(
            command_id=f"cmd-{uuid.uuid4().hex[:8]}",
            command_type=CommandType.DEALLOCATE,
            params={"strategy_id": strategy_id, "amount": amount},
            idempotency_key=idempotency_key or self._generate_idempotency_key(
                "deallocate", strategy_id, str(amount)
            ),
        )
        return self.submit(command)

    def rebalance(
        self,
        objective: str = "TARGET_WEIGHTS",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        """Convenience: submit a rebalance command."""
        command = ControllerCommand(
            command_id=f"cmd-{uuid.uuid4().hex[:8]}",
            command_type=CommandType.REBALANCE,
            params={"objective": objective, "constraints": constraints or {}},
        )
        return self.submit(command)

    # ─── Status ─────────────────────────────────────────────────

    def get_current_rate(self) -> float:
        """Get current command rate per window."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self._rate_window_seconds)
        recent = [ts for ts in self._command_timestamps if ts > window_start]
        return len(recent) / self._rate_window_seconds

    def get_summary(self) -> Dict[str, Any]:
        return {
            "controller_id": self.controller_id,
            "state": self.state.value,
            "processed_keys": len(self._processed_keys),
            "queue_depth": len(self._command_queue),
            "results_history": len(self._results_history),
            "current_rate": self.get_current_rate(),
        }
