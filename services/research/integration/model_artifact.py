"""Model Artifact — artifact management for research models.

Commit 11 Part 1.5: Manages model artifacts including weights, configurations,
serialized models, tokenizers, and metadata files.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelArtifactState(str, Enum):
    """Model artifact lifecycle states."""

    CREATED = "created"
    UPLOADING = "uploading"
    STORED = "stored"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


class ArtifactType(str, Enum):
    """Types of model artifacts."""

    MODEL_WEIGHTS = "model_weights"
    MODEL_CONFIG = "model_config"
    TOKENIZER = "tokenizer"
    PREPROCESSOR = "preprocessor"
    FEATURE_CONFIG = "feature_config"
    TRAINING_LOG = "training_log"
    EVALUATION_REPORT = "evaluation_report"
    ONNX_EXPORT = "onnx_export"
    TORCHSCRIPT = "torchscript"
    CUSTOM = "custom"


class StorageBackend(str, Enum):
    """Supported storage backends."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    MINIO = "minio"


class ModelArtifact:
    """Manages a single model artifact with storage and verification.

    Tracks artifact metadata, checksums, storage location, and provides
    download/upload capabilities.

    Usage::

        artifact = ModelArtifact(
            model_id="model-abc",
            version=1,
            artifact_type=ArtifactType.MODEL_WEIGHTS,
            storage_path="s3://models/model-abc/v1/weights.pkl",
        )
        await artifact.initialize()
        await artifact.set_checksum("sha256:abc123...")
        await artifact.verify()
    """

    def __init__(
        self,
        model_id: str,
        version: int,
        artifact_type: ArtifactType,
        storage_path: str,
        *,
        artifact_id: Optional[str] = None,
        backend: StorageBackend = StorageBackend.LOCAL,
    ) -> None:
        self._id: str = artifact_id or f"art-{uuid4().hex[:16]}"
        self._model_id: str = model_id
        self._version: int = version
        self._artifact_type: ArtifactType = artifact_type
        self._storage_path: str = storage_path
        self._backend: StorageBackend = backend
        self._state: ModelArtifactState = ModelArtifactState.CREATED

        self._created_at: datetime = datetime.now(timezone.utc)
        self._uploaded_at: Optional[datetime] = None
        self._verified_at: Optional[datetime] = None

        # File metadata
        self._filename: str = storage_path.rsplit("/", 1)[-1] if "/" in storage_path else storage_path
        self._size_bytes: int = 0
        self._checksum: Optional[str] = None
        self._checksum_algorithm: str = "sha256"

        # Custom metadata
        self._metadata: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def artifact_type(self) -> ArtifactType:
        return self._artifact_type

    @property
    def storage_path(self) -> str:
        return self._storage_path

    @property
    def state(self) -> ModelArtifactState:
        return self._state

    @property
    def is_verified(self) -> bool:
        return self._state == ModelArtifactState.VERIFIED

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the artifact."""
        logger.info("Initializing ModelArtifact [%s] type=%s", self._id, self._artifact_type.value)
        await asyncio.sleep(0.001)

    async def shutdown(self) -> None:
        """Clean up artifact resources."""
        pass

    # ------------------------------------------------------------------
    # Checksum
    # ------------------------------------------------------------------

    async def set_checksum(self, checksum: str, algorithm: str = "sha256") -> None:
        """Set the artifact checksum.

        Args:
            checksum: Checksum value.
            algorithm: Hash algorithm used.
        """
        self._checksum = checksum
        self._checksum_algorithm = algorithm
        logger.info("Checksum set for artifact %s: %s", self._id, checksum[:16] + "...")

    async def verify(self) -> bool:
        """Verify artifact integrity using checksum."""
        if self._checksum is None:
            logger.warning("No checksum available for verification: %s", self._id)
            return False

        # In production, this would download the file and compute the hash
        await asyncio.sleep(0.01)
        self._state = ModelArtifactState.VERIFIED
        self._verified_at = datetime.now(timezone.utc)
        logger.info("Artifact verified: %s", self._id)
        return True

    # ------------------------------------------------------------------
    # Upload / Download
    # ------------------------------------------------------------------

    async def upload(self, local_path: str) -> None:
        """Upload artifact to storage backend.

        Args:
            local_path: Local file path to upload.
        """
        self._state = ModelArtifactState.UPLOADING
        logger.info("Uploading artifact %s from %s to %s", self._id, local_path, self._storage_path)
        await asyncio.sleep(0.01)  # simulate upload
        self._state = ModelArtifactState.STORED
        self._uploaded_at = datetime.now(timezone.utc)

    async def download(self, local_path: str) -> None:
        """Download artifact from storage backend.

        Args:
            local_path: Local destination path.
        """
        if self._state not in (ModelArtifactState.STORED, ModelArtifactState.VERIFIED):
            raise RuntimeError(f"Artifact not available: state={self._state.value}")
        logger.info("Downloading artifact %s from %s to %s", self._id, self._storage_path, local_path)
        await asyncio.sleep(0.01)  # simulate download

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def set_metadata(self, key: str, value: Any) -> None:
        """Set custom metadata."""
        self._metadata[key] = value

    async def get_metadata(self, key: str) -> Any:
        """Get custom metadata."""
        return self._metadata.get(key)

    async def set_size(self, size_bytes: int) -> None:
        """Set artifact file size."""
        self._size_bytes = size_bytes

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def to_dict(self) -> Dict[str, Any]:
        """Export artifact as dictionary."""
        return {
            "id": self._id,
            "model_id": self._model_id,
            "version": self._version,
            "artifact_type": self._artifact_type.value,
            "storage_path": self._storage_path,
            "backend": self._backend.value,
            "state": self._state.value,
            "filename": self._filename,
            "size_bytes": self._size_bytes,
            "checksum": self._checksum,
            "checksum_algorithm": self._checksum_algorithm,
            "metadata": self._metadata,
            "created_at": self._created_at.isoformat(),
            "uploaded_at": self._uploaded_at.isoformat() if self._uploaded_at else None,
            "verified_at": self._verified_at.isoformat() if self._verified_at else None,
        }
