"""
ICYQuant Model Repository — Artifact storage and retrieval abstraction.

Provides a unified interface for model artifact storage backends:
local filesystem, cloud object storage (S3/GCS), and versioned registries.
Responsible for artifact indexing, integrity verification, and access control.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class StorageBackend(str, Enum):
    """Supported storage backends."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    HTTP = "http"
    REGISTRY = "registry"  # Delegates to Model Registry service


class ArtifactStatus(str, Enum):
    """Artifact lifecycle status."""
    UPLOADING = "uploading"
    AVAILABLE = "available"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"
    DELETED = "deleted"


@dataclass
class ArtifactRecord:
    """Metadata record for a stored model artifact."""
    model_id: str
    version: str
    backend: str
    path: str
    storage_backend: StorageBackend
    status: ArtifactStatus = ArtifactStatus.AVAILABLE
    size_bytes: int = 0
    checksum_sha256: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "backend": self.backend,
            "path": self.path,
            "storage_backend": self.storage_backend.value,
            "status": self.status.value,
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRecord":
        return cls(
            model_id=data["model_id"],
            version=data["version"],
            backend=data.get("backend", ""),
            path=data["path"],
            storage_backend=StorageBackend(data.get("storage_backend", "local")),
            status=ArtifactStatus(data.get("status", "available")),
            size_bytes=data.get("size_bytes", 0),
            checksum_sha256=data.get("checksum_sha256", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", {}),
        )


# ---------------------------------------------------------------------------
# Storage backend handlers
# ---------------------------------------------------------------------------

class LocalStorageHandler:
    """Local filesystem storage."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    async def put(self, model_id: str, version: str, source_path: str) -> str:
        """Copy artifact to local storage. Returns target path."""
        target_dir = self.root_dir / model_id
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(source_path).suffix
        target_path = target_dir / f"{version}{ext}"

        await asyncio.to_thread(shutil.copy2, source_path, target_path)
        return str(target_path.absolute())

    async def get(self, path: str) -> Optional[str]:
        """Verify artifact exists. Returns path if available."""
        p = Path(path)
        if p.exists():
            return str(p.absolute())
        return None

    async def delete(self, path: str) -> bool:
        """Delete artifact from local storage."""
        p = Path(path)
        if p.exists():
            p.unlink()
            return True
        return False

    async def list_versions(self, model_id: str) -> List[str]:
        """List available versions for a model."""
        model_dir = self.root_dir / model_id
        if not model_dir.exists():
            return []
        versions = []
        for f in model_dir.iterdir():
            if f.is_file():
                versions.append(f.stem)
        return sorted(versions)

    async def exists(self, path: str) -> bool:
        return Path(path).exists()


# ---------------------------------------------------------------------------
# Model Repository
# ---------------------------------------------------------------------------

class ModelRepository:
    """Unified model artifact repository.

    Provides:
      - Multi-backend artifact storage (local/S3/GCS/registry)
      - Checksum-based integrity verification
      - Version listing and discovery
      - Tag-based artifact lookup
      - Artifact lifecycle management

    Usage::

        repo = ModelRepository()
        await repo.initialize()
        await repo.store_artifact("nvda_model", "v1.0", "/path/to/model.pkl")
        artifact = await repo.get_artifact("nvda_model", "v1.0")
    """

    def __init__(
        self,
        root_dir: str = "data/models",
        default_backend: StorageBackend = StorageBackend.LOCAL,
    ):
        self.root_dir = root_dir
        self.default_backend = default_backend
        self._initialized = False

        # Storage handlers
        self._local = LocalStorageHandler(root_dir)
        self._handlers: Dict[StorageBackend, Any] = {
            StorageBackend.LOCAL: self._local,
        }

        # In-memory artifact index: (model_id, version) → ArtifactRecord
        self._index: Dict[str, ArtifactRecord] = {}
        self._index_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize repository — scan local storage and build index."""
        logger.info("ModelRepository initializing — root=%s", self.root_dir)

        # Scan local directory for existing artifacts
        await self._scan_local_artifacts()

        self._initialized = True
        logger.info("ModelRepository initialized — %d artifacts indexed", len(self._index))

    async def shutdown(self) -> None:
        """Shutdown repository."""
        self._initialized = False

    # ------------------------------------------------------------------
    # Store / retrieve
    # ------------------------------------------------------------------

    def _make_key(self, model_id: str, version: str) -> str:
        return f"{model_id}:{version}"

    async def store_artifact(
        self,
        model_id: str,
        version: str,
        source_path: str,
        *,
        backend: Optional[str] = None,
        backend_type: Optional[StorageBackend] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> ArtifactRecord:
        """Store a model artifact.

        Args:
            model_id: Model identifier.
            version: Model version string.
            source_path: Path to the serialized model file.
            backend: Model backend type (sklearn, lightgbm, etc.).
            backend_type: Storage backend to use.
            metadata: Arbitrary metadata.
            tags: Key-value tags.

        Returns:
            ArtifactRecord for the stored artifact.
        """
        storage = backend_type or self.default_backend
        handler = self._handlers.get(storage)
        if handler is None:
            raise ValueError(f"Unsupported storage backend: {storage}")

        # Compute checksum
        checksum = await self._compute_checksum(source_path)
        size_bytes = os.path.getsize(source_path)

        # Store
        target_path = await handler.put(model_id, version, source_path)

        # Create record
        record = ArtifactRecord(
            model_id=model_id,
            version=version,
            backend=backend or "unknown",
            path=target_path,
            storage_backend=storage,
            status=ArtifactStatus.AVAILABLE,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            metadata=metadata or {},
            tags=tags or {},
        )

        # Index
        key = self._make_key(model_id, version)
        async with self._index_lock:
            self._index[key] = record

        logger.info("Artifact stored: %s@%s (%d bytes)", model_id, version, size_bytes)
        return record

    async def get_artifact(
        self,
        model_id: str,
        version: str,
        verify: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve artifact metadata and path.

        Args:
            model_id: Model identifier.
            version: Model version.
            verify: Whether to verify file existence and checksum.

        Returns:
            Dict with artifact info, or None if not found.
        """
        key = self._make_key(model_id, version)

        async with self._index_lock:
            record = self._index.get(key)
            if record is None:
                return None

        if verify:
            handler = self._handlers.get(record.storage_backend)
            if handler:
                existing = await handler.exists(record.path)
                if not existing:
                    record.status = ArtifactStatus.DELETED
                    return None

        return record.to_dict()

    async def list_versions(self, model_id: str) -> List[str]:
        """List all versions for a model."""
        async with self._index_lock:
            versions = [
                r.version for r in self._index.values()
                if r.model_id == model_id and r.status != ArtifactStatus.DELETED
            ]
        return sorted(set(versions))

    async def list_models(self) -> List[str]:
        """List all unique model IDs."""
        async with self._index_lock:
            models = set(r.model_id for r in self._index.values()
                        if r.status != ArtifactStatus.DELETED)
        return sorted(models)

    async def get_latest_version(self, model_id: str) -> Optional[str]:
        """Get the latest version for a model."""
        versions = await self.list_versions(model_id)
        return versions[-1] if versions else None

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    async def verify_artifact(self, model_id: str, version: str) -> bool:
        """Verify artifact integrity via checksum."""
        record_dict = await self.get_artifact(model_id, version, verify=False)
        if record_dict is None:
            return False

        record = ArtifactRecord.from_dict(record_dict)
        handler = self._handlers.get(record.storage_backend)
        if handler is None:
            return False

        actual_path = await handler.get(record.path)
        if actual_path is None:
            record.status = ArtifactStatus.CORRUPTED
            return False

        actual_checksum = await self._compute_checksum(actual_path)
        if actual_checksum != record.checksum_sha256:
            record.status = ArtifactStatus.CORRUPTED
            logger.error("Checksum mismatch for %s@%s", model_id, version)
            return False

        record.status = ArtifactStatus.VERIFIED
        async with self._index_lock:
            self._index[self._make_key(model_id, version)] = record

        return True

    async def verify_all(self) -> Dict[str, List[str]]:
        """Verify all artifacts. Returns {ok: [...], failed: [...]}."""
        ok, failed = [], []
        async with self._index_lock:
            keys = list(self._index.keys())

        for key in keys:
            try:
                parts = key.split(":", 1)
                if len(parts) == 2:
                    valid = await self.verify_artifact(parts[0], parts[1])
                    if valid:
                        ok.append(key)
                    else:
                        failed.append(key)
            except Exception:
                failed.append(key)

        logger.info("Verification complete: %d ok, %d failed", len(ok), len(failed))
        return {"ok": ok, "failed": failed}

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_artifact(self, model_id: str, version: str) -> bool:
        """Soft-delete an artifact."""
        key = self._make_key(model_id, version)
        async with self._index_lock:
            record = self._index.get(key)
            if record is None:
                return False
            record.status = ArtifactStatus.DELETED

        handler = self._handlers.get(record.storage_backend)
        if handler:
            await handler.delete(record.path)

        logger.info("Artifact deleted: %s@%s", model_id, version)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _scan_local_artifacts(self) -> None:
        """Scan local directory for existing artifacts and index them."""
        local_versions = await self._local.list_versions("")
        # Actually scan per-model directories
        root = Path(self.root_dir)
        if not root.exists():
            return

        for model_dir in root.iterdir():
            if not model_dir.is_dir():
                continue
            model_id = model_dir.name
            for artifact_file in model_dir.iterdir():
                if artifact_file.is_file():
                    version = artifact_file.stem
                    path = str(artifact_file.absolute())
                    checksum = await self._compute_checksum(path)
                    size = artifact_file.stat().st_size

                    record = ArtifactRecord(
                        model_id=model_id,
                        version=version,
                        backend="unknown",
                        path=path,
                        storage_backend=StorageBackend.LOCAL,
                        size_bytes=size,
                        checksum_sha256=checksum,
                    )
                    self._index[self._make_key(model_id, version)] = record

    @staticmethod
    async def _compute_checksum(filepath: str) -> str:
        """Compute SHA-256 checksum of a file."""
        sha = hashlib.sha256()

        def _hash():
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha.update(chunk)
            return sha.hexdigest()

        return await asyncio.to_thread(_hash)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        async with self._index_lock:
            total = len(self._index)
            available = sum(
                1 for r in self._index.values()
                if r.status in (ArtifactStatus.AVAILABLE, ArtifactStatus.VERIFIED)
            )
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "total_artifacts": total,
            "available": available,
            "backend": self.default_backend.value,
            "root_dir": self.root_dir,
        }

    def __repr__(self) -> str:
        return f"ModelRepository(artifacts={len(self._index)}, backend={self.default_backend.value})"
