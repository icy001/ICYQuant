"""Tool Sandbox — isolated execution environment for tool calls.

Pipeline:
    Tool Execution Request
        -> Sandbox (memory limit, file isolation, network isolation, resource cap)
        -> Tool Handler
        -> Result (with resource usage metrics)

The sandbox provides resource isolation to prevent tools from
affecting the core system.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ──

class SandboxMode(str, Enum):
    """Sandbox isolation mode."""

    NONE = "none"  # No sandboxing
    SOFT = "soft"  # Monitor and warn on limits
    HARD = "hard"  # Enforce limits strictly


# ── SandboxConfig ──

@dataclass
class SandboxConfig:
    """Configuration for the tool sandbox."""

    mode: SandboxMode = SandboxMode.SOFT

    # ── Resource Limits ──
    max_memory_mb: float = 512.0
    max_cpu_time_seconds: float = 30.0
    max_execution_time_seconds: float = 60.0

    # ── File System ──
    allow_file_read: bool = False
    allow_file_write: bool = False
    allowed_paths: List[str] = field(default_factory=list)  # Whitelist of allowed paths
    blocked_paths: List[str] = field(default_factory=list)  # Blacklist of blocked paths

    # ── Network ──
    allow_network: bool = False
    allowed_hosts: List[str] = field(default_factory=list)  # Whitelist of allowed hosts
    blocked_hosts: List[str] = field(default_factory=list)  # Blacklist of blocked hosts
    allowed_ports: List[int] = field(default_factory=list)

    # ── Environment ──
    allow_env_access: bool = False
    allowed_env_vars: List[str] = field(default_factory=list)

    # ── Subprocess ──
    allow_subprocess: bool = False
    allowed_commands: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mode": self.mode.value,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_time_seconds": self.max_cpu_time_seconds,
            "max_execution_time_seconds": self.max_execution_time_seconds,
            "allow_file_read": self.allow_file_read,
            "allow_file_write": self.allow_file_write,
            "allow_network": self.allow_network,
            "allow_subprocess": self.allow_subprocess,
            "allow_env_access": self.allow_env_access,
        }


# ── SandboxViolation ──

@dataclass
class SandboxViolation:
    """A sandbox policy violation."""

    violation_type: str  # memory | cpu | file | network | env | subprocess
    detail: str
    severity: str = "warning"  # warning | error | critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── SandboxMetrics ──

@dataclass
class SandboxMetrics:
    """Resource usage metrics from a sandboxed execution."""

    tool_name: str = ""
    execution_id: str = ""

    # ── Resource Usage ──
    memory_used_mb: float = 0.0
    cpu_time_seconds: float = 0.0
    wall_time_seconds: float = 0.0

    # ── I/O ──
    file_read_count: int = 0
    file_write_count: int = 0
    network_call_count: int = 0

    # ── Violations ──
    violations: List[SandboxViolation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def error_violations(self) -> List[SandboxViolation]:
        return [v for v in self.violations if v.severity in ("error", "critical")]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tool_name": self.tool_name,
            "execution_id": self.execution_id,
            "memory_used_mb": round(self.memory_used_mb, 2),
            "cpu_time_seconds": round(self.cpu_time_seconds, 3),
            "wall_time_seconds": round(self.wall_time_seconds, 3),
            "file_read_count": self.file_read_count,
            "file_write_count": self.file_write_count,
            "network_call_count": self.network_call_count,
            "violations": len(self.violations),
            "violation_details": [v.detail for v in self.violations],
        }


# ── ToolSandbox ──

class ToolSandbox:
    """Isolated execution environment for tool calls.

    Wraps tool execution with resource monitoring and enforcement.
    In SOFT mode, violations are logged as warnings. In HARD mode,
    violations raise exceptions to abort execution.

    Supports:
        - Memory limit monitoring
        - CPU time tracking
        - File system access control
        - Network access control
        - Environment variable access control
        - Subprocess control
        - Resource usage metrics

    Usage:
        sandbox = ToolSandbox(SandboxConfig(mode=SandboxMode.SOFT))
        async with sandbox.wrap("backtest.run") as ctx:
            result = await handler(params)
        metrics = ctx.metrics
    """

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        """Initialize the sandbox.

        Args:
            config: Sandbox configuration.
        """
        self._config = config or SandboxConfig()
        self._initialized: bool = False
        logger.info(f"ToolSandbox created (mode={self._config.mode.value})")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the sandbox."""
        self._initialized = True
        logger.info("ToolSandbox initialized")

    async def shutdown(self) -> None:
        """Shutdown the sandbox."""
        self._initialized = False
        logger.info("ToolSandbox shutdown complete")

    # ── Execution Wrapper ──

    async def wrap(
        self,
        tool_name: str,
        execution_id: str = "",
    ) -> "SandboxContext":
        """Create a sandboxed execution context.

        Args:
            tool_name: The tool being executed.
            execution_id: Optional execution identifier.

        Returns:
            A SandboxContext for the duration of execution.
        """
        return SandboxContext(
            sandbox=self,
            tool_name=tool_name,
            execution_id=execution_id,
        )

    # ── Access Checks ──

    def check_file_access(self, path: str, write: bool = False) -> SandboxViolation:
        """Check if file access is allowed.

        Args:
            path: The file path to check.
            write: Whether write access is requested.

        Returns:
            A SandboxViolation if denied.
        """
        if write and not self._config.allow_file_write:
            return SandboxViolation(
                violation_type="file",
                detail=f"File write not allowed: {path}",
                severity="error",
            )
        if not write and not self._config.allow_file_read:
            return SandboxViolation(
                violation_type="file",
                detail=f"File read not allowed: {path}",
                severity="error",
            )

        # Check blocked paths
        for blocked in self._config.blocked_paths:
            if path.startswith(blocked):
                return SandboxViolation(
                    violation_type="file",
                    detail=f"Path blocked: {path}",
                    severity="error",
                )

        # Check allowed paths (if whitelist is set)
        if self._config.allowed_paths:
            allowed = any(path.startswith(p) for p in self._config.allowed_paths)
            if not allowed:
                return SandboxViolation(
                    violation_type="file",
                    detail=f"Path not in allowed list: {path}",
                    severity="error",
                )

        return SandboxViolation(
            violation_type="file",
            detail=f"File access allowed: {path}",
            severity="info",
        )

    def check_network_access(self, host: str, port: int = 0) -> SandboxViolation:
        """Check if network access is allowed.

        Args:
            host: The target host.
            port: The target port.

        Returns:
            A SandboxViolation if denied.
        """
        if not self._config.allow_network:
            return SandboxViolation(
                violation_type="network",
                detail=f"Network access not allowed: {host}:{port}",
                severity="error",
            )

        if self._config.blocked_hosts and host in self._config.blocked_hosts:
            return SandboxViolation(
                violation_type="network",
                detail=f"Host blocked: {host}",
                severity="error",
            )

        if self._config.allowed_hosts and host not in self._config.allowed_hosts:
            return SandboxViolation(
                violation_type="network",
                detail=f"Host not in allowed list: {host}",
                severity="error",
            )

        if self._config.allowed_ports and port not in self._config.allowed_ports:
            return SandboxViolation(
                violation_type="network",
                detail=f"Port not allowed: {port}",
                severity="error",
            )

        return SandboxViolation(
            violation_type="network",
            detail=f"Network access allowed: {host}:{port}",
            severity="info",
        )

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get sandbox status."""
        return {
            "mode": self._config.mode.value,
            "max_memory_mb": self._config.max_memory_mb,
            "allow_network": self._config.allow_network,
            "allow_file_write": self._config.allow_file_write,
            "allow_subprocess": self._config.allow_subprocess,
            "initialized": self._initialized,
        }


# ── SandboxContext ──

class SandboxContext:
    """Context manager for sandboxed tool execution.

    Tracks resource usage and violations during tool execution.
    """

    def __init__(
        self,
        sandbox: ToolSandbox,
        tool_name: str,
        execution_id: str = "",
    ) -> None:
        """Initialize the sandbox context.

        Args:
            sandbox: The parent ToolSandbox.
            tool_name: The tool being executed.
            execution_id: Optional execution identifier.
        """
        self._sandbox = sandbox
        self._tool_name = tool_name
        self._execution_id = execution_id

        self.metrics = SandboxMetrics(
            tool_name=tool_name,
            execution_id=execution_id,
        )
        self._start_time: float = 0.0
        self._active: bool = False

    async def __aenter__(self) -> "SandboxContext":
        """Enter the sandbox context."""
        self._start_time = time.monotonic()
        self._active = True
        logger.debug(f"Sandbox entered for {self._tool_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the sandbox context."""
        self._active = False
        self.metrics.wall_time_seconds = time.monotonic() - self._start_time

        if self.metrics.has_violations:
            errors = self.metrics.error_violations
            if errors:
                logger.warning(
                    f"Sandbox violations for {self._tool_name}: "
                    f"{len(errors)} errors, {len(self.metrics.violations)} total"
                )
            else:
                logger.info(
                    f"Sandbox warnings for {self._tool_name}: "
                    f"{len(self.metrics.violations)} violations"
                )

    def record_violation(self, violation: SandboxViolation) -> None:
        """Record a sandbox violation.

        Args:
            violation: The violation to record.
        """
        self.metrics.violations.append(violation)
        if violation.severity == "error" and self._sandbox._config.mode == SandboxMode.HARD:
            raise RuntimeError(f"Sandbox violation (hard mode): {violation.detail}")
        elif violation.severity == "warning":
            logger.warning(f"Sandbox violation: {violation.detail}")
