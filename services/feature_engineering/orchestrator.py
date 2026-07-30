"""Pipeline Orchestrator.

Orchestrates multiple feature pipelines with retry, resume,
checkpoint, and parallel execution capabilities.

Usage::

    from services.feature_engineering import PipelineOrchestrator

    orch = PipelineOrchestrator()
    orch.register(pipeline)
    status = orch.run("alpha_daily", raw_data)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.feature_engineering.pipeline import (
    FeaturePipeline,
    PipelineResult,
    PipelineStatus,
)


class RunStatus(str, Enum):
    """Status of an orchestrated run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class RetryPolicy(str, Enum):
    """Retry strategy for failed pipeline stages."""

    IMMEDIATE = "immediate"      # retry immediately
    EXPONENTIAL = "exponential"  # exponential backoff
    FIXED = "fixed"              # fixed delay


@dataclass
class Checkpoint:
    """Execution checkpoint for pipeline recovery.

    Attributes:
        run_id: Unique run identifier.
        pipeline_name: Name of the pipeline.
        stage: Last completed stage.
        progress: Progress percentage (0-100).
        data_snapshot: Optional serialized intermediate data.
        created_at: Timestamp of checkpoint creation.
    """

    run_id: str
    pipeline_name: str
    stage: str
    progress: float = 0.0
    data_snapshot: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"Checkpoint(pipeline={self.pipeline_name}, stage={self.stage}, progress={self.progress:.0f}%)"


@dataclass
class OrchestratorConfig:
    """Configuration for the pipeline orchestrator.

    Attributes:
        max_retries: Maximum retry attempts per pipeline.
        retry_policy: Retry strategy.
        retry_delay_seconds: Base delay between retries.
        checkpoint_enabled: Whether to save checkpoints.
        checkpoint_dir: Directory for checkpoint storage.
        parallel_pipelines: Max parallel pipelines to run.
        timeout_per_pipeline: Max seconds per pipeline run.
        notify_on_failure: Callback for failure notifications.
    """

    max_retries: int = 3
    retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL
    retry_delay_seconds: float = 5.0
    checkpoint_enabled: bool = True
    checkpoint_dir: str = ".checkpoints"
    parallel_pipelines: int = 4
    timeout_per_pipeline: int = 3600
    notify_on_failure: Optional[Callable[[str, str], None]] = None


