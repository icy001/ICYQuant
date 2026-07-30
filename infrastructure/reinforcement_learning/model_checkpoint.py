"""Infrastructure: RL Model Checkpoint and Persistent Storage.

Handles saving/loading of RL model checkpoints with:
- Versioned checkpoints
- Metadata tracking
- Best model management
- Compression support
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import os
import json
import pickle
import time
import logging
from enum import Enum
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class CheckpointType(Enum):
    """Type of checkpoint."""
    PERIODIC = "periodic"
    BEST_REWARD = "best_reward"
    BEST_SHARPE = "best_sharpe"
    LATEST = "latest"
    MANUAL = "manual"


@dataclass
class CheckpointMetadata:
    """Metadata for a model checkpoint."""

    model_id: str
    checkpoint_type: CheckpointType = CheckpointType.PERIODIC
    version: int = 1
    step: int = 0
    episode: int = 0
    reward: float = 0.0
    sharpe_ratio: float = 0.0

    # Model info
    algorithm: str = "ppo"
    state_dim: int = 64
    action_dim: int = 3
    hidden_layers: List[int] = field(default_factory=lambda: [256, 256, 128])

    # Timing
    created_at: str = ""
    training_time_seconds: float = 0.0

    # Storage
    file_path: str = ""
    file_size_bytes: int = 0
    compressed: bool = False

    # Custom tags
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "checkpoint_type": self.checkpoint_type.value,
            "version": self.version,
            "step": self.step,
            "episode": self.episode,
            "reward": self.reward,
            "sharpe_ratio": self.sharpe_ratio,
            "algorithm": self.algorithm,
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "hidden_layers": self.hidden_layers,
            "created_at": self.created_at,
            "training_time_seconds": self.training_time_seconds,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "compressed": self.compressed,
            "tags": self.tags,
        }


class ModelCheckpoint:
    """Model checkpoint management system.

    Handles saving, loading, and versioning of RL model checkpoints
    with metadata tracking and best model management.

    Usage:
        checkpoint = ModelCheckpoint("./checkpoints", "ppo_trader_v1")
        checkpoint.save(policy_params, metrics)
        params = checkpoint.load("best")
        history = checkpoint.list_checkpoints()
    """

    def __init__(
        self,
        base_dir: str = "./checkpoints",
        model_id: Optional[str] = None,
        max_checkpoints: int = 10,
        compress: bool = False,
    ):
        self.base_dir = base_dir
        self.model_id = model_id or f"rl_model_{int(time.time())}"
        self.max_checkpoints = max_checkpoints
        self.compress = compress

        self._checkpoint_dir = os.path.join(base_dir, self.model_id)
        self._metadata_file = os.path.join(self._checkpoint_dir, "metadata.json")
        self._checkpoints: List[CheckpointMetadata] = []

        os.makedirs(self._checkpoint_dir, exist_ok=True)

        # Load existing metadata
        self._load_metadata()

    def save(
        self,
        params: Dict[str, np.ndarray],
        metrics: Optional[Dict[str, float]] = None,
        checkpoint_type: CheckpointType = CheckpointType.PERIODIC,
        step: int = 0,
        episode: int = 0,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Save a model checkpoint.

        Args:
            params: Model parameters dict
            metrics: Training metrics
            checkpoint_type: Type of checkpoint
            step: Current training step
            episode: Current episode
            tags: Custom tags

        Returns:
            Path to saved checkpoint
        """
        version = len(self._checkpoints) + 1
        filename = f"{checkpoint_type.value}_{version:04d}.pkl"
        filepath = os.path.join(self._checkpoint_dir, filename)

        # If saving "best" checkpoint, remove old best
        if checkpoint_type in (
            CheckpointType.BEST_REWARD,
            CheckpointType.BEST_SHARPE,
        ):
            self._cleanup_old_type(checkpoint_type)

        # Save parameters
        save_data = {
            "params": params,
            "version": version,
            "step": step,
            "episode": episode,
            "metrics": metrics or {},
        }

        if self.compress:
            import gzip
            with gzip.open(filepath + ".gz", "wb") as f:
                pickle.dump(save_data, f)
        else:
            with open(filepath, "wb") as f:
                pickle.dump(save_data, f)

        # Create metadata
        meta = CheckpointMetadata(
            model_id=self.model_id,
            checkpoint_type=checkpoint_type,
            version=version,
            step=step,
            episode=episode,
            reward=metrics.get("reward", 0.0) if metrics else 0.0,
            sharpe_ratio=metrics.get("sharpe", 0.0) if metrics else 0.0,
            algorithm=metrics.get("algorithm", "ppo") if metrics else "ppo",
            state_dim=params.get("state_dim", 64) if hasattr(params, "get") else 64,
            action_dim=params.get("action_dim", 3) if hasattr(params, "get") else 3,
            created_at=datetime.now().isoformat(),
            file_path=filepath,
            file_size_bytes=os.path.getsize(filepath),
            compressed=self.compress,
            tags=tags or {},
        )

        self._checkpoints.append(meta)

        # Enforce max checkpoints
        if len(self._checkpoints) > self.max_checkpoints:
            self._prune_old_checkpoints()

        # Save metadata
        self._save_metadata()

        logger.info(f"Checkpoint saved: {filepath} (v{version}, step={step})")
        return filepath

    def load(self, identifier: str = "best") -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Load a model checkpoint.

        Args:
            identifier: "best", "latest", version number, or file path

        Returns:
            (params, metadata) tuple
        """
        meta = self._resolve_checkpoint(identifier)
        if meta is None:
            raise FileNotFoundError(f"No checkpoint found for '{identifier}'")

        filepath = meta.file_path
        if meta.compressed:
            import gzip
            with gzip.open(filepath, "rb") as f:
                save_data = pickle.load(f)
        else:
            with open(filepath, "rb") as f:
                save_data = pickle.load(f)

        params = save_data.get("params", {})
        saved_metrics = save_data.get("metrics", {})
        return params, {**meta.to_dict(), **saved_metrics}

    def load_best(
        self, metric: str = "reward"
    ) -> Optional[Tuple[Dict[str, np.ndarray], Dict[str, Any]]]:
        """Load the best checkpoint by a specific metric."""
        if not self._checkpoints:
            return None

        if metric == "reward":
            best_meta = max(
                self._checkpoints,
                key=lambda m: m.reward,
            )
        elif metric == "sharpe":
            best_meta = max(
                self._checkpoints,
                key=lambda m: m.sharpe_ratio,
            )
        else:
            best_meta = max(
                self._checkpoints,
                key=lambda m: m.reward,
            )

        return self.load(str(best_meta.version))

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints."""
        return [m.to_dict() for m in self._checkpoints]

    def get_best_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get the best checkpoint by reward."""
        if not self._checkpoints:
            return None
        return max(self._checkpoints, key=lambda m: m.reward)

    def get_latest_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get the latest checkpoint."""
        if not self._checkpoints:
            return None
        return max(self._checkpoints, key=lambda m: m.version)

    def delete_checkpoint(self, identifier: str):
        """Delete a specific checkpoint."""
        meta = self._resolve_checkpoint(identifier)
        if meta is None:
            return

        if os.path.exists(meta.file_path):
            os.remove(meta.file_path)

        self._checkpoints = [c for c in self._checkpoints if c != meta]
        self._save_metadata()

    def clear(self):
        """Remove all checkpoints."""
        for meta in self._checkpoints:
            if os.path.exists(meta.file_path):
                os.remove(meta.file_path)
        self._checkpoints = []
        self._save_metadata()

    def _resolve_checkpoint(self, identifier: str) -> Optional[CheckpointMetadata]:
        """Resolve checkpoint identifier to metadata."""
        if not self._checkpoints:
            return None

        if identifier == "best":
            return self.get_best_checkpoint()
        elif identifier == "latest":
            return self.get_latest_checkpoint()
        elif identifier.isdigit():
            version = int(identifier)
            for c in self._checkpoints:
                if c.version == version:
                    return c
            return None
        elif os.path.exists(identifier):
            # Check by file path
            search = os.path.abspath(identifier)
            for c in self._checkpoints:
                if os.path.abspath(c.file_path) == search:
                    return c
            return None
        else:
            # Try checkpoint type
            for c in self._checkpoints:
                if c.checkpoint_type.value == identifier:
                    return c
            return None

    def _save_metadata(self):
        """Save metadata to JSON."""
        metadata = [m.to_dict() for m in self._checkpoints]
        with open(self._metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _load_metadata(self):
        """Load metadata from JSON."""
        if os.path.exists(self._metadata_file):
            try:
                with open(self._metadata_file, "r") as f:
                    data = json.load(f)
                for entry in data:
                    meta = CheckpointMetadata(
                        model_id=entry.get("model_id", self.model_id),
                        checkpoint_type=CheckpointType(entry.get("checkpoint_type", "periodic")),
                        version=entry.get("version", 1),
                        step=entry.get("step", 0),
                        episode=entry.get("episode", 0),
                        reward=entry.get("reward", 0.0),
                        sharpe_ratio=entry.get("sharpe_ratio", 0.0),
                        algorithm=entry.get("algorithm", "ppo"),
                        state_dim=entry.get("state_dim", 64),
                        action_dim=entry.get("action_dim", 3),
                        created_at=entry.get("created_at", ""),
                        training_time_seconds=entry.get("training_time_seconds", 0.0),
                        file_path=entry.get("file_path", ""),
                        file_size_bytes=entry.get("file_size_bytes", 0),
                        compressed=entry.get("compressed", False),
                        tags=entry.get("tags", {}),
                    )
                    self._checkpoints.append(meta)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")

    def _cleanup_old_type(self, checkpoint_type: CheckpointType):
        """Remove old checkpoints of the same type."""
        to_remove = [
            c for c in self._checkpoints
            if c.checkpoint_type == checkpoint_type
        ]
        for c in to_remove:
            if os.path.exists(c.file_path):
                os.remove(c.file_path)
            self._checkpoints.remove(c)

    def _prune_old_checkpoints(self):
        """Remove oldest checkpoints to stay under max."""
        # Keep best checkpoints, remove oldest periodic ones
        periodic = sorted(
            [c for c in self._checkpoints if c.checkpoint_type == CheckpointType.PERIODIC],
            key=lambda c: c.version,
        )
        while len(self._checkpoints) > self.max_checkpoints and periodic:
            oldest = periodic.pop(0)
            if os.path.exists(oldest.file_path):
                os.remove(oldest.file_path)
            self._checkpoints.remove(oldest)
