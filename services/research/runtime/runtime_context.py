"""Runtime Context — execution context and configuration for research runtimes.

Captures environment settings, resource requirements, dependencies,
and configuration needed to reproduce an experiment execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class IsolationLevel(str, Enum):
    """Process isolation levels for runtime execution."""

    NONE = "none"         # Share process
    THREAD = "thread"     # Separate thread
    PROCESS = "process"   # Separate process
    CONTAINER = "container"  # Separate container


class RetryPolicy(str, Enum):
    """Retry policies for failed executions."""

    NEVER = "never"
    IMMEDIATE = "immediate"
    LINEAR = "linear"      # Fixed delay
    EXPONENTIAL = "exponential"  # Exponential backoff


@dataclass
class ExecutionConfig:
    """Resource and execution parameters for a research run."""

    # Resources
    cpu_cores: float = 1.0
    memory_mb: int = 512
    gpu_count: int = 0
    gpu_type: Optional[str] = None
    disk_mb: int = 1024

    # Timing
    timeout_seconds: int = 3600
    startup_timeout_seconds: int = 60

    # Retry
    max_retries: int = 0
    retry_policy: RetryPolicy = RetryPolicy.NEVER
    retry_delay_seconds: int = 5

    # Isolation
    isolation: IsolationLevel = IsolationLevel.PROCESS

    # Priority
    priority: int = 0  # Higher = more urgent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "gpu_count": self.gpu_count,
            "gpu_type": self.gpu_type,
            "disk_mb": self.disk_mb,
            "timeout_seconds": self.timeout_seconds,
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "max_retries": self.max_retries,
            "retry_policy": self.retry_policy.value,
            "retry_delay_seconds": self.retry_delay_seconds,
            "isolation": self.isolation.value,
            "priority": self.priority,
        }

    @classmethod
    def gpu_profile(cls, gpu_type: str = "T4") -> "ExecutionConfig":
        """Preset: GPU-accelerated execution."""
        return cls(cpu_cores=4, memory_mb=16384, gpu_count=1, gpu_type=gpu_type)

    @classmethod
    def high_memory_profile(cls) -> "ExecutionConfig":
        """Preset: high-memory execution."""
        return cls(cpu_cores=8, memory_mb=65536, disk_mb=102400)

    @classmethod
    def lightweight_profile(cls) -> "ExecutionConfig":
        """Preset: lightweight execution."""
        return cls(cpu_cores=1, memory_mb=256, isolation=IsolationLevel.THREAD)


@dataclass
class RuntimeContext:
    """Complete execution context for a research runtime.

    Captures everything needed to reproduce an experiment execution:
    environment, dependencies, configuration, and resource allocation.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    run_id: str = ""

    # Environment
    python_version: str = "3.11"
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Execution config
    config: ExecutionConfig = field(default_factory=ExecutionConfig)

    # Dependencies
    requirements: List[str] = field(default_factory=list)
    pip_packages: List[Dict[str, str]] = field(default_factory=list)

    # Data access
    dataset_ids: List[str] = field(default_factory=list)
    dataset_versions: Dict[str, int] = field(default_factory=dict)

    # Artifacts
    output_path: str = ""
    artifact_prefix: str = ""

    # Identity
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "python_version": self.python_version,
            "env_vars": self.env_vars,
            "config": self.config.to_dict(),
            "requirements": self.requirements,
            "pip_packages": self.pip_packages,
            "dataset_ids": self.dataset_ids,
            "dataset_versions": self.dataset_versions,
            "output_path": self.output_path,
            "artifact_prefix": self.artifact_prefix,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return (
            f"RuntimeContext(experiment={self.experiment_id[:8]}, "
            f"cpu={self.config.cpu_cores}, mem={self.config.memory_mb}MB)"
        )