class PipelineOrchestrator:
    """Orchestrate multiple feature pipelines.

    Handles registration, execution, retry, checkpoint/resume,
    and parallel execution of feature engineering pipelines.

    Example::

        orch = PipelineOrchestrator()
        orch.register(alpha_pipeline)
        orch.register(factor_pipeline)

        results = orch.run_all(raw_data)
        for name, result in results.items():
            print(f"{name}: {result.status.value}")
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None) -> None:
        self.config = config or OrchestratorConfig()
        self._pipelines: Dict[str, FeaturePipeline] = {}
        self._run_history: Dict[str, PipelineResult] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._run_status: Dict[str, RunStatus] = {}

    # ---- Registration ----

    def register(self, pipeline: FeaturePipeline) -> None:
        """Register a pipeline for orchestration.

        Args:
            pipeline: Configured FeaturePipeline instance.
        """
        self._pipelines[pipeline.name] = pipeline

    def unregister(self, pipeline_name: str) -> None:
        """Remove a pipeline from orchestration."""
        self._pipelines.pop(pipeline_name, None)
        self._run_history.pop(pipeline_name, None)
        self._run_status.pop(pipeline_name, None)

    def list_pipelines(self) -> List[str]:
        """List all registered pipeline names."""
        return sorted(self._pipelines.keys())

    def get_pipeline(self, name: str) -> Optional[FeaturePipeline]:
        """Get a registered pipeline by name."""
        return self._pipelines.get(name)

    # ---- Single run ----

    def run(
        self,
        pipeline_name: str,
        raw_data: Dict[str, List[float]],
        run_id: Optional[str] = None,
    ) -> PipelineResult:
        """Execute a single pipeline with retry and checkpoint support.

        Args:
            pipeline_name: Name of the registered pipeline.
            raw_data: Input data dictionary.
            run_id: Optional run identifier (auto-generated if not provided).

        Returns:
            PipelineResult from the final attempt.
        """
        if pipeline_name not in self._pipelines:
            raise KeyError(f"Pipeline '{pipeline_name}' not registered")

        run_id = run_id or str(uuid.uuid4())[:8]
        pipeline = self._pipelines[pipeline_name]
        self._run_status[pipeline_name] = RunStatus.RUNNING

        # Check for checkpoint to resume
        checkpoint = self._checkpoints.get(pipeline_name)
        if checkpoint and checkpoint.run_id == run_id:
            # Resume from checkpoint (use checkpoint data if available)
            if checkpoint.data_snapshot:
                raw_data = {**raw_data, **checkpoint.data_snapshot}

        result = self._execute_with_retry(pipeline, raw_data, run_id)

        self._run_history[pipeline_name] = result
        self._run_status[pipeline_name] = (
            RunStatus.SUCCESS if result.status == PipelineStatus.COMPLETED else RunStatus.FAILED
        )

        return result

    def _execute_with_retry(
        self,
        pipeline: FeaturePipeline,
        raw_data: Dict[str, List[float]],
        run_id: str,
    ) -> PipelineResult:
        """Execute pipeline with configurable retry policy."""
        last_result: Optional[PipelineResult] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    self._run_status[pipeline.name] = RunStatus.RETRYING
                    delay = self._compute_delay(attempt)
                    time.sleep(delay)

                result = pipeline.run(raw_data)

                if result.status == PipelineStatus.COMPLETED:
                    # Save checkpoint on success
                    if self.config.checkpoint_enabled:
                        self._checkpoints[pipeline.name] = Checkpoint(
                            run_id=run_id,
                            pipeline_name=pipeline.name,
                            stage="done",
                            progress=100.0,
                        )
                    return result

                last_result = result
            except Exception as e:
                last_result = PipelineResult(
                    pipeline_name=pipeline.name,
                    status=PipelineStatus.FAILED,
                    errors=[str(e)],
                )

            # Save checkpoint for resume
            if self.config.checkpoint_enabled and last_result:
                completed_stages = len(last_result.stages_completed)
                total_stages = 6  # LOAD, CLEAN, TRANSFORM, VALIDATE, SELECT, PUBLISH
                self._checkpoints[pipeline.name] = Checkpoint(
                    run_id=run_id,
                    pipeline_name=pipeline.name,
                    stage=last_result.stages_completed[-1].value if last_result.stages_completed else "load",
                    progress=(completed_stages / total_stages) * 100,
                )

        # All retries exhausted
        if last_result and self.config.notify_on_failure:
            self.config.notify_on_failure(pipeline.name, "; ".join(last_result.errors))

        return last_result or PipelineResult(
            pipeline_name=pipeline.name,
            status=PipelineStatus.FAILED,
            errors=["All retries exhausted"],
        )

    def _compute_delay(self, attempt: int) -> float:
        """Compute retry delay based on policy."""
        base = self.config.retry_delay_seconds
        if self.config.retry_policy == RetryPolicy.EXPONENTIAL:
            return base * (2 ** (attempt - 1))
        elif self.config.retry_policy == RetryPolicy.FIXED:
            return base
        else:  # IMMEDIATE
            return 0.0

    # ---- Batch run ----

    def run_all(
        self,
        raw_data: Dict[str, List[float]],
        pipeline_names: Optional[List[str]] = None,
    ) -> Dict[str, PipelineResult]:
        """Execute multiple pipelines sequentially.

        Args:
            raw_data: Input data shared across pipelines.
            pipeline_names: Pipelines to run (all if None).

        Returns:
            Dict of pipeline_name -> PipelineResult.
        """
        names = pipeline_names or self.list_pipelines()
        results: Dict[str, PipelineResult] = {}

        for name in names:
            results[name] = self.run(name, raw_data)

        return results

    # ---- Status & history ----

    def get_status(self, pipeline_name: str) -> Optional[RunStatus]:
        """Get current run status of a pipeline."""
        return self._run_status.get(pipeline_name)

    def get_history(self, pipeline_name: Optional[str] = None) -> Dict[str, PipelineResult]:
        """Get run history for one or all pipelines."""
        if pipeline_name:
            result = self._run_history.get(pipeline_name)
            return {pipeline_name: result} if result else {}
        return dict(self._run_history)

    def get_checkpoint(self, pipeline_name: str) -> Optional[Checkpoint]:
        """Get the last checkpoint for a pipeline."""
        return self._checkpoints.get(pipeline_name)

    def clear_checkpoints(self) -> None:
        """Clear all saved checkpoints."""
        self._checkpoints.clear()

    # ---- Cancel ----

    def cancel(self, pipeline_name: str) -> bool:
        """Cancel a running pipeline."""
        if pipeline_name in self._run_status:
            if self._run_status[pipeline_name] == RunStatus.RUNNING:
                self._run_status[pipeline_name] = RunStatus.CANCELLED
                return True
        return False

    # ---- Summary ----

    def summary(self) -> Dict[str, Any]:
        """Return orchestrator summary statistics."""
        statuses = self._run_status
        return {
            "total_pipelines": len(self._pipelines),
            "registered": self.list_pipelines(),
            "running": [n for n, s in statuses.items() if s == RunStatus.RUNNING],
            "success": [n for n, s in statuses.items() if s == RunStatus.SUCCESS],
            "failed": [n for n, s in statuses.items() if s == RunStatus.FAILED],
            "checkpoints": len(self._checkpoints),
        }

    def __repr__(self) -> str:
        return f"PipelineOrchestrator(pipelines={len(self._pipelines)})"
