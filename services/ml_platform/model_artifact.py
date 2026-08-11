"""
ICYQuant Model Artifact - Model artifact management.

Manages serialized model files with integrity verification,
metadata tracking, and storage backend abstraction.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ArtifactFormat(Enum):
    """Supported model serialization formats."""

    PICKLE = "pickle"
    JOBLIB = "joblib"
    ONNX = "onnx"
    PMML = "pmml"
    TORCHSCRIPT = "torchscript"
    TENSORFLOW_SAVEDMODEL = "tf_savedmodel"
    JSON = "json"            # for lightweight models (e.g., sklearn params)
    CUSTOM = "custom"


class ArtifactBackend(Enum):
    """Storage backends for model artifacts."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    HDFS = "hdfs"


@dataclass
class ModelArtifact:
    """A serialized model artifact with metadata."""

    artifact_id: str = ""
    model_id: str = ""
    version_id: str = ""
    format: ArtifactFormat = ArtifactFormat.JOBLIB

    # Storage
    backend: ArtifactBackend = ArtifactBackend.LOCAL
    path: str = ""                 # file path or object key
    size_bytes: int = 0

    # Integrity
    sha256_hash: str = ""
    md5_hash: str = ""

    # Model specifics
    framework: str = "lightgbm"
    framework_version: str = ""
    model_class: str = ""         # full class path

    # Dependencies
    requirements: List[str] = field(default_factory=list)
    python_version: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of the artifact file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def verify_integrity(self) -> bool:
        """Verify artifact integrity by recomputing hash."""
        if not os.path.exists(self.path):
            logger.error("Artifact file not found: %s", self.path)
            return False

        current_hash = self.compute_hash(self.path)
        is_valid = current_hash == self.sha256_hash
        if not is_valid:
            logger.error("Artifact hash mismatch: expected=%s, actual=%s",
                         self.sha256_hash[:16], current_hash[:16])
        return is_valid


class ModelArtifactManager:
    """Manages model artifact lifecycle.

    Handles:
    - Saving trained models with version metadata
    - Loading models for inference
    - Integrity verification
    - Multi-backend storage (local, S3, GCS)
    - Artifact cleanup and retention
    """

    def __init__(self, base_path: str = "models/artifacts") -> None:
        self._base_path = base_path
        self._artifacts: Dict[str, ModelArtifact] = {}

    # -- Save --

    async def save(
        self,
        model: Any,
        model_id: str,
        version_id: str,
        format: ArtifactFormat = ArtifactFormat.JOBLIB,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelArtifact:
        """Save a model as an artifact.

        Args:
            model: The trained model object.
            model_id: Model identifier.
            version_id: Version identifier.
            format: Serialization format.
            metadata: Additional metadata.

        Returns:
            ModelArtifact with storage info and hash.
        """
        import uuid

        artifact_id = uuid.uuid4().hex[:12]
        filename = f"{model_id}_{version_id}_{artifact_id}.{format.value}"
        filepath = os.path.join(self._base_path, model_id, filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        artifact = ModelArtifact(
            artifact_id=artifact_id,
            model_id=model_id,
            version_id=version_id,
            format=format,
            path=filepath,
            framework=metadata.get("framework", "unknown") if metadata else "unknown",
        )

        # Placeholder: actual serialization in production
        # import joblib
        # joblib.dump(model, filepath)
        # artifact.sha256_hash = artifact.compute_hash(filepath)
        # artifact.size_bytes = os.path.getsize(filepath)

        self._artifacts[artifact_id] = artifact
        logger.info("Model artifact saved: %s (%s)", artifact_id, filepath)
        return artifact

    # -- Load --

    async def load(self, artifact_id: str) -> Optional[Any]:
        """Load a model from an artifact.

        Verifies integrity before loading.
        """
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            logger.warning("Artifact not found: %s", artifact_id)
            return None

        if not artifact.verify_integrity():
            logger.error("Artifact integrity check failed: %s", artifact_id)
            return None

        # Placeholder: actual deserialization in production
        # import joblib
        # return joblib.load(artifact.path)
        return None

    async def load_latest(self, model_id: str) -> Optional[Any]:
        """Load the latest artifact for a model."""
        artifacts_for_model = [
            a for a in self._artifacts.values()
            if a.model_id == model_id
        ]
        if not artifacts_for_model:
            return None

        latest = max(artifacts_for_model, key=lambda a: a.created_at)
        return await self.load(latest.artifact_id)

    # -- Management --

    def get_artifact(self, artifact_id: str) -> Optional[ModelArtifact]:
        """Get artifact metadata."""
        return self._artifacts.get(artifact_id)

    def list_artifacts(self, model_id: Optional[str] = None) -> List[ModelArtifact]:
        """List artifacts, optionally filtered by model."""
        artifacts = list(self._artifacts.values())
        if model_id:
            artifacts = [a for a in artifacts if a.model_id == model_id]
        return sorted(artifacts, key=lambda a: a.created_at, reverse=True)

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact (metadata + file)."""
        artifact = self._artifacts.pop(artifact_id, None)
        if artifact and os.path.exists(artifact.path):
            os.remove(artifact.path)
            logger.info("Artifact deleted: %s", artifact_id)
            return True
        return False

    async def cleanup_old_versions(
        self, model_id: str, keep_latest: int = 5,
    ) -> int:
        """Remove old artifacts, keeping only the N most recent."""
        artifacts = self.list_artifacts(model_id)
        to_delete = artifacts[keep_latest:]
        count = 0
        for artifact in to_delete:
            if await self.delete_artifact(artifact.artifact_id):
                count += 1
        return count
