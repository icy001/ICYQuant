"""
ICYQuant Pipeline Checkpoint - Pipeline checkpointing and recovery.

Enables resuming ML pipelines from intermediate states after failures,
avoiding costly recomputation of completed steps.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    """Data saved at a pipeline checkpoint."""

    checkpoint_id: str = field(default_factory=lambda: uuid4().hex[:12])
    run_id: str = ""
    step_name: str = ""

    # State
    intermediate_data: Optional[Any] = None
    data_path: Optional[str] = None
    data_format: str = "pickle"

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    step_duration_seconds: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)

    # Recovery
    can_resume_from: bool = True
    resume_instructions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckpointMetadata:
    """Metadata about a checkpoint."""

    checkpoint_id: str = ""
    run_id: str = ""
    step_name: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    data_size_bytes: int = 0
    data_hash: str = ""


class PipelineCheckpointManager:
    """Manages pipeline checkpoints for fault tolerance.

    Every pipeline step can create a checkpoint. If a pipeline fails
    at step N, it can resume from step N-1's checkpoint instead of
    restarting from scratch.
    """

    def __init__(self, base_path: str = "pipeline_checkpoints") -> None:
        self._base_path = base_path
        self._checkpoints: Dict[str, CheckpointData] = {}
        self._run_checkpoints: Dict[str, List[str]] = {}  # run_id -> [checkpoint_ids]

    # -- Save --

    async def save_checkpoint(
        self,
        run_id: str,
        step_name: str,
        data: Any,
        metrics: Optional[Dict[str, float]] = None,
        duration_seconds: float = 0.0,
    ) -> str:
        """Save a checkpoint for a pipeline step.

        Args:
            run_id: Pipeline run ID.
            step_name: Step that just completed.
            data: Intermediate data to checkpoint.
            metrics: Step metrics.
            duration_seconds: Step duration.

        Returns:
            Checkpoint ID.
        """
        import pickle

        checkpoint = CheckpointData(
            run_id=run_id,
            step_name=step_name,
            intermediate_data=data,
            metrics=metrics or {},
            step_duration_seconds=duration_seconds,
        )

        # Serialize to disk
        os.makedirs(self._base_path, exist_ok=True)
        data_path = os.path.join(self._base_path, f"{checkpoint.checkpoint_id}.pkl")

        try:
            with open(data_path, "wb") as f:
                pickle.dump(data, f)
            checkpoint.data_path = data_path
        except Exception as exc:
            logger.error("Failed to save checkpoint data: %s", exc)
            # Fallback: keep in memory only
            pass

        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        if run_id not in self._run_checkpoints:
            self._run_checkpoints[run_id] = []
        self._run_checkpoints[run_id].append(checkpoint.checkpoint_id)

        logger.info("Checkpoint saved: %s (run=%s, step=%s)", checkpoint.checkpoint_id, run_id, step_name)
        return checkpoint.checkpoint_id

    # -- Load --

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Load a checkpoint by ID."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            logger.warning("Checkpoint not found: %s", checkpoint_id)
            return None

        # Load from disk if not in memory
        if checkpoint.intermediate_data is None and checkpoint.data_path:
            try:
                import pickle
                with open(checkpoint.data_path, "rb") as f:
                    checkpoint.intermediate_data = pickle.load(f)
            except Exception as exc:
                logger.error("Failed to load checkpoint data: %s", exc)
                return None

        return checkpoint

    async def load_latest_checkpoint(self, run_id: str) -> Optional[CheckpointData]:
        """Load the most recent checkpoint for a pipeline run."""
        checkpoint_ids = self._run_checkpoints.get(run_id, [])
        if not checkpoint_ids:
            return None
        return await self.load_checkpoint(checkpoint_ids[-1])

    async def load_checkpoint_for_step(self, run_id: str, step_name: str) -> Optional[CheckpointData]:
        """Load the checkpoint for a specific step."""
        checkpoint_ids = self._run_checkpoints.get(run_id, [])
        for cid in reversed(checkpoint_ids):
            checkpoint = self._checkpoints.get(cid)
            if checkpoint and checkpoint.step_name == step_name:
                return await self.load_checkpoint(cid)
        return None

    # -- Recovery --

    async def get_resume_point(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Determine where a failed pipeline can resume from.

        Returns:
            Dict with 'step_name' and 'checkpoint_id' indicating
            the last successfully completed step to resume from.
        """
        checkpoint_ids = self._run_checkpoints.get(run_id, [])
        if not checkpoint_ids:
            logger.warning("No checkpoints found for run %s", run_id)
            return None

        # Get the last successful checkpoint
        last_checkpoint = self._checkpoints.get(checkpoint_ids[-1])
        if last_checkpoint is None:
            return None

        return {
            "run_id": run_id,
            "last_completed_step": last_checkpoint.step_name,
            "checkpoint_id": last_checkpoint.checkpoint_id,
            "can_resume": last_checkpoint.can_resume_from,
            "created_at": last_checkpoint.created_at.isoformat(),
        }

    # -- Cleanup --

    async def cleanup_run(self, run_id: str) -> int:
        """Clean up all checkpoints for a completed run."""
        checkpoint_ids = self._run_checkpoints.pop(run_id, [])
        count = 0
        for cid in checkpoint_ids:
            checkpoint = self._checkpoints.pop(cid, None)
            if checkpoint and checkpoint.data_path and os.path.exists(checkpoint.data_path):
                os.remove(checkpoint.data_path)
                count += 1
        return count

    def list_checkpoints(self, run_id: Optional[str] = None) -> List[CheckpointMetadata]:
        """List checkpoints, optionally filtered by run."""
        checkpoints = list(self._checkpoints.values())
        if run_id:
            checkpoints = [c for c in checkpoints if c.run_id == run_id]

        return [
            CheckpointMetadata(
                checkpoint_id=c.checkpoint_id,
                run_id=c.run_id,
                step_name=c.step_name,
                created_at=c.created_at,
                data_size_bytes=os.path.getsize(c.data_path) if c.data_path and os.path.exists(c.data_path) else 0,
                data_hash="",
            )
            for c in checkpoints
        ]
