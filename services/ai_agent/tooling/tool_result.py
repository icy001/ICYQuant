"""Tool Result — unified result model for all tool executions.

Data flow:
    Tool Execution
        -> ToolResult (success / failure / error / data)
        -> Observation Engine
        -> Agent Memory
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── ToolResult ──

@dataclass
class ToolResult:
    """Unified result container for tool executions.

    Captures the outcome of any tool call, including success/failure
    status, output data, error details, and performance metrics.

    Supports:
        - Success / failure status
        - Structured output data
        - Error classification and details
        - Latency tracking
        - Retry information
        - Cache information
        - Serialization for observation pipeline

    Usage:
        result = ToolResult(
            tool_name="backtest.run",
            success=True,
            data={"sharpe_ratio": 1.5},
            latency_ms=125.3,
        )
    """

    tool_name: str
    success: bool = False

    # ── Output ──
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_type: str = ""  # validation | permission | runtime | timeout | unknown

    # ── Performance ──
    latency_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Execution Details ──
    execution_id: str = ""
    attempt: int = 1
    max_attempts: int = 1
    was_retried: bool = False

    # ── Cache ──
    from_cache: bool = False
    cache_key: Optional[str] = None

    # ── Permission ──
    permission_checked: bool = True
    permission_granted: bool = True

    # ── Warnings ──
    warnings: List[str] = field(default_factory=list)

    # ── Extra ──
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Properties ──

    @property
    def is_error(self) -> bool:
        return not self.success

    @property
    def has_data(self) -> bool:
        return self.data is not None

    @property
    def is_timeout(self) -> bool:
        return self.error_type == "timeout"

    @property
    def is_permission_denied(self) -> bool:
        return self.error_type == "permission"

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "latency_ms": round(self.latency_ms, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_id": self.execution_id,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "was_retried": self.was_retried,
            "from_cache": self.from_cache,
            "cache_key": self.cache_key,
            "permission_checked": self.permission_checked,
            "permission_granted": self.permission_granted,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

    def to_summary(self) -> Dict[str, Any]:
        """Get a compact summary of the result."""
        return {
            "tool": self.tool_name,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "from_cache": self.from_cache,
            "attempt": f"{self.attempt}/{self.max_attempts}",
        }

    # ── Factory Methods ──

    @classmethod
    def success_result(
        cls,
        tool_name: str,
        data: Any = None,
        latency_ms: float = 0.0,
        **kwargs: Any,
    ) -> "ToolResult":
        """Create a successful result.

        Args:
            tool_name: The tool name.
            data: Output data.
            latency_ms: Execution latency.
            **kwargs: Additional fields.

        Returns:
            A success ToolResult.
        """
        return cls(
            tool_name=tool_name,
            success=True,
            data=data,
            latency_ms=latency_ms,
            **kwargs,
        )

    @classmethod
    def error_result(
        cls,
        tool_name: str,
        error: str,
        error_type: str = "unknown",
        error_code: Optional[str] = None,
        latency_ms: float = 0.0,
        **kwargs: Any,
    ) -> "ToolResult":
        """Create an error result.

        Args:
            tool_name: The tool name.
            error: Error message.
            error_type: Error classification.
            error_code: Optional error code.
            latency_ms: Execution latency.
            **kwargs: Additional fields.

        Returns:
            An error ToolResult.
        """
        return cls(
            tool_name=tool_name,
            success=False,
            error=error,
            error_type=error_type,
            error_code=error_code,
            latency_ms=latency_ms,
            **kwargs,
        )

    @classmethod
    def permission_denied(
        cls,
        tool_name: str,
        error: str = "Permission denied",
    ) -> "ToolResult":
        """Create a permission-denied result.

        Args:
            tool_name: The tool name.
            error: Error message.

        Returns:
            A permission-denied ToolResult.
        """
        return cls(
            tool_name=tool_name,
            success=False,
            error=error,
            error_type="permission",
            permission_granted=False,
        )

    @classmethod
    def timeout_result(
        cls,
        tool_name: str,
        timeout_seconds: float,
        latency_ms: float = 0.0,
    ) -> "ToolResult":
        """Create a timeout result.

        Args:
            tool_name: The tool name.
            timeout_seconds: The configured timeout.
            latency_ms: Execution latency.

        Returns:
            A timeout ToolResult.
        """
        return cls(
            tool_name=tool_name,
            success=False,
            error=f"Execution timed out after {timeout_seconds}s",
            error_type="timeout",
            latency_ms=latency_ms,
        )
